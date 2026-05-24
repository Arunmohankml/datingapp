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
import pusher
from .pusher_utils import broadcast_event
from .cloudinary_utils import upload_to_cloudinary, upload_base64_to_cloudinary
from .moderation import (
    check_bad_words, check_duplicate, check_name_mention,
    check_rate_limit, record_rate_limit, check_shadow_ban
)
from django.core.paginator import Paginator

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

from .models import Profile, Question, Option, UserAnswer, MatchRequest, Message, ProfileImage, WallStroke, WallImage, Confession, ConfessionComment, ConfessionLike, ConfessionReport, UserReport, Spark, BlockedUser, Announcement, FavoriteMovie, FavoriteSong, FCMToken, BannedIdentifier, Conversation, RoomRequest
from .forms import ProfileForm, ProfileEditForm, ProfileImageForm, ProfileInitForm
from .supabase_utils import delete_from_supabase_by_url
from .cloudinary_utils import upload_to_cloudinary, upload_base64_to_cloudinary
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
    profile, created = Profile.objects.get_or_create(user=user)

    # If profile is already initialized with basic info, don't allow re-entry
    if profile.name and profile.age and profile.gender and profile.campus and profile.native_place:
        return redirect('home')

    if request.method == 'POST':
        form = ProfileInitForm(request.POST, instance=profile)
        if form.is_valid():
            new_profile = form.save(commit=False)
            new_profile.user = user
            new_profile.save()
            messages.success(request, "Welcome! Basic profile created successfully.")
            return redirect('home')
    else:
        form = ProfileInitForm(instance=profile)

    return render(request, 'complete_profile.html', {'form': form})


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@login_required
def save_profile_progress(request):
    if request.method == 'POST':
        try:
            user = request.user
            profile, created = Profile.objects.get_or_create(user=user)
            
            # Basic Info
            if 'name' in request.POST:
                profile.name = request.POST.get('name')
            if 'gender' in request.POST:
                profile.gender = request.POST.get('gender')
            if 'age' in request.POST:
                age_val = request.POST.get('age')
                profile.age = int(age_val) if age_val else None
            
            # Origins
            if 'living_place' in request.POST:
                profile.living_place = request.POST.get('living_place')
            if 'native_place' in request.POST:
                profile.native_place = request.POST.get('native_place')
                
            # Languages
            if 'languages' in request.POST:
                profile.languages = request.POST.get('languages')
            if 'mother_tongues' in request.POST:
                profile.mother_tongues = request.POST.get('mother_tongues')
                
            # Interests & Bio
            if 'interest_tags' in request.POST:
                profile.interest_tags = request.POST.get('interest_tags')
            if 'bio' in request.POST:
                profile.bio = request.POST.get('bio')
            if 'liked_songs' in request.POST:
                profile.liked_songs = request.POST.get('liked_songs')
            if 'liked_movies' in request.POST:
                profile.liked_movies = request.POST.get('liked_movies')
            if 'fav_shows' in request.POST:
                profile.fav_shows = request.POST.get('fav_shows')
                
            # Education
            if 'clg_year' in request.POST:
                year_val = request.POST.get('clg_year')
                profile.clg_year = int(year_val) if year_val else None
            if 'campus' in request.POST:
                profile.campus = request.POST.get('campus')
            if 'course' in request.POST:
                profile.course = request.POST.get('course')
                
            # Preferences
            if 'looking_for' in request.POST:
                profile.looking_for = request.POST.get('looking_for')
            if 'pref_gender' in request.POST:
                profile.pref_gender = request.POST.get('pref_gender')
            if 'pref_age_min' in request.POST:
                min_val = request.POST.get('pref_age_min')
                profile.pref_age_min = int(min_val) if min_val else 18
            if 'pref_age_max' in request.POST:
                max_val = request.POST.get('pref_age_max')
                profile.pref_age_max = int(max_val) if max_val else 25
            if 'pref_languages' in request.POST:
                profile.pref_languages = request.POST.get('pref_languages')
                
            # Face Verification & PFP
            if 'verification_image_url' in request.POST:
                profile.verification_image = request.POST.get('verification_image_url')
            if 'verification_status' in request.POST:
                profile.verification_status = request.POST.get('verification_status')
                if profile.verification_status == 'verified':
                    profile.is_face_verified = True
                else:
                    profile.is_face_verified = False
            if 'profile_pic_url' in request.POST:
                profile.profile_pic = request.POST.get('profile_pic_url')
                
            profile.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

@login_required
def verify(request):
    user = request.user
    profile = get_object_or_404(Profile, user=user)

    if profile.is_face_verified:
        return redirect('home')

    if request.method == 'POST':
        # Handle verification image
        verify_url = request.POST.get('verification_image_url')
        verify_status = request.POST.get('verification_status', 'pending')
        
        if verify_url:
            profile.verification_image = verify_url
            profile.verification_status = verify_status
            if verify_status == 'verified':
                profile.is_face_verified = True
            
        # Handle profile pic
        pfp_url = request.POST.get('profile_pic_url')
        if pfp_url:
            profile.profile_pic = pfp_url
        
        if profile.verification_image and profile.profile_pic:
            profile.save()
            messages.success(request, "Identity verification submitted!")
            return redirect('home')
        else:
            messages.error(request, "Both verification and profile picture are required.")

    return render(request, 'verify.html', {'profile': profile})


