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
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.core.files.base import ContentFile
import base64
import math

from .models import Profile, UserVerification, Question, Option, UserAnswer, MatchRequest, Message, ProfileImage, WallStroke, Confession, ConfessionComment, ConfessionLike, ConfessionReport, UserReport, Spark, BlockedUser, Announcement, FavoriteMovie, FavoriteSong
from .forms import ProfileForm, ProfileEditForm, ProfileImageForm
from .supabase_utils import upload_to_supabase
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
            
            # Sync from UserVerification
            uv = getattr(user, 'verification', None)
            
            if 'profile_pic_file' in request.FILES:
                if not uv or not uv.image_front:
                    messages.error(request, "Please complete face verification first.")
                    return render(request, 'complete_profile.html', {'form': form})
                
                img_url = upload_to_supabase(request.FILES['profile_pic_file'], bucket="images", path="profile_pics")
                if img_url:
                    baselines = [uv.image_front, uv.image_left, uv.image_right]
                    baselines = [b for b in baselines if b]
                    
                    from .face_utils import compare_faces
                    status, info, data_dict = compare_faces(img_url, baselines, target_gender=uv.gender)
                    
                    if status == 'REJECT':
                        messages.error(request, info)
                        return render(request, 'complete_profile.html', {'form': form})
                    
                    new_profile.profile_pic = img_url
                    new_profile.is_face_verified = (status == 'PASS')
                    new_profile.verification_status = 'verified' if status == 'PASS' else 'manual_review'
                    
                    # Update Verification Record
                    uv.is_verified = (status == 'PASS')
                    uv.status = 'verified' if status == 'PASS' else 'manual_review'
                    if data_dict:
                        uv.face_match_score = data_dict.get('score')
                        uv.profile_photo_gender = data_dict.get('p_gender')
                    uv.save()
                else:
                    messages.warning(request, "Photo upload failed.")
            elif uv and uv.is_verified:
                new_profile.is_face_verified = True
            
            new_profile.save()

            # Gallery
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

    question = Question.objects.exclude(id__in=answered_ids).first()

    if not question:
        # DISCOVERY MODE: Fetch and Rank All Potential Matches
        # Filter candidates: exclude self, already liked/skipped, and blocked users
        interacted_user_ids = MatchRequest.objects.filter(sender=user).values_list('receiver_id', flat=True)
        blocked_user_ids = list(BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)) + \
                           list(BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True))
        
        candidates = Profile.objects.filter(is_discoverable=True).exclude(user=user).exclude(user__id__in=interacted_user_ids).exclude(user__id__in=blocked_user_ids)
        
        matches_list = []
        for c in candidates:
            # Mutual Preference Filter
            user_pref_ok = (profile.pref_gender == 'any' or profile.pref_gender == c.gender)
            cand_pref_ok = (c.pref_gender == 'any' or c.pref_gender == profile.gender)
            
            if user_pref_ok and cand_pref_ok:
                score = calculate_match_score(user, c.user)
                matches_list.append({
                    'profile': c,
                    'score': score
                })
        
        # Sort by best score
        matches_list.sort(key=lambda x: x['score'], reverse=True)
        
        sparked_ids = list(Spark.objects.filter(sender=user).values_list('receiver_id', flat=True))
        
        return render(request, "home.html", {
            "all_done": True, 
            "progress": 100,
            "matches": matches_list[:20],  # Show top 20
            "sparked_ids": sparked_ids
        })

    total_q_db = Question.objects.count()
    progress = int((ans_count / total_q_db) * 100) if total_q_db > 0 else 0
    sparked_ids = list(Spark.objects.filter(sender=user).values_list('receiver_id', flat=True))

    return render(request, "home.html", {"question": question, "progress": progress, "sparked_ids": sparked_ids})


import math

