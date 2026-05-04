# Force deployment to sync model state and fix ghost 'branch' column issue
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.http import JsonResponse, HttpResponse
from django.core.management import call_command
import json
import os
import requests
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials, messaging

def get_firebase_app():
    """Helper to initialize or get the Firebase app with robust config parsing."""
    if not firebase_admin._apps:
        try:
            # Clear ghost apps
            for app_name in list(firebase_admin._apps.keys()):
                firebase_admin.delete_app(firebase_admin._apps[app_name])
            
            cert_path = os.path.join(settings.BASE_DIR, 'serviceAccountKey.json')
            if os.path.exists(cert_path):
                cred = credentials.Certificate(cert_path)
                firebase_admin.initialize_app(cred)
            else:
                config_str = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '').strip()
                if not config_str:
                    raise Exception("FIREBASE_SERVICE_ACCOUNT env var is missing.")
                
                # Clean wrapping quotes
                if (config_str.startswith('"') and config_str.endswith('"')) or \
                   (config_str.startswith("'") and config_str.endswith("'")):
                    config_str = config_str[1:-1]
                
                cred_dict = None
                
                # Attempt 1: Direct parse
                try:
                    cred_dict = json.loads(config_str, strict=False)
                except json.JSONDecodeError as e1:
                    # Attempt 2: Escape literal newlines (common in some env loaders)
                    try:
                        cred_dict = json.loads(config_str.replace('\n', '\\n'), strict=False)
                    except json.JSONDecodeError as e2:
                        # Attempt 3: Aggressively handle backslashes
                        try:
                            # Doubling backslashes often fixes issues where the string is read "too raw"
                            fixed = config_str.replace('\\', '\\\\')
                            cred_dict = json.loads(fixed, strict=False)
                        except json.JSONDecodeError as e3:
                            print(f"DEBUG: Firebase JSON parsing failed. Error: {e1}")
                            raise e1
                
                # Normalize private_key newlines (Crucial for PEM loading)
                if cred_dict and 'private_key' in cred_dict:
                    pk = cred_dict['private_key']
                    if isinstance(pk, str):
                        # Replace literal \n or \\n with actual newline characters
                        import re
                        cred_dict['private_key'] = re.sub(r'\\+n', '\n', pk).replace('\r', '')
                
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            print("DEBUG: Firebase initialized successfully.")
        except Exception as e:
            print(f"Firebase Init Error: {e}")
            raise e
    return firebase_admin.get_app()
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.core.files.base import ContentFile
import base64
import math
from django.utils import timezone

from .models import Profile, Question, Option, UserAnswer, MatchRequest, Message, ProfileImage, WallStroke, WallImage, Confession, ConfessionComment, ConfessionLike, ConfessionReport, UserReport, Spark, BlockedUser, Announcement, FavoriteMovie, FavoriteSong, FCMToken, BannedIdentifier
from .forms import ProfileForm, ProfileEditForm, ProfileImageForm
from .supabase_utils import upload_to_supabase, delete_from_supabase_by_url
# AI imports moved inside functions to prevent Vercel crashes

# Safe print for Windows console encoding issues
def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(str(msg).encode('ascii', 'ignore').decode('ascii'))


@login_required
def complete_profile(request):
    user = request.user
    profile = getattr(user, 'profile', None)

    # If profile is already completed (has a name), don't allow re-entry to this setup page
    if profile and profile.name:
        return redirect('home')

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            new_profile = form.save(commit=False)
            new_profile.user = user
            
            # Face Verification Data (Simplified)
            verify_data = request.POST.get('verification_image_data')
            verify_url_client = request.POST.get('verification_image_url')
            verify_status = request.POST.get('verification_status', 'pending')
            
            if verify_url_client:
                # Use URL directly from client (most reliable)
                new_profile.verification_image = verify_url_client
                new_profile.verification_status = verify_status
                if verify_status == 'verified':
                    new_profile.is_face_verified = True
            elif verify_data:
                # Fallback: Save base64 to Supabase on server
                from .supabase_utils import upload_base64_to_supabase
                verify_url, _ = upload_base64_to_supabase(verify_data, bucket="images", path="verification")
                if verify_url:
                    new_profile.verification_image = verify_url
                    new_profile.verification_status = verify_status
                    if verify_status == 'verified':
                        new_profile.is_face_verified = True

            pic_url = request.POST.get('profile_pic_url')
            if pic_url:
                new_profile.profile_pic = pic_url
            elif 'profile_pic_file' in request.FILES:
                img_url = upload_to_supabase(request.FILES['profile_pic_file'], bucket="images", path="profile_pics")
                if img_url:
                    new_profile.profile_pic = img_url
                else:
                    messages.warning(request, "Photo upload failed.")

            if not new_profile.profile_pic:
                messages.error(request, "A profile picture is required to complete your profile.")
                return render(request, 'complete_profile.html', {'form': form})

            new_profile.save()

            # Gallery
            gallery_urls_raw = request.POST.get('gallery_urls')
            if gallery_urls_raw:
                urls = [u.strip() for u in gallery_urls_raw.split(',') if u.strip()]
                for u in urls:
                    ProfileImage.objects.create(profile=new_profile, image=u)
            else:
                gallery_files = request.FILES.getlist('gallery_images')
                for gf in gallery_files:
                    img_url = upload_to_supabase(gf, bucket="images", path="gallery")
                    if img_url: ProfileImage.objects.create(profile=new_profile, image=img_url)

            messages.success(request, "Profile created!")
            return redirect('home')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'complete_profile.html', {'form': form})

