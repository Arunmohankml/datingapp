from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.http import JsonResponse
import json
from firebase_admin import auth as firebase_auth
from django.views.decorators.csrf import csrf_exempt

from .models import Profile, Question, Option, UserAnswer, MatchRequest, Message
from .forms import ProfileForm
from django.db.models import Q


# ---------------- PROFILE SETUP ----------------
@login_required
def complete_profile(request):
    user = request.user

    # Try fetching existing profile, else None
    profile = getattr(user, 'profile', None)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            new_profile = form.save(commit=False)
            new_profile.user = user
            new_profile.save()
            return redirect('home')
        # If form is invalid, fall through to re-render with errors
    else:
        form = ProfileForm(instance=profile)

    # BUG FIX: was incorrectly rendering home.html — must render complete_profile.html
    return render(request, 'complete_profile.html', {'form': form})

# ---------------- HOME / QUIZ ----------------
@login_required
def home(request):
    user = request.user

    # Ensure user has a completed profile
    profile, created = Profile.objects.get_or_create(user=user)
    if not profile.name:
        return redirect('complete_profile')

    # Get answered questions count
    answered_ids = list(UserAnswer.objects.filter(user=user).values_list("question_id", flat=True))
    ans_count = len(answered_ids)

    # ── 4-question round break ──
    # Round number = how many complete 4-question rounds the user has finished
    # We use session to track how many rounds we've already shown a match for
    rounds_shown = request.session.get('rounds_shown', 0)
    current_round = ans_count // 4  # integer division: 4→1, 8→2, 12→3 ...

    if current_round > rounds_shown:
        # A new round has been completed — show a match
        request.session['rounds_shown'] = current_round
        return redirect('check_match')

    question = Question.objects.exclude(id__in=answered_ids).first()

    if not question:
        # All questions answered
        return render(request, "home.html", {"all_done": True, "progress": 100})

    total_q_db = Question.objects.count()
    progress = int((ans_count / total_q_db) * 100) if total_q_db > 0 else 0

    return render(request, "home.html", {"question": question, "progress": progress})


import numpy as np

# ---------------- MATCHING LOGIC ----------------
def calculate_match_score(user1, user2):
    """Calculate match % between two users based on answers using Cosine Similarity and Euclidean distance"""
    user1_answers = UserAnswer.objects.filter(user=user1).select_related('option')
    user2_answers = UserAnswer.objects.filter(user=user2).select_related('option')
    
    user1_dict = {ans.question_id: ans.option.weight for ans in user1_answers}
    user2_dict = {ans.question_id: ans.option.weight for ans in user2_answers}
    
    common_questions = set(user1_dict.keys()).intersection(set(user2_dict.keys()))
    
    if not common_questions:
        return 0
    
    v1 = np.array([user1_dict[q_id] for q_id in common_questions])
    v2 = np.array([user2_dict[q_id] for q_id in common_questions])
    
    # Euclidean distance
    euc_dist = np.linalg.norm(v1 - v2)
    euc_sim = 1 / (1 + euc_dist)
    
    # Cosine Similarity
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    if norm_v1 == 0 and norm_v2 == 0:
        cos_sim = 1.0
    elif norm_v1 == 0 or norm_v2 == 0:
        cos_sim = 0.0
    else:
        cos_sim = np.dot(v1, v2) / (norm_v1 * norm_v2)
        
    # Map [-1, 1] to [0, 1]
    normalized_cos_sim = (cos_sim + 1) / 2
    
    # Blended Score: 60% Euclidean, 40% Cosine
    combined_score = (0.6 * euc_sim + 0.4 * normalized_cos_sim) * 100
    
    return int(combined_score)


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

    # IDs of users already shown to this user in previous rounds (stored in session)
    seen_ids = request.session.get('seen_match_ids', [])

    # ── Step 1: Filter candidates by mutual preference ──
    candidates = Profile.objects.exclude(user=user).exclude(user__id__in=seen_ids)

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

    # Fall back to all unseen candidates if no one passes preference filter
    if not preference_filtered:
        preference_filtered = list(candidates)

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
        return render(request, "match_popup.html", {
            "match": best_match,
            "score": best_score
        })

    # No one left to show — reset seen list and send back to quiz
    request.session['seen_match_ids'] = []
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
        try:
            data = json.loads(request.body)
            id_token = data.get('idToken')
            decoded_token = firebase_auth.verify_id_token(id_token)
            email = decoded_token.get('email', '')
            
            # if not email.endswith('@srmist.edu.in'):
            #     return JsonResponse({'success': False, 'error': 'Only @srmist.edu.in emails are allowed.'}, status=403)
            
            # Get or create user
            user, created = User.objects.get_or_create(username=email, defaults={'email': email})
            
            # Log the user in
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            return JsonResponse({'success': True})
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
    
    connected_users = []
    for req in accepted_sent:
        connected_users.append(req.receiver)
    for req in accepted_received:
        connected_users.append(req.sender)
        
    chats = []
    for partner in connected_users:
        latest_msg = Message.objects.filter(
            Q(sender=user, receiver=partner) | Q(sender=partner, receiver=user)
        ).order_by('-timestamp').first()
        
        unread_count = Message.objects.filter(sender=partner, receiver=user, is_read=False).count()
        
        chats.append({
            'partner': partner,
            'latest_message': latest_msg,
            'unread_count': unread_count,
            'timestamp': latest_msg.timestamp if latest_msg else None
        })
        
    # Sort so that chats with the most recent messages appear first
    chats.sort(key=lambda x: x['timestamp'].timestamp() if x['timestamp'] else 0, reverse=True)
    
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
            except json.JSONDecodeError:
                text = None
        else:
            text = request.POST.get('text')
            
        if text:
            msg = Message.objects.create(sender=request.user, receiver=partner, text=text)
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': {
                        'id': msg.id,
                        'text': msg.text,
                        'sender_id': msg.sender_id,
                        'timestamp': msg.timestamp.strftime("%H:%M")
                    }
                })
            return redirect('chat_view', partner_id=partner.id)
            
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Empty message'}, status=400)
            
    messages = Message.objects.filter(
        Q(sender=request.user, receiver=partner) |
        Q(sender=partner, receiver=request.user)
    ).order_by('timestamp')
    
    # Mark messages as read
    Message.objects.filter(sender=partner, receiver=request.user, is_read=False).update(is_read=True)
    
    return render(request, 'chat.html', {
        'partner': partner,
        'messages': messages
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
        
    messages = Message.objects.filter(
        Q(sender=request.user, receiver=partner) |
        Q(sender=partner, receiver=request.user)
    ).order_by('timestamp')
    
    # Mark incoming unread messages as read
    Message.objects.filter(sender=partner, receiver=request.user, is_read=False).update(is_read=True)
    
    msg_list = []
    for msg in messages:
        msg_list.append({
            'id': msg.id,
            'text': msg.text,
            'sender_id': msg.sender_id,
            'timestamp': msg.timestamp.strftime("%H:%M")
        })
        
    return JsonResponse({'messages': msg_list})