# ---------------- HOME HUB ----------------
@login_required
def home_hub(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    if not profile or not profile.name or not profile.age or not profile.gender or not profile.campus or not profile.native_place:
        return redirect('complete_profile')

    from .models import Confession, Announcement
    latest_confession = Confession.objects.filter(moderation_status='approved', is_flagged=False).order_by('-created_at').first()
    latest_update = Announcement.objects.order_by('-created_at').first()
    total_users = User.objects.count() + 50
    
    # Discovery checklist & hint variables
    missing = _profile_missing_fields(profile)
    checklist = _profile_discovery_checklist(profile)
    profile_complete = len(missing) == 0
    is_verified = profile.is_face_verified
    
    return render(request, "home_hub.html", {
        "profile": profile,
        "latest_confession": latest_confession,
        "latest_update": latest_update,
        "total_users": total_users,
        "is_discoverable": profile.is_discoverable,
        "profile_complete": profile_complete,
        "is_verified": is_verified,
        "missing_fields": missing,
        "checklist": checklist,
    })

@login_required
def more_menu(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    return render(request, "more_menu.html", {"profile": profile})

# ---------------- MATCHING FEED ----------------
@login_required
def match_feed(request):
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

    if not profile.name or not profile.age or not profile.gender or not profile.campus or not profile.native_place:
        return redirect('complete_profile')



    # If user is not discoverable, they can't see the feed
    if not profile.is_discoverable:
        missing = _profile_missing_fields(profile)
        checklist = _profile_discovery_checklist(profile)
        return render(request, "home.html", {
            "not_discoverable": True,
            "profile": profile,
            "missing_fields": missing,
            "checklist": checklist,
            "profile_complete": len(missing) == 0,
            "is_verified": profile.is_face_verified,
        })

    # Get answered questions count
    answered_ids = list(UserAnswer.objects.filter(user=user).values_list("question_id", flat=True))
    ans_count = len(answered_ids)

    # ── 10-question round break ──
    # Round number = how many complete 10-question rounds the user has finished
    current_round = ans_count // 10  # 10→1, 20→2, 30→3 ...

    if 'rounds_shown' not in request.session:
        request.session['rounds_shown'] = current_round

    rounds_shown = request.session['rounds_shown']

    if current_round > rounds_shown:
        # A new round has been completed — show a match
        request.session['rounds_shown'] = current_round
        return redirect('check_match')

    # CHECK IF ANY MATCHES ARE LEFT BEFORE SHOWING QUIZ
    # Users the current user has already acted on
    users_i_acted_on = list(MatchRequest.objects.filter(sender=user).values_list('receiver_id', flat=True))
    # Users who acted on the current user, excluding those who just skipped them
    users_who_acted_on_me_excluding_skips = list(MatchRequest.objects.filter(receiver=user).exclude(status='skipped').values_list('sender_id', flat=True))
    interacted_user_ids = set(users_i_acted_on + users_who_acted_on_me_excluding_skips)
    
    blocked_user_ids = list(BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)) + \
                       list(BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True))
    
    # Candidates are discoverable, verified profiles (quiz completion optional to avoid empty feeds after reset)
    candidates_qs = Profile.objects.filter(
        is_discoverable=True, 
        is_face_verified=True,
    ).exclude(user=user).exclude(user__id__in=interacted_user_ids).exclude(user__id__in=blocked_user_ids)
    
    has_valid_candidates = False
    for c in candidates_qs:
        user_pref_ok = (profile.pref_gender == 'any' or profile.pref_gender == c.gender)
        cand_pref_ok = (profile.pref_gender == 'any' or c.pref_gender == 'any' or c.pref_gender == profile.gender)
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
        users_i_acted_on = list(MatchRequest.objects.filter(sender=user).values_list('receiver_id', flat=True))
        users_who_acted_on_me_excluding_skips = list(MatchRequest.objects.filter(receiver=user).exclude(status='skipped').values_list('sender_id', flat=True))
        interacted_user_ids = set(users_i_acted_on + users_who_acted_on_me_excluding_skips)
        
        blocked_user_ids = list(BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)) + \
                           list(BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True))
        
        candidates = Profile.objects.filter(
            is_discoverable=True,
        ).exclude(user=user).exclude(user__id__in=interacted_user_ids).exclude(user__id__in=blocked_user_ids).select_related('user')
        
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
            # 1. Strict Gender Preference
            user_pref_ok = (profile.pref_gender == 'any' or profile.pref_gender == c.gender)
            cand_pref_ok = (profile.pref_gender == 'any' or c.pref_gender == 'any' or c.pref_gender == profile.gender)
            
            if not (user_pref_ok and cand_pref_ok):
                continue
                
            cand_dict = cand_ans_map.get(c.user_id, {})
            score = calculate_match_score_optimized(user_dict, cand_dict)
            
            # Age preference bool
            user_age_ok = True
            if profile.age:
                user_age_ok = (c.pref_age_min <= profile.age <= c.pref_age_max)
            cand_age_ok = True
            if c.age:
                cand_age_ok = (profile.pref_age_min <= c.age <= profile.pref_age_max)
            mutual_age_ok = (user_age_ok and cand_age_ok)

            looking_for_match = (profile.looking_for == c.looking_for)
            campus_match = (profile.campus == c.campus)
            
            matches_list.append({
                'profile': c, 
                'score': min(score, 100),
                'mutual_age_ok': mutual_age_ok,
                'looking_for_match': looking_for_match,
                'campus_match': campus_match
            })
        
        # Sort by: (Age Match, Looking For Match, Question Score, Campus Match, Random/Fallthrough)
        # True sorts after False, so reverse=True sorts True first
        matches_list.sort(key=lambda x: (x['mutual_age_ok'], x['looking_for_match'], x['score'], x['campus_match']), reverse=True)
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

    # Exclude ANY users where a MatchRequest exists, UNLESS they only skipped us
    users_i_acted_on = list(MatchRequest.objects.filter(sender=user).values_list('receiver_id', flat=True))
    users_who_acted_on_me_excluding_skips = list(MatchRequest.objects.filter(receiver=user).exclude(status='skipped').values_list('sender_id', flat=True))
    interacted_user_ids = set(users_i_acted_on + users_who_acted_on_me_excluding_skips)

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
    
    candidates = Profile.objects.filter(
        is_discoverable=True,
    ).exclude(user=user).exclude(user__id__in=interacted_user_ids).exclude(user__id__in=seen_ids)

    matches_list = []
    for c in candidates:
        # 1. Strict Gender Preference
        user_pref_ok = (profile.pref_gender == 'any' or profile.pref_gender == c.gender)
        cand_pref_ok = (profile.pref_gender == 'any' or c.pref_gender == 'any' or c.pref_gender == profile.gender)
        
        if not (user_pref_ok and cand_pref_ok):
            continue

        score = calculate_match_score(user, c.user)
        score = min(score, 100)

        # Age range check (both ways)
        user_age_ok = True
        if profile.age:
            user_age_ok = (c.pref_age_min <= profile.age <= c.pref_age_max)
        cand_age_ok = True
        if c.age:
            cand_age_ok = (profile.pref_age_min <= c.age <= profile.pref_age_max)
        mutual_age_ok = (user_age_ok and cand_age_ok)

        looking_for_match = (profile.looking_for == c.looking_for)
        campus_match = (profile.campus == c.campus)

        matches_list.append({
            'profile': c, 
            'score': score,
            'mutual_age_ok': mutual_age_ok,
            'looking_for_match': looking_for_match,
            'campus_match': campus_match
        })

    # ── Step 2: Rank by priority ──
    best_match = None
    best_score = 0
    if matches_list:
        matches_list.sort(key=lambda x: (x['mutual_age_ok'], x['looking_for_match'], x['score'], x['campus_match']), reverse=True)
        best_match_data = matches_list[0]
        best_match = best_match_data['profile']
        best_score = best_match_data['score']

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
        if profile and profile.name and profile.age and profile.gender and profile.campus and profile.native_place:
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
            profile_complete = profile is not None and bool(profile.name) and bool(profile.age) and bool(profile.gender) and bool(profile.campus) and bool(profile.native_place)
            
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
            
            # Prevent unique token IntegrityError if token belongs to another user
            FCMToken.objects.filter(token=token).exclude(user=request.user).delete()
            
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

    # Construct absolute HTTPS URL as required by Firebase WebpushFCMOptions.link
    domain = os.environ.get('VERCEL_URL')
    if not domain:
        domain = 'srmmatch.vercel.app' # fallback
    
    if not domain.startswith('http'):
        domain = f"https://{domain}"
    elif domain.startswith('http://'):
        domain = domain.replace('http://', 'https://')
        
    absolute_url = f"{domain.rstrip('/')}/{url.lstrip('/')}"

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
                link=absolute_url
            )
        )
    )
    try:
        response = messaging.send_each_for_multicast(message)
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
                # Send Push Notification
                try:
                    send_push_to_user(
                        receiver,
                        title="New Connection Request ⚡",
                        body="You have received a request from someone",
                        url="/connections/"
                    )
                except Exception as e:
                    print(f"Push Error (Connection Request): {e}")
            else:
                messages.info(request, "Connection request already sent.")
        
        # Reset last_match_count so they can continue answering
    
    return redirect('match_feed')
    
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
    return redirect('match_feed')