# ---------------- HOME / QUIZ ----------------
@login_required
def home(request):
    user = request.user
    
    # Try getting the profile, but catch schema errors if migration is needed
    try:
        profile, created = Profile.objects.get_or_create(user=user)
    except Exception as e:
        # If the database is broken (missing fields), try to migrate automatically
        if os.environ.get('VERCEL'):
            try:
                from django.core.management import call_command
                call_command('migrate', interactive=False)
                profile, created = Profile.objects.get_or_create(user=user)
            except Exception as e2:
                return HttpResponse(f"Database error: {str(e2)}. Please visit /run_migrations/.")
        else:
            raise e

    if not profile.name:
        return redirect('complete_profile')

    # If user is not discoverable, they can't see the feed
    if not profile.is_discoverable:
        return render(request, "home.html", {"not_discoverable": True, "profile": profile})

    # Get answered questions count
    answered_ids = list(UserAnswer.objects.filter(user=user).values_list("question_id", flat=True))
    ans_count = len(answered_ids)

    # ── 10-question round break ──
    # Round number = how many complete 10-question rounds the user has finished
    rounds_shown = request.session.get('rounds_shown', 0)
    current_round = ans_count // 10  # 10→1, 20→2, 30→3 ...

    if current_round > rounds_shown:
        # A new round has been completed — show a match
        request.session['rounds_shown'] = current_round
        return redirect('check_match')

    # CHECK IF ANY MATCHES ARE LEFT BEFORE SHOWING QUIZ
    # Exclude users where a MatchRequest exists in EITHER direction (sent, received, accepted, skipped, etc)
    interacted_user_ids = list(MatchRequest.objects.filter(sender=user).values_list('receiver_id', flat=True)) + \
                          list(MatchRequest.objects.filter(receiver=user).values_list('sender_id', flat=True))
    blocked_user_ids = list(BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)) + \
                       list(BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True))
    
    candidates_qs = Profile.objects.filter(is_discoverable=True).exclude(user=user).exclude(user__id__in=interacted_user_ids).exclude(user__id__in=blocked_user_ids)
    
    has_valid_candidates = False
    for c in candidates_qs:
        user_pref_ok = (profile.pref_gender == 'any' or profile.pref_gender == c.gender)
        cand_pref_ok = (c.pref_gender == 'any' or c.pref_gender == profile.gender)
        user_age_ok = True
        if profile.age:
            user_age_ok = (c.pref_age_min <= profile.age <= c.pref_age_max)
        cand_age_ok = True
        if c.age:
            cand_age_ok = (profile.pref_age_min <= c.age <= profile.pref_age_max)

        if user_pref_ok and cand_pref_ok and user_age_ok and cand_age_ok:
            has_valid_candidates = True
            break
        elif user_pref_ok and user_age_ok:
            # At least one person matches the user's criteria, even if the other person's criteria isn't met.
            # This allows the quiz to continue so the user can see potential matches even if they aren't perfect mutual matches.
            has_valid_candidates = True
            break

    if not has_valid_candidates:
        return render(request, "home.html", {
            "all_done": True, 
            "progress": 100,
            "matches": [],
            "profile": profile
        })

    question = Question.objects.exclude(id__in=answered_ids).first()

    if not question:
        # DISCOVERY MODE: Fetch and Rank All Potential Matches
        interacted_user_ids = list(MatchRequest.objects.filter(sender=user).values_list('receiver_id', flat=True)) + \
                              list(MatchRequest.objects.filter(receiver=user).values_list('sender_id', flat=True))
        blocked_user_ids = list(BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)) + \
                           list(BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True))
        
        candidates = Profile.objects.filter(is_discoverable=True).exclude(user=user).exclude(user__id__in=interacted_user_ids).exclude(user__id__in=blocked_user_ids).select_related('user')
        
        user_ans = UserAnswer.objects.filter(user=user).select_related('option')
        user_dict = {ans.question_id: ans.option.weight for ans in user_ans}
        
        cand_user_ids = [c.user_id for c in candidates]
        all_cand_ans = UserAnswer.objects.filter(user_id__in=cand_user_ids).select_related('option')
        
        cand_ans_map = {}
        for ans in all_cand_ans:
            if ans.user_id not in cand_ans_map: cand_ans_map[ans.user_id] = {}
            cand_ans_map[ans.user_id][ans.question_id] = ans.option.weight

        matches_list = []
        for c in candidates:
            user_pref_ok = (profile.pref_gender == 'any' or profile.pref_gender == c.gender)
            cand_pref_ok = (c.pref_gender == 'any' or c.pref_gender == profile.gender)
            
            if user_pref_ok: # Relaxed from (user_pref_ok and cand_pref_ok)
                cand_dict = cand_ans_map.get(c.user_id, {})
                score = calculate_match_score_optimized(user_dict, cand_dict)
                
                # Bonus for matching 'looking_for'
                if profile.looking_for == c.looking_for:
                    score += 5
                
                # Bonus for matching languages
                user_pref_langs = set(profile.pref_languages_list)
                cand_langs = set(c.languages_list)
                if user_pref_langs.intersection(cand_langs):
                    score += 5
                
                matches_list.append({'profile': c, 'score': min(score, 100)})
        
        matches_list.sort(key=lambda x: x['score'], reverse=True)
        sparked_ids = list(Spark.objects.filter(sender=user).values_list('receiver_id', flat=True))
        
        return render(request, "home.html", {
            "all_done": True, 
            "progress": 100,
            "matches": matches_list[:20],  # Show top 20
            "sparked_ids": sparked_ids,
            "profile": profile
        })

    total_q_db = Question.objects.count()
    progress = int((ans_count / total_q_db) * 100) if total_q_db > 0 else 0
    sparked_ids = list(Spark.objects.filter(sender=user).values_list('receiver_id', flat=True))

    return render(request, "home.html", {"question": question, "progress": progress, "sparked_ids": sparked_ids})


import math

# ---------------- MATCHING LOGIC ----------------
# ---------------- MATCHING LOGIC ----------------
def calculate_match_score(user1_or_obj, user2_or_obj):
    """Calculate match % between two users based on common answers."""
    # Handle if objects or users are passed
    u1 = user1_or_obj if hasattr(user1_or_obj, 'id') else user1_or_obj.user
    u2 = user2_or_obj if hasattr(user2_or_obj, 'id') else user2_or_obj.user
    
    user1_ans = UserAnswer.objects.filter(user=u1).select_related('option')
    user2_ans = UserAnswer.objects.filter(user=u2).select_related('option')
    
    u1_dict = {ans.question_id: ans.option.weight for ans in user1_ans}
    u2_dict = {ans.question_id: ans.option.weight for ans in user2_ans}
    
    common_questions = set(u1_dict.keys()).intersection(set(u2_dict.keys()))
    if not common_questions: return 0
    
    v1 = [u1_dict[q_id] for q_id in common_questions]
    v2 = [u2_dict[q_id] for q_id in common_questions]
    
    # Blended Score: Cosine Similarity + Euclidean Distance
    euc_dist = math.sqrt(sum((x - y) ** 2 for x, y in zip(v1, v2)))
    euc_sim = 1 / (1 + euc_dist)
    
    dot_product = sum(x * y for x, y in zip(v1, v2))
    norm_v1 = math.sqrt(sum(x * x for x in v1))
    norm_v2 = math.sqrt(sum(x * x for x in v2))
    cos_sim = dot_product / (norm_v1 * norm_v2) if (norm_v1 > 0 and norm_v2 > 0) else 0
    
    final_score = (cos_sim * 0.7) + (euc_sim * 0.3)
    return int(round(final_score * 100))

def calculate_match_score_optimized(u1_dict, u2_dict):
    """Fast version for bulk ranking in discovery feed."""
    common = set(u1_dict.keys()).intersection(set(u2_dict.keys()))
    if not common: return 0
    v1 = [u1_dict[q] for q in common]; v2 = [u2_dict[q] for q in common]
    euc = 1 / (1 + math.sqrt(sum((x-y)**2 for x,y in zip(v1,v2))))
    dot = sum(x*y for x,y in zip(v1,v2)); n1 = math.sqrt(sum(x*x for x in v1)); n2 = math.sqrt(sum(x*x for x in v2))
    cos = dot / (n1*n2) if (n1>0 and n2>0) else 0
    return int(round(((cos*0.7) + (euc*0.3)) * 100))




# ---------------- CHECK MATCH POPUP ----------------
@login_required