# ---------------- MATCHING LOGIC ----------------
def calculate_match_score(user1, user2):
    """Calculate match % between two users based on answers using Cosine Similarity and Euclidean distance (Pure Python)"""
    user1_answers = UserAnswer.objects.filter(user=user1).select_related('option')
    user2_answers = UserAnswer.objects.filter(user=user2).select_related('option')
    
    user1_dict = {ans.question_id: ans.option.weight for ans in user1_answers}
    user2_dict = {ans.question_id: ans.option.weight for ans in user2_answers}
    
    common_questions = set(user1_dict.keys()).intersection(set(user2_dict.keys()))
    
    if not common_questions:
        return 0
    
    v1 = [user1_dict[q_id] for q_id in common_questions]
    v2 = [user2_dict[q_id] for q_id in common_questions]
    
    # 1. Euclidean distance
    euc_dist_sq = sum((x - y) ** 2 for x, y in zip(v1, v2))
    euc_dist = math.sqrt(euc_dist_sq)
    euc_sim = 1 / (1 + euc_dist)
    
    # 2. Cosine Similarity
    dot_product = sum(x * y for x, y in zip(v1, v2))
    norm_v1 = math.sqrt(sum(x * x for x in v1))
    norm_v2 = math.sqrt(sum(x * x for x in v2))
    
    if norm_v1 == 0 and norm_v2 == 0:
        cos_sim = 1.0
    elif norm_v1 == 0 or norm_v2 == 0:
        cos_sim = 0.0
    else:
        cos_sim = dot_product / (norm_v1 * norm_v2)
        
    # Map [-1, 1] to [0, 1]
    normalized_cos_sim = (cos_sim + 1) / 2
    
    # Blended Score: 60% Euclidean, 40% Cosine
    combined_score = (0.6 * euc_sim + 0.4 * normalized_cos_sim) * 100
    
    return int(combined_score)


    return int(combined_score)


# ---------------- FAST QUIZ API ----------------
from django.http import JsonResponse
import json

@login_required
def get_quiz_batch(request):
    """Returns a batch of 15 questions. If all are answered, loops back to oldest ones."""
    answered_ids = UserAnswer.objects.filter(user=request.user).values_list('question_id', flat=True)
    
    # Try to get 15 unanswered
    questions = list(Question.objects.exclude(id__in=answered_ids).order_by('?')[:15])
    
    # If we don't have enough unanswered, fill with answered ones (to allow looping)
    if len(questions) < 15:
        needed = 15 - len(questions)
        loop_questions = Question.objects.filter(id__in=answered_ids).order_by('?')[:needed]
        questions.extend(list(loop_questions))
    
    data = []
    for q in questions:
        data.append({
            'id': q.id,
            'text': q.text,
            'options': [{'id': o.id, 'text': o.text} for o in q.options.all()]
        })
    
    return JsonResponse({'questions': data})

@login_required
def save_quiz_batch(request):
    """Saves a batch of answers and triggers match check if needed."""
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            answers = body.get('answers', []) # List of {question_id, option_id}
            
            for ans in answers:
                question = get_object_or_404(Question, id=ans['question_id'])
                option = get_object_or_404(Option, id=ans['option_id'])
                UserAnswer.objects.update_or_create(
                    user=request.user,
                    question=question,
                    defaults={"option": option},
                )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False})


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

        # BUG FIX: redirect to home so the 5-question session-break logic runs properly
        return redirect('home')

    return redirect('home')


# ---------------- CHECK MATCH POPUP ----------------
@login_required

def check_match(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    if profile is None:
        return redirect('home')

    # Exclude ANY users we have already interacted with (liked, rejected, skipped, pending)
    interacted_user_ids = MatchRequest.objects.filter(sender=user).values_list('receiver_id', flat=True)

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

        if user_pref_ok and cand_pref_ok and user_age_ok and cand_age_ok:
            preference_filtered.append(c)

    # ── Step 2: Rank by answer similarity ──
    best_match = None
    best_score = -1

    for candidate in preference_filtered:
        score = calculate_match_score(user, candidate.user)
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


# ---------------- SETUP PAGE ----------------
@login_required
def setup(request):
    return render(request, "setup.html")


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
        # --- LAZY FIREBASE INITIALIZATION ---
        if not firebase_admin._apps:
            try:
                # Clear any ghost apps to prevent "app already exists" or "app does not exist" confusion
                for app_name in list(firebase_admin._apps.keys()):
                    firebase_admin.delete_app(firebase_admin._apps[app_name])
                
                cert_path = os.path.join(settings.BASE_DIR, 'serviceAccountKey.json')
                if os.path.exists(cert_path):
                    cred = credentials.Certificate(cert_path)
                    firebase_admin.initialize_app(cred)
                else:
                    firebase_config = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '').strip()
                    if firebase_config:
                        # Clean wrapping quotes
                        if (firebase_config.startswith('"') and firebase_config.endswith('"')):
                            firebase_config = firebase_config[1:-1]
                        
                        # Ensure newlines are escaped for JSON
                        safe_config = firebase_config.replace('\n', '\\n').replace('\r', '')
                        try:
                            cred_dict = json.loads(safe_config, strict=False)
                        except:
                            cred_dict = json.loads(firebase_config, strict=False)
                        
                        if 'private_key' in cred_dict:
                            pk = cred_dict['private_key']
                            if isinstance(pk, str):
                                cred_dict['private_key'] = pk.replace('\\n', '\n').replace('\\\\n', '\n')
                        
                        cred = credentials.Certificate(cred_dict)
                        firebase_admin.initialize_app(cred)
                print("DEBUG: Firebase initialized successfully in view.")
            except Exception as e:
                print(f"Firebase Lazy Init Error: {e}")
                return JsonResponse({'success': False, 'error': f'Firebase Init Failure: {str(e)}'}, status=500)

        try:
            data = json.loads(request.body)
            id_token = data.get('idToken')
            
            # Use get_app() to ensure we are using the initialized default app
            default_app = firebase_admin.get_app()
            decoded_token = firebase_auth.verify_id_token(id_token, app=default_app)
            email = decoded_token.get('email', '')
            
            # if not email.endswith('@srmist.edu.in'):
            #     return JsonResponse({'success': False, 'error': 'Only @srmist.edu.in emails are allowed.'}, status=403)
            
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