@login_required
def accept_match(request, req_id):
    req = get_object_or_404(MatchRequest, id=req_id, receiver=request.user)
    req.status = 'accepted'
    req.save()
    
    # Send Push Notification to the sender of the request
    try:
        send_push_to_user(
            req.sender,
            title="Connection Accepted! 🎉",
            body="Someone has accepted your request",
            url=f"/chat/{request.user.id}/"
        )
    except Exception as e:
        print(f"Push Error (Accept Match): {e}")

    # Broadcast to Pusher for real-time foreground update
    try:
        broadcast_event(f'chat_{req.sender.id}', 'connection_accepted', {
            'receiver_id': request.user.id,
            'receiver_name': request.user.profile.name if hasattr(request.user, 'profile') else request.user.username
        })
    except Exception as e:
        print(f"Pusher Error (Accept Match): {e}")

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
    ).exists() or Conversation.objects.filter(
        Q(user1=request.user, user2=partner) |
        Q(user1=partner, user2=request.user)
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
                send_push_to_user(
                    partner, 
                    title="New Message 💬", 
                    body="Someone sent you a message",
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
    ).exists() or Conversation.objects.filter(
        Q(user1=request.user, user2=partner) |
        Q(user1=partner, user2=request.user)
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

def _profile_missing_fields(profile):
    """Return list of missing required field labels for discovery."""
    missing = []
    if not profile.profile_pic:
        missing.append("Profile photo")
    if not profile.bio or not profile.bio.strip():
        missing.append("Bio")
    if not profile.living_place or not profile.living_place.strip():
        missing.append("Living place")
    if not profile.native_place or not profile.native_place.strip():
        missing.append("Native place")
    if not profile.course or not profile.course.strip():
        missing.append("Course")
    if not profile.clg_year:
        missing.append("Year of study")
    if not profile.interest_tags or not profile.interest_tags.strip():
        missing.append("Interests")
    if not profile.looking_for or not profile.looking_for.strip():
        missing.append("Looking for")
    if not profile.pref_gender or not profile.pref_gender.strip():
        missing.append("Interested in")
    # Need at least 2 gallery photos
    if profile.images.count() < 2:
        missing.append("At least 2 gallery photos")
    return missing


def _profile_discovery_checklist(profile):
    """Return a list of dicts with field names and their completion status."""
    return [
        {'name': 'Profile photo', 'done': bool(profile.profile_pic)},
        {'name': 'Bio', 'done': bool(profile.bio and profile.bio.strip())},
        {'name': 'Living place', 'done': bool(profile.living_place and profile.living_place.strip())},
        {'name': 'Native place', 'done': bool(profile.native_place and profile.native_place.strip())},
        {'name': 'Course', 'done': bool(profile.course and profile.course.strip())},
        {'name': 'Year of study', 'done': bool(profile.clg_year)},
        {'name': 'Interests', 'done': bool(profile.interest_tags and profile.interest_tags.strip())},
        {'name': 'At least 2 gallery photos', 'done': profile.images.count() >= 2},
        {'name': 'Account verification', 'done': profile.is_face_verified},
    ]


@login_required
@csrf_exempt
def toggle_discoverable(request):
    profile = request.user.profile

    # Check if request prefers JSON response (AJAX/Fetch)
    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '') or
        request.content_type == 'application/json'
    )

    if not profile.is_discoverable:
        # Turning ON discovery — check completeness and verification
        missing = _profile_missing_fields(profile)
        profile_complete = len(missing) == 0
        is_verified = profile.is_face_verified

        if not profile_complete and not is_verified:
            msg = f"Please complete your profile ({', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}) and verify your account first."
            if is_ajax:
                return JsonResponse({'success': False, 'error_code': 'need_both', 'error': msg, 'missing': missing})
            messages.error(request, msg)
            return redirect('edit_profile')

        if not profile_complete:
            msg = f"Please complete your profile first. Missing: {', '.join(missing)}."
            if is_ajax:
                return JsonResponse({'success': False, 'error_code': 'need_profile', 'error': msg, 'missing': missing})
            messages.error(request, msg)
            return redirect('edit_profile')

        if not is_verified:
            msg = "Your account is not verified. Please verify your face to enable discovery."
            if is_ajax:
                return JsonResponse({'success': False, 'error_code': 'need_verification', 'error': msg})
            messages.error(request, msg)
            return redirect('verify')

    profile.is_discoverable = not profile.is_discoverable
    profile.save()

    if is_ajax:
        return JsonResponse({'success': True, 'is_discoverable': profile.is_discoverable})

    # Otherwise, redirect native form submission back to the referring page
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('home')