def check_match(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    if profile is None:
        return redirect('home')

    # Exclude ANY users where a MatchRequest exists in EITHER direction (liked, rejected, skipped, pending, accepted)
    interacted_user_ids = list(MatchRequest.objects.filter(sender=user).values_list('receiver_id', flat=True)) + \
                          list(MatchRequest.objects.filter(receiver=user).values_list('sender_id', flat=True))

    # Check if we have a current match that hasn't been interacted with (prevents refresh bypass)
    current_match_id = request.session.get('current_match_id')
    if current_match_id and current_match_id not in interacted_user_ids:
        best_match = Profile.objects.filter(user__id=current_match_id, is_discoverable=True).first()
        if best_match:
            score = calculate_match_score(user, best_match.user)
            return render(request, "match_popup.html", {
                "match": best_match,
                "score": score
            })

    # IDs of users already shown to this user in previous rounds (stored in session)
    seen_ids = request.session.get('seen_match_ids', [])
    
    candidates = Profile.objects.filter(is_discoverable=True).exclude(user=user).exclude(user__id__in=interacted_user_ids).exclude(user__id__in=seen_ids)

    preference_filtered = []
    for c in candidates:
        # Gender preference check (both ways)
        user_pref_ok = (profile.pref_gender == 'any' or profile.pref_gender == c.gender)
        cand_pref_ok = (c.pref_gender == 'any' or c.pref_gender == profile.gender)

        # Age range check (both ways)
        user_age_ok = True
        if profile.age:
            user_age_ok = (c.pref_age_min <= profile.age <= c.pref_age_max)
        cand_age_ok = True
        if c.age:
            cand_age_ok = (profile.pref_age_min <= c.age <= profile.pref_age_max)

        if user_pref_ok and user_age_ok: # Relaxed from (user_pref_ok and cand_pref_ok and user_age_ok and cand_age_ok)
            preference_filtered.append(c)

    # ── Step 2: Rank by answer similarity ──
    best_match = None
    best_score = -1

    for candidate in preference_filtered:
        score = calculate_match_score(user, candidate.user)
        
        # Bonus for matching 'looking_for' (Soft priority)
        if profile.looking_for == candidate.looking_for:
            score += 5
        
        # Bonus for matching preferred languages (Soft priority)
        user_pref_langs = set(profile.pref_languages_list)
        cand_langs = set(candidate.languages_list)
        if user_pref_langs.intersection(cand_langs):
            score += 5
            
        score = min(score, 100) # Cap at 100%
        
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_match is not None:
        # Remember we showed this person
        seen_ids.append(best_match.user.id)
        request.session['seen_match_ids'] = seen_ids
        request.session['current_match_id'] = best_match.user.id
        return render(request, "match_popup.html", {
            "match": best_match,
            "score": best_score
        })

    # No one left to show — reset seen list and send back to quiz
    request.session['seen_match_ids'] = []
    request.session['current_match_id'] = None
    return redirect("home")



# ---------------- FIREBASE LOGIN ----------------
def login_view(request):
    if request.user.is_authenticated:
        # Check if profile is set up — if not, send to complete_profile
        profile = getattr(request.user, 'profile', None)
        if profile and profile.name:
            return redirect('home')
        return redirect('complete_profile')
    return render(request, "login.html")

@csrf_exempt
def api_verify_token(request):
    if request.method == 'POST':
        try:
            default_app = get_firebase_app()
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Firebase Init Failure: {str(e)}'}, status=500)

        try:
            data = json.loads(request.body)
            id_token = data.get('idToken')
            
            # Use get_app() to ensure we are using the initialized default app
            default_app = firebase_admin.get_app()
            decoded_token = firebase_auth.verify_id_token(id_token, app=default_app)
            email = decoded_token.get('email', '')
            
            # Get or create user
            user, created = User.objects.get_or_create(username=email, defaults={'email': email})
            
            # Log the user in
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Check if profile is complete
            profile = getattr(user, 'profile', None)
            profile_complete = profile is not None and bool(profile.name)
            
            # Sync round count to avoid immediate check_match popup for existing users
            if profile_complete:
                ans_count = UserAnswer.objects.filter(user=user).count()
                request.session['rounds_shown'] = ans_count // 10
            
            return JsonResponse({
                'success': True,
                'profile_complete': profile_complete
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@csrf_exempt
@login_required
def api_save_fcm_token(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            token = data.get('token')
            device_type = data.get('device_type', 'web')
            
            if not token:
                return JsonResponse({'success': False, 'error': 'Token missing'}, status=400)
            
            # Save or update the token
            FCMToken.objects.update_or_create(
                user=request.user,
                token=token,
                defaults={'device_type': device_type}
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)


def send_push_to_user(user, title, body, url='/'):
    tokens = list(FCMToken.objects.filter(user=user).values_list('token', flat=True))
    if not tokens:
        raise Exception("No push tokens found for this user. Make sure you granted notification permission.")
    
    # Lazy init check
    get_firebase_app()

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data={
            'url': url,
            'title': title,
            'body': body
        },
        tokens=tokens,
        webpush=messaging.WebpushConfig(
            headers={'Urgency': 'high'},
            notification=messaging.WebpushNotification(
                icon='/icon-192x192.png',
                badge='/icon-192x192.png',
                tag='chat-msg',
                renotify=True
            ),
            fcm_options=messaging.WebpushFCMOptions(
                link=url
            )
        )
    )
    try:
        response = messaging.send_multicast(message)
        if response.failure_count > 0:
            # log or handle invalid tokens here
            pass
        return response
    except Exception as e:
        raise Exception(f"FCM Send Error: {str(e)}")


# ---------------- SOCIAL & CONNECTIONS ----------------
@login_required
def send_match_request(request, receiver_id):
    if request.method == 'POST':
        receiver = get_object_or_404(User, id=receiver_id)
        if receiver != request.user:
            req, created = MatchRequest.objects.get_or_create(sender=request.user, receiver=receiver)
            if created:
                messages.success(request, "Connection request sent!")
                broadcast_event(f'chat_{receiver.id}', 'new_connection', {
                    'sender_id': request.user.id,
                    'sender_name': request.user.profile.name if hasattr(request.user, 'profile') else request.user.username
                })
            else:
                messages.info(request, "Connection request already sent.")
        
        # Reset last_match_count so they can continue answering
    
    return redirect('home')
    
@login_required
def skip_match(request, receiver_id):
    if request.method == 'POST':
        receiver = get_object_or_404(User, id=receiver_id)
        if receiver != request.user:
            MatchRequest.objects.get_or_create(
                sender=request.user, 
                receiver=receiver, 
                defaults={'status': 'skipped'}
            )
    return redirect('home')

@login_required
def accept_match(request, req_id):
    req = get_object_or_404(MatchRequest, id=req_id, receiver=request.user)
    req.status = 'accepted'
    req.save()
    return redirect('connections')

@login_required
def reject_match(request, req_id):
    req = get_object_or_404(MatchRequest, id=req_id, receiver=request.user)
    req.status = 'rejected'
    req.save()
    return redirect('connections')

@login_required
def connections_view(request):
    incoming_requests = MatchRequest.objects.filter(receiver=request.user, status='pending').select_related('sender__profile')
    # Accepted matches can be either sent or received
    accepted_sent = MatchRequest.objects.filter(sender=request.user, status='accepted').select_related('receiver__profile')
    accepted_received = MatchRequest.objects.filter(receiver=request.user, status='accepted').select_related('sender__profile')
    
    connections = []
    for req in accepted_sent:
        connections.append(req.receiver)
    for req in accepted_received:
        connections.append(req.sender)
        
    return render(request, 'connections.html', {
        'incoming_requests': incoming_requests,
        'connections': connections
    })

# ---------------- CHAT INBOX ----------------
from django.views.decorators.cache import never_cache

@never_cache
@login_required
def chat_list_view(request):
    user = request.user
    
    # Get all active connections with pre-fetched profiles
    accepted_sent = MatchRequest.objects.filter(sender=user, status='accepted').select_related('receiver__profile')
    accepted_received = MatchRequest.objects.filter(receiver=user, status='accepted').select_related('sender__profile')
    
    blocked_ids = set(BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)) | \
                  set(BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True))
    
    partners = []
    for req in accepted_sent:
        if req.receiver_id not in blocked_ids: partners.append(req.receiver)
    for req in accepted_received:
        if req.sender_id not in blocked_ids: partners.append(req.sender)
    
    if not partners:
        return render(request, 'chat_list.html', {'chats': []})

    # Fetch all recent messages involving these partners in one query
    all_msgs = Message.objects.filter(
        (Q(sender=user, receiver__in=partners, sender_deleted=False)) |
        (Q(sender__in=partners, receiver=user, receiver_deleted=False))
    ).exclude(text__startswith='__SPIN__:').order_by('-timestamp').select_related('sender')

    # Group latest messages and unread counts in memory
    latest_msg_map = {}
    unread_map = {}
    for msg in all_msgs:
        partner_id = msg.sender_id if msg.receiver_id == user.id else msg.receiver_id
        if partner_id not in latest_msg_map:
            latest_msg_map[partner_id] = msg
        if msg.receiver_id == user.id and not msg.is_read and not msg.receiver_deleted:
            unread_map[partner_id] = unread_map.get(partner_id, 0) + 1

    chats = []
    for partner in partners:
        latest = latest_msg_map.get(partner.id)
        if latest:
            chats.append({
                'partner': partner,
                'latest_message': latest,
                'unread_count': unread_map.get(partner.id, 0),
                'timestamp': latest.timestamp
            })
    
    chats.sort(key=lambda x: x['timestamp'].timestamp() if x.get('timestamp') else 0, reverse=True)
    return render(request, 'chat_list.html', {
        'chats': chats,
        'today': timezone.localtime(timezone.now()).date()
    })


# ---------------- CHAT ----------------
@login_required
def chat_view(request, partner_id):
    partner = get_object_or_404(User, id=partner_id)
    
    # Verify they are actually connected
    is_connected = MatchRequest.objects.filter(
        Q(sender=request.user, receiver=partner, status='accepted') |
        Q(sender=partner, receiver=request.user, status='accepted')
    ).exists()
    
    if not is_connected:
        return redirect('connections')
        
    if request.method == 'POST':
        is_ajax = request.headers.get('Content-Type') == 'application/json'
        
        if is_ajax:
            import json
            try:
                data = json.loads(request.body)
                text = data.get('text')
                parent_id = data.get('parent_id')
            except json.JSONDecodeError:
                text = None
                parent_id = None
        else:
            text = request.POST.get('text')
            parent_id = request.POST.get('parent_id')
            
        if text:
            reply_to_msg = None
            if parent_id:
                reply_to_msg = Message.objects.filter(id=parent_id).first()
                
            msg = Message.objects.create(sender=request.user, receiver=partner, text=text, reply_to=reply_to_msg)
            # Broadcast to Pusher
            broadcast_event(f'chat_{partner.id}', 'new_message', {
                'id': msg.id,
                'text': msg.text,
                'sender_id': msg.sender_id,
                'timestamp': timezone.localtime(msg.timestamp).strftime("%I:%M %p"),
                'reply_to': {
                    'id': msg.reply_to.id,
                    'text': msg.reply_to.text,
                    'sender_name': msg.reply_to.sender.profile.name if hasattr(msg.reply_to.sender, 'profile') else msg.reply_to.sender.username
                } if msg.reply_to else None
            })

            # Send Push Notification
            try:
                sender_name = request.user.profile.name if hasattr(request.user, 'profile') else request.user.username
                send_push_to_user(
                    partner, 
                    title=f"New message from {sender_name}", 
                    body=text[:100] + ("..." if len(text) > 100 else ""),
                    url=f"/chat/{request.user.id}/"
                )
            except Exception as e:
                print(f"Push Error: {e}")

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': {
                        'id': msg.id,
                        'text': msg.text,
                        'sender_id': msg.sender_id,
                        'timestamp': timezone.localtime(msg.timestamp).strftime("%I:%M %p"),
                        'reply_to': {
                            'id': msg.reply_to.id,
                            'text': msg.reply_to.text,
                            'sender_name': msg.reply_to.sender.profile.name if hasattr(msg.reply_to.sender, 'profile') else msg.reply_to.sender.username
                        } if msg.reply_to else None
                    }
                })
            return redirect('chat_view', partner_id=partner.id)
            
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Empty message'}, status=400)
            
    chat_messages = Message.objects.filter(
        (Q(sender=request.user, receiver=partner, sender_deleted=False)) |
        (Q(sender=partner, receiver=request.user, receiver_deleted=False))
    ).exclude(text__startswith='__SPIN__:') .order_by('timestamp')
    
    # Mark messages as read
    Message.objects.filter(sender=partner, receiver=request.user, is_read=False).update(is_read=True)
    
    # Spark status
    has_sparked = Spark.objects.filter(sender=request.user, receiver=partner).exists()
    
    return render(request, "chat.html", {
        "partner": partner,
        "chat_messages": chat_messages,
        "has_sparked": has_sparked,
        'PUSHER_KEY': settings.PUSHER_KEY,
        'PUSHER_CLUSTER': settings.PUSHER_CLUSTER
    })