# ---------------- SOCIAL & CONNECTIONS ----------------
@login_required
def send_match_request(request, receiver_id):
    if request.method == 'POST':
        receiver = get_object_or_404(User, id=receiver_id)
        if receiver != request.user:
            MatchRequest.objects.get_or_create(sender=request.user, receiver=receiver)
        
        # Reset last_match_count so they can continue answering
        # request.session['last_match_count'] it was already set in home
    
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
    incoming_requests = MatchRequest.objects.filter(receiver=request.user, status='pending')
    # Accepted matches can be either sent or received
    accepted_sent = MatchRequest.objects.filter(sender=request.user, status='accepted')
    accepted_received = MatchRequest.objects.filter(receiver=request.user, status='accepted')
    
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
@login_required
def chat_list_view(request):
    user = request.user
    
    # Get all active connections
    accepted_sent = MatchRequest.objects.filter(sender=user, status='accepted')
    accepted_received = MatchRequest.objects.filter(receiver=user, status='accepted')
    
    # Get blocked user IDs to filter out
    blocked_ids = set(BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)) | \
                  set(BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True))
    
    connected_users = []
    for req in accepted_sent:
        if req.receiver.id not in blocked_ids:
            connected_users.append(req.receiver)
    for req in accepted_received:
        if req.sender.id not in blocked_ids:
            connected_users.append(req.sender)
        
    chats = []
    for partner in connected_users:
        latest_msg = Message.objects.filter(
            (Q(sender=user, receiver=partner, sender_deleted=False)) |
            (Q(sender=partner, receiver=user, receiver_deleted=False))
        ).order_by('-timestamp').first()
        
        # Only show chat in Inbox if there is at least one visible message
        if latest_msg:
            unread_count = Message.objects.filter(sender=partner, receiver=user, is_read=False, receiver_deleted=False).count()
            
            chats.append({
                'partner': partner,
                'latest_message': latest_msg,
                'unread_count': unread_count,
                'timestamp': latest_msg.timestamp
            })
        
    # Sort so that chats with the most recent messages appear first
    chats.sort(key=lambda x: x['timestamp'].timestamp() if x.get('timestamp') else 0, reverse=True)
    
    return render(request, 'chat_list.html', {'chats': chats})


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
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': {
                        'id': msg.id,
                        'text': msg.text,
                        'sender_id': msg.sender_id,
                        'timestamp': msg.timestamp.strftime("%H:%M"),
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
        (Q(sender=partner, receiver=user, receiver_deleted=False))
    ).exclude(text__startswith='__SPIN__:') .order_by('timestamp')
    
    # Mark messages as read
    Message.objects.filter(sender=partner, receiver=request.user, is_read=False).update(is_read=True)
    
    # Spark status
    has_sparked = Spark.objects.filter(sender=request.user, receiver=partner).exists()
    
    return render(request, "chat.html", {
        "partner": partner,
        "chat_messages": chat_messages,
        "has_sparked": has_sparked
    })


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
            'timestamp': msg.timestamp.strftime("%H:%M"),
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
def reverify_profile(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return redirect('setup')
    
    return render(request, 'reverify_profile.html', {
        'profile': profile
    })

@login_required
def edit_profile(request):
    profile = get_object_or_404(Profile, user=request.user)
    
    if request.method == "POST":
        # Handle Profile Info Update
        if 'update_profile' in request.POST:
            print("DEBUG: edit_profile POST received (update_profile)")
            print(f"FILES in request: {request.FILES.keys()}")
            form = ProfileEditForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                print("DEBUG: form.is_valid() is TRUE")
                updated_profile = form.save(commit=False)
                
                # Handle Supabase Upload
                if 'profile_pic_file' in request.FILES:
                    if not profile.is_face_verified:
                        messages.error(request, "Please verify your face before updating your profile picture.")
                        return redirect('edit_profile')
                        
                    submitted_pfp = request.FILES['profile_pic_file']
                    img_url = upload_to_supabase(submitted_pfp, bucket="images", path="profile_pics")
                    print(f"DEBUG: PFP Uploaded, URL: {img_url}")
                    if img_url:
                        # Compare faces
                        from .face_utils import compare_faces
                        match, error = compare_faces(img_url, profile.verification_image)
                        if match:
                            updated_profile.profile_pic = img_url
                            messages.success(request, "Profile picture updated successfully!")
                        else:
                            messages.error(request, f"Face mismatch: The photo does not match your verified face. {error if error else ''}")
                            return redirect('edit_profile')
                    else:
                        messages.error(request, "Failed to upload profile picture to Supabase. Please check your credentials.")
                
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
            if not profile.is_face_verified:
                messages.error(request, "Please verify your face first.")
                return redirect('edit_profile')
                
            if 'profile_pic_file' in request.FILES:
                img_url = upload_to_supabase(request.FILES['profile_pic_file'], bucket="images", path="profile_pics")
                if img_url:
                    profile.profile_pic = img_url
                    profile.save()
                    messages.success(request, "Profile picture updated successfully!")
                else:
                    messages.error(request, "Failed to upload profile picture. Check Supabase policies.")
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
    return render(request, 'wall.html')


@csrf_exempt
def wall_api(request):
    if request.method == 'GET':
        strokes = WallStroke.objects.all().values('id', 'points', 'color', 'brush_size')
        return JsonResponse({'strokes': list(strokes)})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            stroke = WallStroke.objects.create(
                points=data['points'],
                color=data['color'],
                brush_size=data['brush_size']
            )
            return JsonResponse({'success': True, 'id': stroke.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


# ---------------- CONFESSIONS ----------------

def confessions_feed(request):
    sort_by = request.GET.get('sort', 'latest')
    campus_filter = request.GET.get('campus', '')
    
    is_admin = request.user.is_authenticated and request.user.email == 'arunmohankml@gmail.com'
    
    confessions = Confession.objects.all()
    
    if not is_admin:
        # For normal users, hide heavily flagged posts if you want, or just show everything
        pass

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

@login_required
def create_confession(request):
    if request.method == 'POST':
        content = request.POST.get('content')
        is_anonymous = request.POST.get('is_anonymous') == 'true'
        campus = request.POST.get('campus', '')
        
        if request.user.profile.is_banned:
            messages.error(request, "You are banned.")
            return redirect('confessions_feed')

        Confession.objects.create(
            user=request.user,
            content=content,
            image='',
            campus=campus,
            is_anonymous=is_anonymous
        )
        messages.success(request, 'Confession posted!')
        return redirect('confessions_feed')
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
        messages.success(request, "Confession deleted.")
        return redirect('confessions_feed')
    
    messages.error(request, "Not authorized.")
    return redirect('confession_detail', confession_id=confession_id)

@login_required
def report_confession(request, confession_id):
    confession = get_object_or_404(Confession, id=confession_id)
    if request.method == 'POST':
        reasons = request.POST.getlist('reasons')
        other_reason = request.POST.get('other_reason', '')
        ConfessionReport.objects.update_or_create(
            confession=confession,
            user=request.user,
            defaults={
                'reasons': reasons,
                'other_reason': other_reason
            }
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

@login_required
def add_comment(request, confession_id):
    if request.method == 'POST':
        confession = get_object_or_404(Confession, id=confession_id)
        content = request.POST.get('content')
        is_anonymous = request.POST.get('is_anonymous') == 'true'
        
        if content:
            ConfessionComment.objects.create(
                confession=confession,
                user=request.user,
                content=content,
                is_anonymous=is_anonymous
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


# ---------------- ADMIN MENU ----------------

def is_admin_check(user):
    return user.is_authenticated and user.email == 'arunmohankml@gmail.com'

@login_required
def admin_dashboard(request):
    if not is_admin_check(request.user):
        return HttpResponse("Not authorized", status=403)
    
    reported_confessions = Confession.objects.filter(is_flagged=True).order_by('-created_at')
    user_reports = UserReport.objects.all().order_by('-created_at')
    all_users = Profile.objects.all().order_by('-created_at')
    face_reviews = UserVerification.objects.filter(status='manual_review').order_by('-updated_at')
    
    return render(request, 'admin_dashboard.html', {
        'reported_confessions': reported_confessions,
        'user_reports': user_reports,
        'all_users': all_users,
        'face_reviews': face_reviews
    })

@login_required
def admin_action(request):
    if not is_admin_check(request.user):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        target_id = request.POST.get('target_id')
        
        if action == 'delete_confession':
            Confession.objects.filter(id=target_id).delete()
        elif action == 'dismiss_confession':
            Confession.objects.filter(id=target_id).update(is_flagged=False)
            ConfessionReport.objects.filter(confession_id=target_id).delete()
        elif action == 'delete_user_report':
            UserReport.objects.filter(id=target_id).delete()
        elif action == 'clear_wall':
            WallStroke.objects.all().delete()
        elif action == 'ban_user':
            profile = get_object_or_404(Profile, id=target_id)
            profile.is_banned = True
            profile.save()
        elif action == 'unban_user':
            profile = get_object_or_404(Profile, id=target_id)
            profile.is_banned = False
            profile.save()
            
        elif action == 'approve_face':
            uv = get_object_or_404(UserVerification, id=target_id)
            uv.status = 'verified'
            uv.is_verified = True
            uv.save()
            if hasattr(uv.user, 'profile'):
                uv.user.profile.is_face_verified = True
                uv.user.profile.verification_status = 'verified'
                uv.user.profile.save()
        elif action == 'reject_face':
            uv = get_object_or_404(UserVerification, id=target_id)
            uv.status = 'rejected'
            uv.is_verified = False
            uv.save()
            if hasattr(uv.user, 'profile'):
                uv.user.profile.is_face_verified = False
                uv.user.profile.verification_status = 'rejected'
                # Do not delete profile pic, just mark as rejected
                uv.user.profile.save()
            
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

@login_required
@csrf_exempt
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



@login_required
@csrf_exempt
def verify_face_live(request):
    """
    Receives 3 base64 images and saves to UserVerification + Supabase.
    Analyzes baseline gender.
    """
    print("================ VERIFY LIVE DEBUG ================")
    print(f"User: {request.user} (ID: {request.user.id})")
    print(f"Method: {request.method}")
    print(f"Content-Length: {request.META.get('CONTENT_LENGTH')}")
    print(f"Body size: {len(request.body)} bytes")
    
    if request.method != 'POST': 
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        img_f = data.get('image_front') or data.get('image')
        img_l = data.get('image_left')
        img_r = data.get('image_right')
        
        if not img_f: 
            return JsonResponse({'success': False, 'message': 'Front image required'}, status=400)

        from concurrent.futures import ThreadPoolExecutor

        def analyze_gender_task():
            from .face_utils import save_base64_to_temp, analyze_gender
            temp_path = save_base64_to_temp(img_f, f"gender_check_{request.user.id}.jpg")
            gender, conf = analyze_gender(temp_path)
            if os.path.exists(temp_path): os.remove(temp_path)
            return gender, conf

        def upload_b64(b64, name):
            if not b64: return None
            if 'base64,' in b64: b64 = b64.split('base64,')[1]
            img_data = base64.b64decode(b64)
            f_obj = ContentFile(img_data, name=f"{name}_{request.user.id}.jpg")
            return upload_to_supabase(f_obj, bucket="images", path="verification_baselines")

        print("[VERIFY-LIVE] Starting concurrent analysis and uploads...")
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_gender = executor.submit(analyze_gender_task)
            future_f = executor.submit(upload_b64, img_f, "front")
            future_l = executor.submit(upload_b64, img_l, "left")
            future_r = executor.submit(upload_b64, img_r, "right")

            baseline_gender, baseline_conf = future_gender.result()
            url_f = future_f.result()
            url_l = future_l.result()
            url_r = future_r.result()

        print(f"[VERIFY-LIVE] Detected Baseline Gender: {baseline_gender} ({baseline_conf}%)")

        if not url_f:
            print("[VERIFY-LIVE] ERROR: url_f is None. Upload to Supabase failed.")
            return JsonResponse({'success': False, 'message': 'Upload to Supabase failed. Check storage.'}, status=400)

        # Save to UserVerification
        uv, _ = UserVerification.objects.update_or_create(
            user=request.user,
            defaults={
                'image_front': url_f,
                'image_left': url_l,
                'image_right': url_r,
                'gender': baseline_gender,
                'status': 'pending',
                'is_verified': False
            }
        )
        
        safe_print(f"UserVerification created for {request.user.id}")
        return JsonResponse({'success': True, 'message': 'Face profiles secured!'})
            
    except Exception as e:
        import traceback
        print("VERIFY LIVE ERROR:", str(e))
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@csrf_exempt
def compare_pfp_live(request):
    """
    Dual-model PFP comparison against UserVerification.
    Uses stored baseline gender for strict rejection.
    """
    if request.method != 'POST': return JsonResponse({'success': False}, status=405)
    
    try:
        data = json.loads(request.body)
        image_data = data.get('image')
        if not image_data: return JsonResponse({'success': False, 'error': 'No image'}, status=400)
            
        uv = getattr(request.user, 'verification', None)
        if not uv or not uv.image_front:
            return JsonResponse({'success': False, 'error': 'Please complete face scan first.'}, status=400)

        # Collect baselines
        baselines = [uv.image_front, uv.image_left, uv.image_right]
        baselines = [b for b in baselines if b]

        # Helper to convert to path
        def get_path(val, name):
            if not val: return None
            if str(val).startswith('http'):
                import requests as req_lib
                resp = req_lib.get(val, timeout=10)
                if resp.status_code == 200:
                    temp_dir = os.environ.get('TEMP', '/tmp') if os.name == 'nt' else '/tmp'
                    path = os.path.join(temp_dir, f"baseline_{name}_{request.user.id}.jpg")
                    with open(path, 'wb') as f: f.write(resp.content)
                    return path
            return None

        gallery_paths = [get_path(b, f"angle_{i}") for i, b in enumerate(baselines)]
        gallery_paths = [p for p in gallery_paths if p]

        from .face_utils import save_base64_to_temp, compare_faces
        probe_path = save_base64_to_temp(image_data, f"probe_{request.user.id}.jpg")

        # Use stored baseline gender for comparison
        status, info, data_dict = compare_faces(probe_path, gallery_paths, target_gender=uv.gender)
        print(f"[COMPARE-PFP] Result: {status} | Data: {data_dict}")

        # Handle Decisions
        if status == 'PASS':
            uv.is_verified = True
            uv.status = 'verified'
        elif status == 'REVIEW':
            uv.status = 'manual_review'
        else:
            uv.status = 'rejected'
            
        if data_dict:
            uv.face_match_score = data_dict.get('score')
            uv.profile_photo_gender = data_dict.get('p_gender')
        uv.save()

        # Update Profile sync
        profile = getattr(request.user, 'profile', None)
        if profile:
            profile.is_face_verified = (status == 'PASS')
            profile.verification_status = 'verified' if status == 'PASS' else ('manual_review' if status == 'REVIEW' else 'rejected')
            profile.save()

        # Cleanup
        for p in gallery_paths + [probe_path]:
            if p and os.path.exists(p): os.remove(p)

        if status == 'PASS':
            return JsonResponse({'success': True, 'message': 'Identity verified! Looking great.'})
        elif status == 'REVIEW':
            return JsonResponse({
                'success': True,
                'manual_review': True,
                'message': "We're reviewing your photo"
            })
        else:
            return JsonResponse({'success': False, 'error': info}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def migrate_face_verification(request):
    """
    One-time migration for existing users: use current PFP as verification image.
    """
    if not request.user.is_staff and request.user.email != 'arunmohankml@gmail.com':
        return HttpResponse("Unauthorized", status=403)
        
    profiles = Profile.objects.filter(is_face_verified=False).exclude(profile_pic='')
    count = 0
    for p in profiles:
        if p.profile_pic and ('http' in p.profile_pic):
            p.verification_image = p.profile_pic
            p.is_face_verified = True
            p.save()
            count += 1
            
    return HttpResponse(f"Migrated {count} profiles successfully.")