@login_required
def edit_profile(request):
    profile = get_object_or_404(Profile, user=request.user)
    
    if request.method == "POST":
        try:
            # Handle Profile Info Update
            if 'update_profile' in request.POST:
                form = ProfileEditForm(request.POST, request.FILES, instance=profile)
                if form.is_valid():
                    updated_profile = form.save(commit=False)
                    
                    # Handle Cloudinary Upload
                    if 'profile_pic_file' in request.FILES:
                        submitted_pfp = request.FILES['profile_pic_file']
                        img_url = upload_to_cloudinary(submitted_pfp, folder="srm_match/profile_pics")
                        if img_url:
                            updated_profile.profile_pic = img_url
                            messages.success(request, "Profile picture updated successfully!")
                        else:
                            messages.error(request, "Failed to upload profile picture to Cloudinary.")
                    
                    for field in ['languages', 'mother_tongues', 'interest_tags', 'pref_languages']:
                        if field in request.POST:
                            val = request.POST.get(field, '').strip()
                            if val.startswith('[') and val.endswith(']'):
                                val = val[1:-1].replace("'", "").replace('"', "")
                            
                            if field == 'mother_tongues':
                                current_val = getattr(profile, 'mother_tongues', '')
                                if not current_val:
                                    setattr(updated_profile, field, val)
                                else:
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
                    img_url = upload_to_cloudinary(request.FILES['profile_pic_file'], folder="srm_match/profile_pics")
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
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'error', 'message': 'Maximum 5 photos allowed.'}, status=400)
                    return redirect('edit_profile')

                # Directly handle the uploaded file — skip ModelForm validation
                # because ProfileImage.image is a URLField (Cloudinary URL), not a file field.
                if 'image_file' in request.FILES:
                    img_url = upload_to_cloudinary(request.FILES['image_file'], folder="srm_match/gallery")
                    if img_url:
                        img_obj = ProfileImage.objects.create(profile=profile, image=img_url)
                        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                            return JsonResponse({
                                'status': 'success',
                                'id': img_obj.id,
                                'url': img_obj.get_image_url,
                                'count': profile.images.count(),
                                'delete_url': f"/profile/image/delete/{img_obj.id}/"
                            })
                        messages.success(request, "Gallery photo added successfully!")
                    else:
                        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                            return JsonResponse({'status': 'error', 'message': 'Failed to upload to cloud storage.'}, status=500)
                        messages.error(request, "Failed to upload gallery image.")
                else:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'error', 'message': 'No image file received.'}, status=400)
                return redirect('edit_profile')

        except Exception as e:
            import traceback
            print("!!! EDIT PROFILE POST ERROR !!!")
            traceback.print_exc()
            messages.error(request, f"An error occurred: {str(e)}")
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
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'You must keep at least 2 images in your gallery.'}, status=400)
        messages.error(request, "You must keep at least 2 images in your gallery.")
        return redirect('edit_profile')

    image.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message': 'Photo removed.',
            'count': profile.images.count()
        })
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
            broadcast_event('wall', event_type, payload)
            return JsonResponse({'success': True, 'id': obj.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    elif request.method == 'DELETE':
        if not request.user.is_superuser and request.user.email != 'arunmohankml@gmail.com':
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        try:
            data = json.loads(request.body)
            x = data.get('x')
            y = data.get('y')
            size = data.get('size', 1)
            pixel_size = 10 # Matches PIXEL_SIZE in wall.html
            
            # Area to clear
            clear_rect = size * pixel_size
            half = clear_rect / 2
            
            # Find and delete strokes that have points within the eraser area
            # We use a slightly broader search for efficiency and then filter if needed
            # For a pixel wall, most strokes are very short.
            
            # Simple approach: delete strokes whose first point is in the area
            # (In a pixel wall, strokes are often just one or a few pixels)
            deleted_ids = []
            
            # More robust: find any stroke that overlaps the bounding box
            # This is hard with JSONField directly in SQL without complex queries,
            # so we'll do a coordinate range check if possible, or just fetch recent ones and filter.
            
            # Optimization: only check strokes from the last 24 hours or just all of them if the wall is small
            all_s = WallStroke.objects.all()
            for s in all_s:
                in_range = False
                for p in s.points:
                    if (x - half <= p['x'] <= x + half + pixel_size) and (y - half <= p['y'] <= y + half + pixel_size):
                        in_range = True
                        break
                if in_range:
                    deleted_ids.append(s.id)
            
            if deleted_ids:
                WallStroke.objects.filter(id__in=deleted_ids).delete()
                broadcast_event('wall', 'delete_strokes', {'ids': deleted_ids})
                
            # Also check images
            deleted_image_ids = []
            all_i = WallImage.objects.all()
            for img in all_i:
                # Check if center point overlaps image rect
                if (img.x <= x <= img.x + img.width) and (img.y <= y <= img.y + img.height):
                    deleted_image_ids.append(img.id)
            
            if deleted_image_ids:
                WallImage.objects.filter(id__in=deleted_image_ids).delete()
                broadcast_event('wall', 'delete_images', {'ids': deleted_image_ids})

            return JsonResponse({'success': True, 'deleted_ids': deleted_ids, 'deleted_image_ids': deleted_image_ids})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


# ---------------- CONFESSIONS ----------------

def confessions_feed(request):
    sort_by = request.GET.get('sort', 'latest')
    campus_filter = request.GET.get('campus', '')
    page_number = request.GET.get('page', 1)

    is_admin = request.user.is_authenticated and request.user.email == 'arunmohankml@gmail.com'

    # Public feed: ONLY approved confessions for EVERYONE
    confessions_list = Confession.objects.filter(
        moderation_status='approved'
    ).select_related('user__profile')

    if campus_filter:
        confessions_list = confessions_list.filter(campus__iexact=campus_filter)

    if sort_by == 'top':
        confessions_list = confessions_list.order_by('-likes_count', '-created_at')
    else:
        confessions_list = confessions_list.order_by('-created_at')

    paginator = Paginator(confessions_list, 20) # Show 20 confessions per page
    page_obj = paginator.get_page(page_number)

    return render(request, 'confessions.html', {
        'confessions': page_obj,
        'current_sort': sort_by,
        'current_campus': campus_filter,
        'is_admin': is_admin
    })

def create_confession(request):
    if request.method != 'POST':
        return redirect('confessions_feed')

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
    is_admin = user and user.email == 'arunmohankml@gmail.com'
    if not is_admin:
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
    bad_word_result = check_bad_words(content)
    if not bad_word_result["safe"]:
        record_rate_limit(fingerprint, ip)  # still counts toward rate limit
        detected_str = ", ".join(bad_word_result["detected"])
        Confession.objects.create(
            user=user, content=content, campus=campus,
            is_anonymous=is_anon, poster_fingerprint=fingerprint,
            moderation_status='pending_review',
            moderation_reason=f'bad_word:{detected_str}'
        )
        messages.info(
            request,
            'Your confession has been sent for admin approval because it contains sensitive words.'
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
def admin_all_users(request):
    if not is_admin_check(request.user):
        return HttpResponse("Not authorized", status=403)
    profiles = Profile.objects.all().order_by('name')
    return render(request, 'admin_all_users.html', {'profiles': profiles})

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
            # Admin rejected a pending confession -> DELETE it
            Confession.objects.filter(id=target_id).delete()

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

        elif action == 'reset_verification':
            # Reset verification status, delete verification image and profile pic
            profile = get_object_or_404(Profile, id=target_id)
            profile.verification_status = 'pending'
            profile.is_face_verified = False
            profile.verification_image = "" # Correct field name is verification_image
            profile.profile_pic = ""
            profile.save()
            
            messages.warning(request, f"Verification reset for {profile.user.username}. They must verify again.")

        return redirect('admin_dashboard')

    return redirect('admin_dashboard')


@login_required
def admin_edit_user_profile(request, user_id):
    """Admin-only view to edit ANY user's profile."""
    from .forms import ProfileEditForm, ProfileImageForm
    if not is_admin_check(request.user):
        return HttpResponse("Not authorized", status=403)
        
    target_user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(Profile, user=target_user)
    
    if request.method == "POST":
        # We reuse the logic from edit_profile but for the target_user
        if 'update_profile' in request.POST:
            form = ProfileEditForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                updated_profile = form.save(commit=False)
                
                # Manual file handling for admin
                if 'profile_pic_file' in request.FILES:
                    img_url = upload_to_cloudinary(request.FILES['profile_pic_file'], folder="srm_match/profile_pics")
                    if img_url: updated_profile.profile_pic = img_url
                
                if 'verification_image_file' in request.FILES:
                    img_url = upload_to_cloudinary(request.FILES['verification_image_file'], folder="srm_match/verification_images")
                    if img_url: updated_profile.verification_image = img_url

                # Admin-only fields
                if 'verification_status' in request.POST:
                    updated_profile.verification_status = request.POST.get('verification_status')
                    if updated_profile.verification_status == 'verified':
                        updated_profile.is_face_verified = True

                # Tags cleanup
                for field in ['languages', 'mother_tongues', 'interest_tags', 'pref_languages']:
                    if field in request.POST:
                        val = request.POST.get(field, '').strip()
                        if val.startswith('[') and val.endswith(']'):
                            val = val[1:-1].replace("'", "").replace('"', "")
                        setattr(updated_profile, field, val)

                updated_profile.save()
                messages.success(request, f"Profile for {target_user.username} updated by Admin.")
                return redirect('view_profile', user_id=user_id)
        
        elif 'add_image' in request.POST:
            if 'image_file' in request.FILES:
                img_url = upload_to_cloudinary(request.FILES['image_file'], folder="srm_match/gallery_images")
                if img_url:
                    ProfileImage.objects.create(profile=profile, image=img_url)
                    messages.success(request, "Gallery photo added by Admin.")
            return redirect('view_profile', user_id=user_id)
            
        elif 'update_pfp_instant' in request.POST:
            if 'profile_pic_file' in request.FILES:
                img_url = upload_to_cloudinary(request.FILES['profile_pic_file'], folder="srm_match/profile_pics")
                if img_url:
                    profile.profile_pic = img_url
                    profile.save()
                    messages.success(request, "Profile picture updated by Admin.")
            return redirect('admin_edit_user_profile', user_id=user_id)

    # If GET, just redirect to a modified version of the edit page or handle it inline
    # For now, let's just reuse the edit_profile template but with the target profile
    form = ProfileEditForm(instance=profile)
    image_form = ProfileImageForm()
    gallery = profile.images.all()
    
    return render(request, "edit_profile.html", {
        "form": form,
        "image_form": image_form,
        "gallery": gallery,
        "profile": profile,
        "is_admin_editing": True
    })
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
            
        url = upload_base64_to_cloudinary(base64_str, folder=f"srm_match/{path}")
        
        if url:
            return JsonResponse({'success': True, 'url': url})
        else:
            return JsonResponse({'success': False, 'message': f'Upload failed.'}, status=500)
            
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

# ==========================================
# ROOM FINDER VIEWS & APIs
# ==========================================
from .models import RoomListing, RoomImage, SavedRoomListing
from django.core.paginator import Paginator

@login_required
def roomfinder_feed(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.name or not profile.age or not profile.gender or not profile.campus or not profile.native_place:
        return redirect('complete_profile')
    
    return render(request, 'roomfinder.html', {'profile': profile})

@login_required
def roomfinder_detail(request, id):
    try:
        listing = RoomListing.objects.get(id=id, is_active=True)
    except RoomListing.DoesNotExist:
        messages.error(request, "Listing not found or is no longer available.")
        return redirect('roomfinder_feed')
    
    is_saved = SavedRoomListing.objects.filter(user=request.user, listing=listing).exists()
    
    return render(request, 'roomfinder_detail.html', {'listing': listing, 'is_saved': is_saved})

@login_required
@csrf_exempt
def api_toggle_save_room(request, id):
    if request.method == 'POST':
        try:
            listing = RoomListing.objects.get(id=id, is_active=True)
            saved_item, created = SavedRoomListing.objects.get_or_create(user=request.user, listing=listing)
            if not created:
                saved_item.delete()
                return JsonResponse({'success': True, 'saved': False, 'message': 'Listing removed from saved.'})
            return JsonResponse({'success': True, 'saved': True, 'message': 'Listing saved to favorites!'})
        except RoomListing.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Listing not found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@login_required
@csrf_exempt
def api_edit_room(request, id):
    if request.method == 'POST':
        try:
            listing = RoomListing.objects.get(id=id)
            # Authorization check
            if not (request.user == listing.user or request.user.is_staff or request.user.email == 'arunmohankml@gmail.com'):
                return JsonResponse({'success': False, 'error': 'Unauthorized to edit this listing.'})
            
            # Update fields
            listing.campus = request.POST.get('campus', listing.campus)
            listing.room_type = request.POST.get('room_type', listing.room_type)
            listing.location = request.POST.get('location', listing.location)
            listing.rent = int(request.POST.get('rent', listing.rent))
            listing.advance = int(request.POST.get('advance', listing.advance))
            listing.gender_preference = request.POST.get('gender_preference', listing.gender_preference)
            listing.furnished_status = request.POST.get('furnished_status', listing.furnished_status)
            listing.current_occupants = int(request.POST.get('current_occupants', listing.current_occupants))
            listing.needed_occupants = int(request.POST.get('needed_occupants', listing.needed_occupants))
            listing.custom_note = request.POST.get('custom_note', listing.custom_note)
            
            contact_info = request.POST.get('contact_info', listing.contact_info)
            # Validate contact info
            cleaned_contact = contact_info.strip()
            is_phone = any(c.isdigit() for c in cleaned_contact) and len([c for c in cleaned_contact if c.isdigit()]) >= 7
            is_insta = ' ' not in cleaned_contact and (cleaned_contact.startswith('@') or len(cleaned_contact) >= 3)
            if not cleaned_contact or not (is_phone or is_insta):
                return JsonResponse({'success': False, 'error': 'Contact info must be a valid phone number or Instagram ID (no spaces).'})
            
            listing.contact_info = cleaned_contact
            listing.save()
            
            new_images = request.FILES.getlist('images')
            if new_images:
                total_existing = listing.images.count()
                for img in new_images[:(5 - total_existing)]:
                    img_url = upload_to_cloudinary(img, folder="srm_match/room_images")
                    if img_url:
                        RoomImage.objects.create(listing=listing, image_url=img_url)
            
            return JsonResponse({'success': True})
        except RoomListing.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Listing not found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@login_required
@csrf_exempt
def api_delete_room(request, id):
    if request.method == 'POST':
        try:
            listing = RoomListing.objects.get(id=id)
            # Authorization check
            if not (request.user == listing.user or request.user.is_staff or request.user.email == 'arunmohankml@gmail.com'):
                return JsonResponse({'success': False, 'error': 'Unauthorized to delete this listing.'})
            
            listing.is_active = False # soft delete
            listing.save()
            return JsonResponse({'success': True})
        except RoomListing.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Listing not found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@csrf_exempt
@login_required
def api_create_room(request):
    if request.method == 'POST':
        # Enforce max 2 listings
        if RoomListing.objects.filter(user=request.user, is_active=True).count() >= 2:
            return JsonResponse({'success': False, 'error': 'You can only have up to 2 active listings.'})
        
        try:
            campus = request.POST.get('campus', '')
            location = request.POST.get('location', '')
            distance_from_campus = request.POST.get('distance_from_campus', '')
            rent = request.POST.get('rent', 0)
            advance = request.POST.get('advance', 0)
            room_type = request.POST.get('room_type', '')
            furnished_status = request.POST.get('furnished_status', '')
            current_occupants = request.POST.get('current_occupants', 0)
            needed_occupants = request.POST.get('needed_occupants', 1)
            gender_preference = request.POST.get('gender_preference', 'any')
            food_preference = request.POST.get('food_preference', '')
            smoking_drinking_preference = request.POST.get('smoking_drinking_preference', '')
            languages_preferred = request.POST.get('languages_preferred', '')
            available_from_date = request.POST.get('available_from_date') or None
            custom_note = request.POST.get('custom_note', '')
            contact_info = request.POST.get('contact_info', '')

            # Validate contact info is a valid phone number or Instagram ID (no spaces)
            cleaned_contact = contact_info.strip()
            is_phone = any(c.isdigit() for c in cleaned_contact) and len([c for c in cleaned_contact if c.isdigit()]) >= 7
            is_insta = ' ' not in cleaned_contact and (cleaned_contact.startswith('@') or len(cleaned_contact) >= 3)
            if not cleaned_contact or not (is_phone or is_insta):
                return JsonResponse({'success': False, 'error': 'Contact info must be a valid phone number or Instagram ID (no spaces).'})


            listing = RoomListing.objects.create(
                user=request.user,
                campus=campus,
                location=location,
                distance_from_campus=distance_from_campus,
                rent=int(rent),
                advance=int(advance),
                room_type=room_type,
                furnished_status=furnished_status,
                current_occupants=int(current_occupants),
                needed_occupants=int(needed_occupants),
                gender_preference=gender_preference,
                food_preference=food_preference,
                smoking_drinking_preference=smoking_drinking_preference,
                languages_preferred=languages_preferred,
                available_from_date=available_from_date,
                custom_note=custom_note,
                contact_info=contact_info
            )
            
            images = request.FILES.getlist('images')
            for img in images[:5]: # Max 5 images
                img_url = upload_to_cloudinary(img, folder="srm_match/room_images")
                if img_url:
                    RoomImage.objects.create(listing=listing, image_url=img_url)
            
            return JsonResponse({'success': True, 'listing_id': listing.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def api_get_rooms(request):
    if request.method == 'GET':
        listings = RoomListing.objects.filter(is_active=True).order_by('-created_at')
        
        # Exclude blocked users for safety
        blocked_ids = set(BlockedUser.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)) | \
                      set(BlockedUser.objects.filter(blocked=request.user).values_list('blocker_id', flat=True))
        if blocked_ids:
            listings = listings.exclude(user_id__in=blocked_ids)
            
        # Filters
        saved_only = request.GET.get('saved_only')
        if saved_only == 'true':
            saved_ids = SavedRoomListing.objects.filter(user=request.user).values_list('listing_id', flat=True)
            listings = listings.filter(id__in=saved_ids)

        campus = request.GET.get('campus')

        if campus:
            listings = listings.filter(campus=campus)
            
        gender = request.GET.get('gender')
        if gender:
            listings = listings.filter(gender_preference=gender)
            
        room_type = request.GET.get('room_type')
        if room_type:
            listings = listings.filter(room_type=room_type)
            
        min_rent = request.GET.get('min_rent')
        if min_rent:
            listings = listings.filter(rent__gte=int(min_rent))
            
        max_rent = request.GET.get('max_rent')
        if max_rent:
            listings = listings.filter(rent__lte=int(max_rent))
            
        furnished = request.GET.get('furnished')
        if furnished:
            listings = listings.filter(furnished_status=furnished)
            
        # Pagination
        page_num = request.GET.get('page', 1)
        paginator = Paginator(listings, 10)
        page = paginator.get_page(page_num)
        
        data = []
        saved_ids = set(SavedRoomListing.objects.filter(user=request.user).values_list('listing_id', flat=True))
        for lst in page.object_list:
            images = [img.image_url for img in lst.images.all()]
            
            # Simple compatibility score mock (randomized per user for now, or based on overlap)
            # You can enhance this by comparing lst.user.profile and request.user.profile
            compatibility = 85
            
            profile = lst.user.profile
            data.append({
                'id': lst.id,
                'campus': lst.campus,
                'location': lst.location,
                'distance': lst.distance_from_campus,
                'rent': lst.rent,
                'room_type': lst.get_room_type_display(),
                'furnished_status': lst.get_furnished_status_display(),
                'current_occupants': lst.current_occupants,
                'needed_occupants': lst.needed_occupants,
                'gender_preference': lst.get_gender_preference_display(),
                'images': images,
                 'is_owner': lst.user == request.user,
                'poster': {
                    'id': lst.user.id,
                    'name': profile.name,
                    'pic': profile.get_profile_pic_url,
                    'course': profile.course,
                    'year': profile.clg_year,
                    'is_verified': profile.is_face_verified
                },
                'compatibility': compatibility,
                'is_saved': lst.id in saved_ids,
                'created_at': lst.created_at.strftime("%b %d, %Y")
            })
            
        return JsonResponse({'success': True, 'listings': data, 'has_next': page.has_next()})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@csrf_exempt
@login_required
def api_get_or_create_conversation(request):
    if request.method == 'POST':
        try:
            import json
            if request.headers.get('Content-Type') == 'application/json' or (request.body and b'{' in request.body):
                try:
                    data = json.loads(request.body)
                except Exception:
                    data = request.POST
            else:
                data = request.POST

            other_user_id = data.get('other_user_id')
            if not other_user_id:
                return JsonResponse({'success': False, 'error': 'Missing other_user_id.'})
            
            other_user_id = int(other_user_id)
            if other_user_id == request.user.id:
                return JsonResponse({'success': False, 'error': 'You cannot chat with yourself.'})
            
            other_user = get_object_or_404(User, id=other_user_id)
            source = data.get('source', 'roomie')
            listing_id = data.get('listing_id')
            request_id = data.get('request_id')
            
            u1, u2 = (request.user, other_user) if request.user.id < other_user.id else (other_user, request.user)
            
            conv, conv_created = Conversation.objects.get_or_create(
                user1=u1,
                user2=u2,
                defaults={
                    'source': source,
                    'listing_id': int(listing_id) if listing_id else None,
                    'request_id': int(request_id) if request_id else None,
                }
            )
            
            match_req = MatchRequest.objects.filter(
                Q(sender=request.user, receiver=other_user) |
                Q(sender=other_user, receiver=request.user)
            ).first()
            
            if match_req:
                if match_req.status != 'accepted':
                    match_req.status = 'accepted'
                    match_req.save()
            else:
                MatchRequest.objects.create(
                    sender=request.user,
                    receiver=other_user,
                    status='accepted'
                )
                
            return JsonResponse({
                'success': True,
                'conversation_id': other_user.id,
                'partner_id': other_user.id
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@csrf_exempt
@login_required
def api_create_room_request(request):
    if request.method == 'POST':
        try:
            profile = getattr(request.user, 'profile', None)
            if not profile:
                return JsonResponse({'success': False, 'error': 'Profile not found.'})
            
            # Check profile completeness for languages, mother_tongues, native_place
            langs = profile.languages_list
            mts = profile.mother_tongues_list
            np = profile.native_place.strip() if profile.native_place else ""
            
            if not langs or not mts or not np:
                return JsonResponse({
                    'success': False,
                    'error': 'profile_incomplete',
                    'message': 'Please complete your mother tongue, languages spoken, and native place in your profile before posting a Room Request.'
                })
            
            import json
            if request.headers.get('Content-Type') == 'application/json' or (request.body and b'{' in request.body):
                try:
                    data = json.loads(request.body)
                except Exception:
                    data = request.POST
            else:
                data = request.POST
                
            title = data.get('title', '').strip()
            campus = data.get('campus', '').strip()
            looking_near = data.get('looking_near', '').strip()
            min_rent = data.get('min_rent', '0').strip()
            max_rent = data.get('max_rent', '0').strip()
            preferred_room_type = data.get('preferred_room_type', '').strip()
            sharing_preference = data.get('sharing_preference', '').strip()
            needed_amenities = data.get('needed_amenities', '').strip() # comma separated
            move_in_date = data.get('move_in_date', '').strip()
            extra_note = data.get('extra_note', '').strip()
            
            if not title or len(title) > 70:
                return JsonResponse({'success': False, 'error': 'Title must be between 1 and 70 characters.'})
            if not campus:
                return JsonResponse({'success': False, 'error': 'Campus is required.'})
            if not looking_near:
                return JsonResponse({'success': False, 'error': 'Looking near is required.'})
            if not min_rent or not max_rent:
                return JsonResponse({'success': False, 'error': 'Budget range is required.'})
            if not preferred_room_type:
                return JsonResponse({'success': False, 'error': 'Preferred room type is required.'})
            if not sharing_preference:
                return JsonResponse({'success': False, 'error': 'Sharing preference is required.'})
            if not move_in_date:
                return JsonResponse({'success': False, 'error': 'Move-in date is required.'})
            if len(extra_note) > 110:
                return JsonResponse({'success': False, 'error': 'Extra note must be at most 110 characters.'})
                
            req = RoomRequest.objects.create(
                user=request.user,
                title=title,
                campus=campus,
                looking_near=looking_near,
                min_rent=int(min_rent),
                max_rent=int(max_rent),
                preferred_room_type=preferred_room_type,
                sharing_preference=sharing_preference,
                needed_amenities=needed_amenities,
                move_in_date=move_in_date,
                extra_note=extra_note
            )
            return JsonResponse({'success': True, 'request_id': req.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@login_required
def api_get_room_requests(request):
    if request.method == 'GET':
        reqs = RoomRequest.objects.filter(is_active=True).order_by('-created_at')
        
        # Exclude blocked users for safety
        blocked_ids = set(BlockedUser.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)) | \
                      set(BlockedUser.objects.filter(blocked=request.user).values_list('blocker_id', flat=True))
        if blocked_ids:
            reqs = reqs.exclude(user_id__in=blocked_ids)
            
        # Filters
        campus = request.GET.get('campus')
        if campus:
            reqs = reqs.filter(campus=campus)
            
        min_rent = request.GET.get('min_rent')
        if min_rent:
            reqs = reqs.filter(max_rent__gte=int(min_rent))
            
        max_rent = request.GET.get('max_rent')
        if max_rent:
            reqs = reqs.filter(min_rent__lte=int(max_rent))
            
        gender = request.GET.get('gender')
        if gender:
            reqs = reqs.filter(user__profile__gender=gender)
            
        room_type = request.GET.get('room_type')
        if room_type:
            reqs = reqs.filter(preferred_room_type=room_type)
            
        amenity = request.GET.get('amenity')
        if amenity:
            reqs = reqs.filter(needed_amenities__icontains=amenity)
            
        mother_tongue = request.GET.get('mother_tongue')
        if mother_tongue:
            reqs = reqs.filter(user__profile__mother_tongues__icontains=mother_tongue)
            
        # Pagination
        page_num = request.GET.get('page', 1)
        paginator = Paginator(reqs, 10)
        page = paginator.get_page(page_num)
        
        data = []
        for r in page.object_list:
            profile = r.user.profile
            gender_char = 'M' if profile.gender == 'male' else 'F' if profile.gender == 'female' else 'O'
            gender_age = f"{profile.age or ''}{gender_char}"
            
            data.append({
                'id': r.id,
                'title': r.title,
                'campus': r.campus,
                'looking_near': r.looking_near,
                'min_rent': r.min_rent,
                'max_rent': r.max_rent,
                'preferred_room_type': r.preferred_room_type,
                'sharing_preference': r.sharing_preference,
                'needed_amenities': r.needed_amenities,
                'move_in_date': r.move_in_date.strftime("%b %d, %Y") if r.move_in_date else '',
                'extra_note': r.extra_note,
                'created_at': r.created_at.strftime("%b %d, %Y"),
                'is_owner': r.user == request.user,
                'is_admin': request.user.is_staff or request.user.email == 'arunmohankml@gmail.com',
                'user': {
                    'id': r.user.id,
                    'name': profile.name,
                    'pic': profile.get_profile_pic_url,
                    'gender_age': gender_age,
                    'mother_tongue': profile.mother_tongues,
                    'languages': profile.languages,
                    'native_place': profile.native_place,
                    'is_verified': profile.is_face_verified
                }
            })
            
        return JsonResponse({'success': True, 'requests': data, 'has_next': page.has_next()})
        
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@csrf_exempt
@login_required
def api_delete_room_request(request, id):
    if request.method == 'POST':
        try:
            req = RoomRequest.objects.get(id=id)
            if not (request.user == req.user or request.user.is_staff or request.user.email == 'arunmohankml@gmail.com'):
                return JsonResponse({'success': False, 'error': 'Unauthorized.'})
                
            req.is_active = False # soft delete
            req.save()
            return JsonResponse({'success': True})
        except RoomRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Request not found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@csrf_exempt
@login_required
def api_edit_room_request(request, id):
    if request.method == 'POST':
        try:
            req = RoomRequest.objects.get(id=id, is_active=True)
            if not (request.user == req.user or request.user.is_staff or request.user.email == 'arunmohankml@gmail.com'):
                return JsonResponse({'success': False, 'error': 'Unauthorized.'})
            
            import json
            if request.headers.get('Content-Type') == 'application/json' or (request.body and b'{' in request.body):
                try:
                    data = json.loads(request.body)
                except Exception:
                    data = request.POST
            else:
                data = request.POST
            
            title = data.get('title', '').strip()
            if title and len(title) <= 70:
                req.title = title
            
            campus = data.get('campus', '').strip()
            if campus:
                req.campus = campus
            
            looking_near = data.get('looking_near', '').strip()
            if looking_near:
                req.looking_near = looking_near
            
            min_rent = data.get('min_rent', '').strip()
            if min_rent:
                req.min_rent = int(min_rent)
            
            max_rent = data.get('max_rent', '').strip()
            if max_rent:
                req.max_rent = int(max_rent)
            
            preferred_room_type = data.get('preferred_room_type', '').strip()
            if preferred_room_type:
                req.preferred_room_type = preferred_room_type
            
            sharing_preference = data.get('sharing_preference', '').strip()
            if sharing_preference:
                req.sharing_preference = sharing_preference
            
            needed_amenities = data.get('needed_amenities', '').strip()
            req.needed_amenities = needed_amenities
            
            move_in_date = data.get('move_in_date', '').strip()
            if move_in_date:
                req.move_in_date = move_in_date
            
            extra_note = data.get('extra_note', '').strip()
            if len(extra_note) <= 110:
                req.extra_note = extra_note
            
            req.save()
            return JsonResponse({'success': True})
        except RoomRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Request not found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@login_required
def roomrequest_detail(request, id):
    try:
        req = RoomRequest.objects.get(id=id, is_active=True)
    except RoomRequest.DoesNotExist:
        messages.error(request, "Room request not found or has been deleted.")
        return redirect('roomfinder_feed')
    
    profile = req.user.profile
    is_owner = request.user == req.user
    is_admin = request.user.is_staff or request.user.email == 'arunmohankml@gmail.com'
    
    return render(request, 'roomrequest_detail.html', {
        'req': req,
        'profile': profile,
        'is_owner': is_owner,
        'is_admin': is_admin,
    })