@csrf_exempt
@login_required
def chat_typing(request, partner_id):
    broadcast_event(f'chat_{request.user.id}', 'typing', {'user_id': request.user.id})
    return JsonResponse({'success': True})
@csrf_exempt
@login_required
def mark_messages_read(request, partner_id):
    if request.method == 'POST':
        partner = get_object_or_404(User, id=partner_id)
        Message.objects.filter(sender=partner, receiver=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


@login_required
def chat_api_messages(request, partner_id):
    partner = get_object_or_404(User, id=partner_id)
    
    # Optional security check to ensure they are connected
    is_connected = MatchRequest.objects.filter(
        Q(sender=request.user, receiver=partner, status='accepted') |
        Q(sender=partner, receiver=request.user, status='accepted')
    ).exists()
    
    if not is_connected:
        return JsonResponse({'error': 'Not connected'}, status=403)
        
    from django.utils import timezone
    from datetime import timedelta
    recent_cutoff = timezone.now() - timedelta(seconds=15)

    messages = Message.objects.filter(
        (Q(sender=request.user, receiver=partner, sender_deleted=False)) |
        (Q(sender=partner, receiver=request.user, receiver_deleted=False))
    ).exclude(
        Q(text__startswith='__SPIN__:') & Q(timestamp__lt=recent_cutoff)
    ).order_by('timestamp')
    
    # Mark incoming unread messages as read
    Message.objects.filter(sender=partner, receiver=request.user, is_read=False).update(is_read=True)
    
    msg_list = []
    for msg in messages:
        msg_list.append({
            'id': msg.id,
            'text': msg.text,
            'sender_id': msg.sender_id,
            'timestamp': timezone.localtime(msg.timestamp).strftime("%I:%M %p"),
            'reply_to': {
                'id': msg.reply_to.id,
                'text': msg.reply_to.text,
                'sender_name': msg.reply_to.sender.profile.name if hasattr(msg.reply_to.sender, 'profile') else msg.reply_to.sender.username
            } if msg.reply_to else None
        })
        
    return JsonResponse({'messages': msg_list})

# ---------------- PROFILE MANAGEMENT ----------------

@login_required
def view_profile(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(Profile, user=target_user)
    
    # Matching logic (simplified)
    my_profile = request.user.profile
    score = 0
    if my_profile.campus == profile.campus: score += 20
    
    # Spark logic
    spark_count = Spark.objects.filter(receiver=target_user).count()
    has_sparked = Spark.objects.filter(sender=request.user, receiver=target_user).exists()
    
    # Gallery
    gallery = profile.images.all()
    
    return render(request, "view_profile.html", {
        "profile": profile,
        "score": score,
        "spark_count": spark_count,
        "has_sparked": has_sparked,
        "gallery": gallery
    })

@login_required
def block_user(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user != request.user:
        BlockedUser.objects.get_or_create(blocker=request.user, blocked=target_user)
        # Also remove any match requests
        MatchRequest.objects.filter(
            (Q(sender=request.user) & Q(receiver=target_user)) |
            (Q(sender=target_user) & Q(receiver=request.user))
        ).delete()
        messages.success(request, f"You have blocked {target_user.username}.")
    return redirect('home')

@login_required
def delete_chat(request, partner_id):
    partner = get_object_or_404(User, id=partner_id)
    # Soft delete for the current user
    # If I am the sender, set sender_deleted = True
    # If I am the receiver, set receiver_deleted = True
    Message.objects.filter(sender=request.user, receiver=partner).update(sender_deleted=True)
    Message.objects.filter(sender=partner, receiver=request.user).update(receiver_deleted=True)
    
    messages.success(request, "Chat cleared for you.")
    return redirect('chat_list')
@login_required
def toggle_spark(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        return JsonResponse({'success': False, 'error': 'Cannot spark yourself'})
        
    spark_qs = Spark.objects.filter(sender=request.user, receiver=target_user)
    if spark_qs.exists():
        spark_qs.delete()
        action = 'removed'
    else:
        Spark.objects.create(sender=request.user, receiver=target_user)
        action = 'added'
        
    new_count = Spark.objects.filter(receiver=target_user).count()
    return JsonResponse({'success': True, 'action': action, 'new_count': new_count})

@login_required
@csrf_exempt
def toggle_discoverable(request):
    profile = request.user.profile
    profile.is_discoverable = not profile.is_discoverable
    profile.save()
    return JsonResponse({'success': True, 'is_discoverable': profile.is_discoverable})

@login_required
def edit_profile(request):
    profile = get_object_or_404(Profile, user=request.user)
    
    if request.method == "POST":
        # Handle Profile Info Update
        if 'update_profile' in request.POST:
            form = ProfileEditForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                updated_profile = form.save(commit=False)
                
                # Handle Supabase Upload
                if 'profile_pic_file' in request.FILES:
                    submitted_pfp = request.FILES['profile_pic_file']
                    img_url = upload_to_supabase(submitted_pfp, bucket="images", path="profile_pics")
                    if img_url:
                        updated_profile.profile_pic = img_url
                        messages.success(request, "Profile picture updated successfully!")
                    else:
                        messages.error(request, "Failed to upload profile picture to Supabase.")
                
                # The form already handles clg_year, course, branch, etc.
                # but we explicitly save the tag fields to ensure they match our new JS dropdowns
                # Specialized handling for tag-like fields to ensure clean data
                for field in ['languages', 'mother_tongues', 'interest_tags', 'pref_languages']:
                    if field in request.POST:
                        val = request.POST.get(field, '').strip()
                        
                        # CLEANUP: Strip brackets and quotes if they exist
                        if val.startswith('[') and val.endswith(']'):
                            val = val[1:-1].replace("'", "").replace('"', "")
                        
                        # MOTHER TONGUE LOCK: Only allow saving if currently empty
                        if field == 'mother_tongues':
                            current_val = getattr(profile, 'mother_tongues', '')
                            if not current_val:
                                setattr(updated_profile, field, val)
                            else:
                                # Keep the old value
                                setattr(updated_profile, field, current_val)
                        else:
                            setattr(updated_profile, field, val)

                updated_profile.save()
                messages.success(request, "Profile updated successfully!")
                return redirect('edit_profile')
            else:
                print(f"DEBUG: form.is_valid() is FALSE. Errors: {form.errors}")
                messages.error(request, f"Form validation failed: {form.errors.as_text()}")
        
        # Handle Instant PFP Upload
        elif 'update_pfp_instant' in request.POST:
            if 'profile_pic_file' in request.FILES:
                img_url = upload_to_supabase(request.FILES['profile_pic_file'], bucket="images", path="profile_pics")
                if img_url:
                    profile.profile_pic = img_url
                    profile.save()
                    messages.success(request, "Profile picture updated successfully!")
                else:
                    messages.error(request, "Failed to upload profile picture.")
            return redirect('edit_profile')
        
        # Handle Image Upload
        elif 'add_image' in request.POST:
            if profile.images.count() >= 5:
                return redirect('edit_profile')
            
            image_form = ProfileImageForm(request.POST, request.FILES)
            if image_form.is_valid():
                # Handle Supabase Upload for gallery
                if 'image_file' in request.FILES:
                    img_url = upload_to_supabase(request.FILES['image_file'], bucket="images", path="gallery")
                    if img_url:
                        ProfileImage.objects.create(profile=profile, image=img_url)
                        messages.success(request, "Gallery photo added successfully!")
                    else:
                        messages.error(request, "Failed to upload gallery image. Please check your credentials.")
                return redirect('edit_profile')

    form = ProfileEditForm(instance=profile)
    image_form = ProfileImageForm()
    gallery = profile.images.all()
    spark_count = Spark.objects.filter(receiver=request.user).count()

    return render(request, "edit_profile.html", {
        "form": form,
        "image_form": image_form,
        "gallery": gallery,
        "profile": profile,
        "spark_count": spark_count
    })

@login_required
def delete_profile_image(request, image_id):
    image = get_object_or_404(ProfileImage, id=image_id, profile__user=request.user)
    profile = image.profile
    gallery_count = profile.images.count()

    if gallery_count <= 2:
        messages.error(request, "You must keep at least 2 images in your gallery.")
        return redirect('edit_profile')

    image.delete()
    messages.success(request, "Photo removed.")
    return redirect('edit_profile')

# ---------------- UTILS ----------------

def run_migrations(request):
    """Temporary view to run migrations on Vercel"""
    try:
        call_command('migrate')
        return HttpResponse("Migrations applied successfully!")
    except Exception as e:
        return HttpResponse(f"Migration error: {str(e)}")


# ---------------- ANONYMOUS WALL ----------------

def wall_view(request):
    return render(request, 'wall.html', {
        'PUSHER_KEY': settings.PUSHER_KEY,
        'PUSHER_CLUSTER': settings.PUSHER_CLUSTER
    })


from .pusher_utils import broadcast_event

@csrf_exempt
def wall_api(request):
    if request.method == 'GET':
        strokes = list(WallStroke.objects.all().values('id', 'points', 'color', 'brush_size'))
        images = list(WallImage.objects.all().values('id', 'image_url', 'x', 'y', 'width', 'height'))
        return JsonResponse({'strokes': strokes, 'images': images})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            if 'image_url' in data:
                # Handle image upload (Admin only check in frontend, but could add here too)
                if not request.user.is_superuser and request.user.email != 'arunmohankml@gmail.com':
                    return JsonResponse({'error': 'Unauthorized'}, status=403)
                    
                obj = WallImage.objects.create(
                    image_url=data['image_url'],
                    x=data['x'],
                    y=data['y'],
                    width=data['width'],
                    height=data['height']
                )
                event_type = 'new_image'
                payload = {
                    'id': obj.id,
                    'image_url': obj.image_url,
                    'x': obj.x,
                    'y': obj.y,
                    'width': obj.width,
                    'height': obj.height
                }
            else:
                # Handle stroke
                obj = WallStroke.objects.create(
                    points=data['points'],
                    color=data['color'],
                    brush_size=data['brush_size']
                )
                event_type = 'new_stroke'
                payload = {
                    'id': obj.id,
                    'points': obj.points,
                    'color': obj.color,
                    'brush_size': obj.brush_size
                }

            # Broadcast to Pusher
            from .pusher_utils import broadcast_event
            broadcast_event('wall', event_type, payload)
            return JsonResponse({'success': True, 'id': obj.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


# ---------------- CONFESSIONS ----------------

def confessions_feed(request):
    sort_by = request.GET.get('sort', 'latest')
    campus_filter = request.GET.get('campus', '')

    is_admin = request.user.is_authenticated and request.user.email == 'arunmohankml@gmail.com'

    if is_admin:
        # Admins see everything
        confessions = Confession.objects.all().select_related('user__profile')
    else:
        # Public feed: only approved confessions
        confessions = Confession.objects.filter(
            moderation_status='approved'
        ).select_related('user__profile')

    if campus_filter:
        confessions = confessions.filter(campus__iexact=campus_filter)

    if sort_by == 'top':
        confessions = confessions.order_by('-likes_count', '-created_at')
    else:
        confessions = confessions.order_by('-created_at')

    return render(request, 'confessions.html', {
        'confessions': confessions,
        'current_sort': sort_by,
        'current_campus': campus_filter,
        'is_admin': is_admin
    })

def create_confession(request):
    if request.method != 'POST':
        return redirect('confessions_feed')

    from .moderation import (
        check_bad_words, check_duplicate, check_name_mention,
        check_rate_limit, record_rate_limit, check_shadow_ban
    )

    content    = request.POST.get('content', '').strip()
    is_anon    = request.POST.get('is_anonymous') == 'true'
    campus     = request.POST.get('campus', '')
    fingerprint = request.POST.get('fingerprint', '').strip()
    ip = (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
          or request.META.get('REMOTE_ADDR', ''))

    if not content:
        messages.error(request, 'Confession cannot be empty.')
        return redirect('confessions_feed')

    # ── 1. Hard ban check ──
    if fingerprint and BannedIdentifier.objects.filter(
        fingerprint=fingerprint, is_shadow_ban=False
    ).exists():
        messages.error(request, 'You are banned from posting.')
        return redirect('confessions_feed')

    user = None
    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile.is_banned:
            messages.error(request, 'You are banned.')
            return redirect('confessions_feed')
        user = request.user

    # ── 2. Rate limit ──
    allowed, wait = check_rate_limit(fingerprint, ip)
    if not allowed:
        mins = max(1, wait // 60)
        messages.warning(
            request,
            f"You\'re posting too fast. Please try again in about {mins} minute(s)."
        )
        return redirect('confessions_feed')

    # ── 3. Shadow ban (silent — let them think it posted) ──
    is_shadow = check_shadow_ban(fingerprint)

    # ── 4. Bad word filter ──
    bad, word = check_bad_words(content)
    if bad:
        record_rate_limit(fingerprint, ip)  # still counts toward rate limit
        Confession.objects.create(
            user=user, content=content, campus=campus,
            is_anonymous=is_anon, poster_fingerprint=fingerprint,
            moderation_status='rejected',
            moderation_reason=f'bad_word:{word}'
        )
        messages.error(
            request,
            'Your confession was rejected because it violates community rules.'
        )
        return redirect('confessions_feed')

    # ── 5. Duplicate / near-duplicate ──
    if check_duplicate(content, fingerprint, user):
        messages.warning(
            request,
            'Duplicate confession detected. Please don\'t spam.'
        )
        return redirect('confessions_feed')

    # ── 6. Name mention → pending review ──
    if check_name_mention(content):
        record_rate_limit(fingerprint, ip)
        Confession.objects.create(
            user=user, content=content, campus=campus,
            is_anonymous=is_anon, poster_fingerprint=fingerprint,
            moderation_status='pending_review',
            moderation_reason='name_mention'
        )
        messages.info(
            request,
            'Your confession has been sent for admin approval because it may mention a person.'
        )
        return redirect('confessions_feed')

    # ── 7. Shadow ban → store but never show ──
    if is_shadow:
        record_rate_limit(fingerprint, ip)
        Confession.objects.create(
            user=user, content=content, campus=campus,
            is_anonymous=is_anon, poster_fingerprint=fingerprint,
            moderation_status='rejected',
            moderation_reason='shadow_ban'
        )
        # Deliberately show success to avoid tipping off the spammer
        messages.success(request, 'Confession posted! \u2728')
        return redirect('confessions_feed')

    # ── 8. All clear → approve ──
    record_rate_limit(fingerprint, ip)
    Confession.objects.create(
        user=user, content=content, campus=campus,
        is_anonymous=is_anon, poster_fingerprint=fingerprint,
        moderation_status='approved',
        moderation_reason=''
    )
    messages.success(request, 'Confession posted! \u2728')
    return redirect('confessions_feed')

@login_required
def edit_confession(request, confession_id):
    confession = get_object_or_404(Confession, id=confession_id)
    if confession.user != request.user:
        messages.error(request, "Not authorized.")
        return redirect('confession_detail', confession_id=confession_id)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            confession.content = content
            confession.save()
            messages.success(request, "Updated!")
        return redirect('confession_detail', confession_id=confession_id)
    
    return render(request, 'edit_confession.html', {'confession': confession})

@login_required
def delete_confession(request, confession_id):
    confession = get_object_or_404(Confession, id=confession_id)
    is_admin = request.user.email == 'arunmohankml@gmail.com'
    
    if confession.user == request.user or is_admin:
        confession.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, "Confession deleted.")
        return redirect('confessions_feed')
    
    messages.error(request, "Not authorized.")
    return redirect('confession_detail', confession_id=confession_id)

def report_confession(request, confession_id):
    confession = get_object_or_404(Confession, id=confession_id)
    if request.method == 'POST':
        reasons = request.POST.getlist('reasons')
        other_reason = request.POST.get('other_reason', '')
        fingerprint = request.POST.get('fingerprint', '')

        # Use update_or_create logic based on user or fingerprint
        if request.user.is_authenticated:
            ConfessionReport.objects.update_or_create(
                confession=confession,
                user=request.user,
                defaults={
                    'reasons': reasons,
                    'other_reason': other_reason,
                    'reporter_fingerprint': fingerprint
                }
            )
        else:
            # For anonymous reports, we just create a new one each time or try to match fingerprint
            # but fingerprint might not be unique enough for update_or_create without user.
            ConfessionReport.objects.create(
                confession=confession,
                reporter_fingerprint=fingerprint,
                reasons=reasons,
                other_reason=other_reason
            )

        confession.is_flagged = True
        confession.save()
        messages.success(request, "Report submitted.")
    return redirect('confession_detail', confession_id=confession_id)

@login_required
def report_user(request, user_id):
    reported_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        reasons = request.POST.getlist('reasons')
        other_reason = request.POST.get('other_reason', '')
        
        # Get recent chat history between these two users
        messages_qs = Message.objects.filter(
            (Q(sender=request.user) & Q(receiver=reported_user)) |
            (Q(sender=reported_user) & Q(receiver=request.user))
        ).order_by('-timestamp')[:50]
        
        chat_snapshot = []
        for m in messages_qs:
            chat_snapshot.append({
                'sender': m.sender.username,
                'content': m.text,
                'time': m.timestamp.strftime("%Y-%m-%d %H:%M")
            })
            
        UserReport.objects.create(
            reported_user=reported_user,
            reporter=request.user,
            reasons=reasons,
            other_reason=other_reason,
            chat_snapshot=chat_snapshot
        )
        messages.success(request, f"Reported {reported_user.username}. We will review the chat logs.")
    return redirect('chat_view', partner_id=user_id)

def confession_detail(request, confession_id):
    confession = get_object_or_404(Confession, id=confession_id)
    return render(request, 'confession_detail.html', {'confession': confession})

def add_comment(request, confession_id):
    if request.method == 'POST':
        confession = get_object_or_404(Confession, id=confession_id)
        content = request.POST.get('content')
        is_anonymous = request.POST.get('is_anonymous') == 'true'
        fingerprint = request.POST.get('fingerprint', '')

        # Check if fingerprint is banned
        if fingerprint and BannedIdentifier.objects.filter(fingerprint=fingerprint).exists():
            messages.error(request, "You are banned from commenting.")
            return redirect('confession_detail', confession_id=confession_id)
        
        user = None
        if request.user.is_authenticated:
            if hasattr(request.user, 'profile') and request.user.profile.is_banned:
                messages.error(request, "You are banned.")
                return redirect('confession_detail', confession_id=confession_id)
            user = request.user

        if content:
            ConfessionComment.objects.create(
                confession=confession,
                user=user,
                content=content,
                is_anonymous=is_anonymous,
                poster_fingerprint=fingerprint
            )
    return redirect('confession_detail', confession_id=confession_id)

@csrf_exempt
def like_confession(request, confession_id):
    if request.method == 'POST':
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        
        confession = get_object_or_404(Confession, id=confession_id)
        like, created = ConfessionLike.objects.get_or_create(
            confession=confession,
            session_key=session_key
        )
        
        if created:
            confession.likes_count += 1
            confession.save()
            return JsonResponse({'success': True, 'likes_count': confession.likes_count})
        else:
            return JsonResponse({'success': False, 'error': 'Already liked'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


# ---------------- ANSWER QUESTION ----------------
@login_required
def answer_question(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    if request.method == "POST":
        option_id = request.POST.get("option")
        if option_id:
            option = get_object_or_404(Option, id=option_id)
            UserAnswer.objects.update_or_create(
                user=request.user,
                question=question,
                defaults={"option": option},
            )
        return redirect('home')
    return redirect('home')


# ---------------- FAST QUIZ API ----------------

@login_required
def get_quiz_batch(request):
    """Returns 10 unanswered questions for the Fast Fire quiz."""
    answered_ids = UserAnswer.objects.filter(user=request.user).values_list('question_id', flat=True)
    questions = Question.objects.exclude(id__in=answered_ids)[:10]
    
    data = []
    for q in questions:
        options = []
        for opt in q.options.all():
            options.append({'id': opt.id, 'text': opt.text})
        data.append({
            'id': q.id,
            'text': q.text,
            'options': options
        })
    
    return JsonResponse({'questions': data})

@csrf_exempt
@login_required
def save_quiz_batch(request):
    """Saves a batch of answers and triggers match recalculation."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            answers = data.get('answers', [])
            
            for ans in answers:
                question_id = ans.get('question_id')
                option_id = ans.get('option_id')
                if question_id and option_id:
                    question = get_object_or_404(Question, id=question_id)
                    option = get_object_or_404(Option, id=option_id)
                    UserAnswer.objects.get_or_create(
                        user=request.user,
                        question=question,
                        defaults={'option': option}
                    )
            
            # Reset rounds_shown to trigger 'check_match' redirect on next home load
            ans_count = UserAnswer.objects.filter(user=request.user).count()
            request.session['rounds_shown'] = (ans_count // 10) - 1
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=405)


# ---------------- ADMIN MENU ----------------

def is_admin_check(user):
    return user.is_authenticated and user.email == 'arunmohankml@gmail.com'

@login_required
def admin_view_user(request, user_id):
    if not is_admin_check(request.user):
        return HttpResponse("Not authorized", status=403)

    target_user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(Profile, user=target_user)

    # All related data
    gallery_images = ProfileImage.objects.filter(profile=profile)
    match_requests_sent = MatchRequest.objects.filter(sender=target_user).select_related('receiver__profile')
    match_requests_received = MatchRequest.objects.filter(receiver=target_user).select_related('sender__profile')
    messages_sent = Message.objects.filter(sender=target_user).order_by('-timestamp')[:50]
    messages_received = Message.objects.filter(receiver=target_user).order_by('-timestamp')[:50]
    confessions = Confession.objects.filter(user=target_user).order_by('-created_at')
    reports_made = UserReport.objects.filter(reporter=target_user).select_related('reported_user')
    reports_received = UserReport.objects.filter(reported_user=target_user).select_related('reporter')
    answers = UserAnswer.objects.filter(user=target_user).select_related('question', 'option')
    fav_movies = FavoriteMovie.objects.filter(user=target_user)
    fav_songs = FavoriteSong.objects.filter(user=target_user)
    connections = MatchRequest.objects.filter(
        Q(sender=target_user, status='accepted') | Q(receiver=target_user, status='accepted')
    ).select_related('sender__profile', 'receiver__profile')

    return render(request, 'admin_user_view.html', {
        'u': target_user,
        'p': profile,
        'gallery': gallery_images,
        'sent_requests': match_requests_sent,
        'received_requests': match_requests_received,
        'messages_sent': messages_sent,
        'messages_received': messages_received,
        'confessions': confessions,
        'reports_made': reports_made,
        'reports_received': reports_received,
        'answers': answers,
        'fav_movies': fav_movies,
        'fav_songs': fav_songs,
        'connections': connections,
    })

@login_required
def admin_dashboard(request):
    if not is_admin_check(request.user):
        return HttpResponse("Not authorized", status=403)

    reported_confessions = Confession.objects.filter(
        is_flagged=True
    ).exclude(moderation_status='rejected').order_by('-created_at')

    pending_confessions = Confession.objects.filter(
        moderation_status='pending_review'
    ).order_by('-created_at')

    user_reports  = UserReport.objects.all().order_by('-created_at')
    all_users     = Profile.objects.all().select_related('user').order_by('-created_at')
    face_reviews  = Profile.objects.filter(
        verification_status='manual_review'
    ).select_related('user').order_by('-updated_at')
    banned_identifiers = BannedIdentifier.objects.all().order_by('-created_at')[:50]

    return render(request, 'admin_dashboard.html', {
        'reported_confessions':  reported_confessions,
        'pending_confessions':   pending_confessions,
        'user_reports':          user_reports,
        'all_users':             all_users,
        'face_reviews':          face_reviews,
        'banned_identifiers':    banned_identifiers,
    })

@login_required
def admin_action(request):
    if not is_admin_check(request.user):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        action    = request.POST.get('action')
        target_id = request.POST.get('target_id')

        if action == 'delete_confession':
            Confession.objects.filter(id=target_id).delete()

        elif action == 'approve_confession':
            Confession.objects.filter(id=target_id).update(
                moderation_status='approved', is_flagged=False
            )

        elif action == 'reject_confession':
            Confession.objects.filter(id=target_id).update(
                moderation_status='rejected'
            )

        elif action == 'dismiss_confession':
            Confession.objects.filter(id=target_id).update(is_flagged=False)
            ConfessionReport.objects.filter(confession_id=target_id).delete()

        elif action == 'delete_user_report':
            UserReport.objects.filter(id=target_id).delete()

        elif action == 'clear_wall':
            wall_images = WallImage.objects.all()
            for img in wall_images:
                if img.image:
                    delete_from_supabase_by_url(img.image, bucket="images")
            WallStroke.objects.all().delete()
            WallImage.objects.all().delete()

        elif action == 'ban_user':
            profile = get_object_or_404(Profile, id=target_id)
            profile.is_banned = True
            profile.save()

        elif action == 'unban_user':
            profile = get_object_or_404(Profile, id=target_id)
            profile.is_banned = False
            profile.save()

        elif action == 'delete_user':
            profile = get_object_or_404(Profile, id=target_id)
            profile.user.delete()

        elif action == 'approve_face':
            profile = get_object_or_404(Profile, id=target_id)
            profile.verification_status = 'verified'
            profile.is_face_verified = True
            profile.save()

        elif action == 'reject_face':
            profile = get_object_or_404(Profile, id=target_id)
            profile.verification_status = 'rejected'
            profile.is_face_verified = False
            profile.save()

        elif action == 'ban_fingerprint':
            # Hard ban — blocks site access entirely
            fingerprint = request.POST.get('fingerprint', '').strip()
            reason      = request.POST.get('reason', 'Admin ban').strip()
            if fingerprint:
                BannedIdentifier.objects.update_or_create(
                    fingerprint=fingerprint,
                    defaults={'is_shadow_ban': False, 'reason': reason}
                )

        elif action == 'shadow_ban_fingerprint':
            # Shadow ban — posts silently disappear
            fingerprint = request.POST.get('fingerprint', '').strip()
            reason      = request.POST.get('reason', 'Shadow ban').strip()
            if fingerprint:
                BannedIdentifier.objects.update_or_create(
                    fingerprint=fingerprint,
                    defaults={'is_shadow_ban': True, 'reason': reason}
                )

        elif action == 'unban_fingerprint':
            fingerprint = request.POST.get('fingerprint', '').strip()
            if fingerprint:
                BannedIdentifier.objects.filter(fingerprint=fingerprint).delete()

        return redirect('admin_dashboard')

    return redirect('admin_dashboard')
@login_required
def announcements_view(request):
    is_admin = is_admin_check(request.user)
    
    if request.method == 'POST' and is_admin:
        text = request.POST.get('text')
        if text:
            Announcement.objects.create(text=text)
            messages.success(request, "Announcement posted successfully!")
            return redirect('announcements')
            
    announcements = Announcement.objects.all()
    return render(request, 'announcements.html', {
        'announcements': announcements,
        'is_admin': is_admin
    })

@login_required
def settings_view(request):
    return render(request, 'settings.html')

@csrf_exempt
@login_required
def test_push(request):
    if request.method == 'POST':
        try:
            send_push_to_user(
                request.user, 
                title="Test Notification ✅", 
                body="If you see this, push notifications are working perfectly!",
                url="/settings/"
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required
def delete_account(request):
    if request.method == 'POST':
        # Get the user to delete
        user_to_delete = request.user
        
        # Log out the user before deleting to clear session
        from django.contrib.auth import logout
        logout(request)
        
        # Delete the user. This will cascade and delete their profile, chats, confessions etc.
        user_to_delete.delete()
        
        # Add a success message
        messages.success(request, "Your account has been successfully deleted.")
        return redirect('login')
        
    return redirect('settings')

# ---------------- FAVORITES API ----------------

import requests
from django.conf import settings

@login_required
def search_movies(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})
        
    api_key = getattr(settings, 'TMDB_API_KEY', None)
    if not api_key:
        return JsonResponse({'error': 'TMDb API key not configured'}, status=500)
        
    url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}&include_adult=false&language=en-US&page=1"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get('results', [])[:10]: # Return top 10
                poster_path = item.get('poster_path')
                poster_url = f"https://image.tmdb.org/t/p/w200{poster_path}" if poster_path else None
                release_date = item.get('release_date', '')
                release_year = release_date.split('-')[0] if release_date else ''
                
                results.append({
                    'id': item.get('id'),
                    'title': item.get('title'),
                    'poster_url': poster_url,
                    'release_year': release_year
                })
            return JsonResponse({'results': results})
        else:
            return JsonResponse({'error': 'TMDb API error'}, status=response.status_code)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def upload_base64_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=405)
    
    try:
        data = json.loads(request.body)
        base64_str = data.get('image')
        path = data.get('path', 'temp')
        bucket = data.get('bucket', 'images')
        
        if not base64_str:
            return JsonResponse({'success': False, 'message': 'Missing image data'}, status=400)
            
        from .supabase_utils import upload_base64_to_supabase
        import os
        
        has_url = bool(os.environ.get('SUPABASE_URL'))
        has_key = bool(os.environ.get('SUPABASE_KEY'))
        
        url, error_msg = upload_base64_to_supabase(base64_str, bucket=bucket, path=path)
        
        if url:
            return JsonResponse({'success': True, 'url': url})
        else:
            return JsonResponse({'success': False, 'message': f'Upload failed: {error_msg}. Diagnostic: URL Set={has_url}, KEY Set={has_key}'}, status=500)
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def save_favorites(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            movies = data.get('movies', [])
            songs = data.get('songs', [])
            
            if len(movies) > 3 or len(songs) > 3:
                return JsonResponse({'success': False, 'error': 'Maximum 3 items allowed per category'}, status=400)
                
            # Update Movies
            FavoriteMovie.objects.filter(user=request.user).delete()
            for m in movies:
                FavoriteMovie.objects.create(
                    user=request.user,
                    tmdb_id=m.get('id'),
                    title=m.get('title')[:255],
                    poster_url=m.get('poster_url'),
                    release_year=m.get('release_year', '')[:10]
                )
                
            # Update Songs
            FavoriteSong.objects.filter(user=request.user).delete()
            for s in songs:
                FavoriteSong.objects.create(
                    user=request.user,
                    itunes_track_id=str(s.get('id'))[:100],
                    title=s.get('title')[:255],
                    artist=s.get('artist')[:255],
                    album=s.get('album', '')[:255],
                    artwork_url=s.get('artwork_url')
                )
                
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode('ascii', 'ignore').decode('ascii'))
        except:
            pass

