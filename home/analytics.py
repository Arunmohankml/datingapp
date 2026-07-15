from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import timedelta, datetime
from .models import (
    User, Profile, MatchRequest, Message, Confession, ConfessionComment,
    ConfessionLike, ConfessionReport, UserReport, Spark, BlockedUser,
    RoomListing, RoomRequest, SavedRoomListing, Conversation, VoiceRoom,
    VoiceParticipant, GiveawayEntry, FCMToken, ProfileImage, Announcement,
    BannedIdentifier,
)
from django.contrib.auth.models import User as AuthUser

TODAY = timezone.now().date()
NOW = timezone.now()

def _days(n):
    return TODAY - timedelta(days=n)

def _start_of(period):
    if period == '5m':
        return timezone.now() - timedelta(minutes=5)
    if period == 'today':
        return timezone.make_aware(datetime.combine(TODAY, datetime.min.time()))
    if period == '7d':
        return timezone.make_aware(datetime.combine(_days(7), datetime.min.time()))
    if period == '30d':
        return timezone.make_aware(datetime.combine(_days(30), datetime.min.time()))
    if period == '90d':
        return timezone.make_aware(datetime.combine(_days(90), datetime.min.time()))
    if period == '1y':
        return timezone.make_aware(datetime.combine(_days(365), datetime.min.time()))
    return datetime(2020, 1, 1, tzinfo=timezone.get_current_timezone())

def _count(queryset):
    return queryset.count()

def _pct(part, total):
    if not total:
        return 0
    return round((part / total) * 100, 1)

def _change(current, previous):
    if previous == 0:
        return 0
    return round(((current - previous) / previous) * 100, 1)

# ─────────────────────────────────────────────
#  OVERVIEW
# ─────────────────────────────────────────────

def overview():
    users = AuthUser.objects.all()
    profiles = Profile.objects.all()
    total_users = _count(users)
    verified = _count(profiles.filter(verification_status='verified'))
    face_verified = _count(profiles.filter(is_face_verified=True))
    discoverable = _count(profiles.filter(is_discoverable=True))
    banned = _count(profiles.filter(is_banned=True))

    dau = _count(users.filter(last_login__gte=_start_of('today')))
    wau = _count(users.filter(last_login__gte=_start_of('7d')))
    mau = _count(users.filter(last_login__gte=_start_of('30d')))

    new_today = _count(users.filter(date_joined__gte=_start_of('today')))
    new_week = _count(users.filter(date_joined__gte=_start_of('7d')))
    new_month = _count(users.filter(date_joined__gte=_start_of('30d')))

    matches = MatchRequest.objects.filter(status='accepted')
    total_matches = _count(matches)
    matches_today = _count(matches.filter(created_at__gte=_start_of('today')))

    messages = Message.objects.all()
    total_msgs = _count(messages)
    msgs_today = _count(messages.filter(timestamp__gte=_start_of('today')))

    confessions = Confession.objects.all()
    total_conf = _count(confessions)
    conf_today = _count(confessions.filter(created_at__gte=_start_of('today')))

    voice_joins_today = _count(VoiceParticipant.objects.filter(joined_at__gte=_start_of('today')))

    listings = _count(RoomListing.objects.filter(is_active=True))
    requests = _count(RoomRequest.objects.filter(is_active=True))

    # Previous period comparisons
    prev_start = _start_of('7d') - timedelta(days=7)
    prev_end = _start_of('7d')
    prev_new = _count(users.filter(date_joined__gte=prev_start, date_joined__lt=prev_end))

    return {
        'total_users': total_users,
        'total_verified': verified,
        'total_face_verified': face_verified,
        'total_active_users': discoverable,
        'dau': dau,
        'wau': wau,
        'mau': mau,
        'new_users_today': new_today,
        'new_users_week': new_week,
        'new_users_month': new_month,
        'new_users_change': _change(new_week, prev_new),
        'total_matches': total_matches,
        'matches_today': matches_today,
        'total_messages': total_msgs,
        'messages_today': msgs_today,
        'total_confessions': total_conf,
        'confessions_today': conf_today,
        'voice_joins_today': voice_joins_today,
        'total_listings': listings,
        'total_requests': requests,
    }

# ─────────────────────────────────────────────
#  USER ANALYTICS
# ─────────────────────────────────────────────

def user_analytics():
    profiles = Profile.objects.all()
    total = _count(profiles)

    gender = {}
    for g, label in [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]:
        cnt = _count(profiles.filter(gender=g))
        gender[label] = {'count': cnt, 'pct': _pct(cnt, total)}

    age_groups = {}
    for age in range(18, 23):
        cnt = _count(profiles.filter(age=age))
        age_groups[str(age)] = cnt
    age_groups['23+'] = _count(profiles.filter(age__gte=23))
    avg_age = profiles.filter(age__isnull=False).aggregate(a=Avg('age'))['a']
    age_groups['avg'] = round(avg_age, 1) if avg_age else 0

    campus_qs = profiles.values('campus').annotate(cnt=Count('id')).filter(campus__gt='').order_by('-cnt')
    campus = [{'name': c['campus'], 'count': c['cnt'], 'pct': _pct(c['cnt'], total)} for c in campus_qs]

    course_qs = profiles.values('course').annotate(cnt=Count('id')).filter(course__gt='').order_by('-cnt')[:20]
    course = [{'name': c['course'], 'count': c['cnt']} for c in course_qs]

    native = _text_field_distribution(profiles, 'native_place', total)
    living = _text_field_distribution(profiles, 'living_place', total)
    languages = _text_field_distribution(profiles, 'languages', total, split=True)
    mother_tongues = _text_field_distribution(profiles, 'mother_tongues', total, split=True)

    looking = {}
    for lf, label in [('friendship', 'Friendship'), ('serious', 'Relationship'), ('vibe', 'Just Vibing')]:
        cnt = _count(profiles.filter(looking_for=lf))
        looking[label] = {'count': cnt, 'pct': _pct(cnt, total)}

    verif = {}
    for vs, label in [('verified', 'Verified'), ('pending', 'Pending'), ('rejected', 'Rejected'), ('manual_review', 'Manual Review')]:
        cnt = _count(profiles.filter(verification_status=vs))
        verif[label] = cnt

    discoverable = _count(profiles.filter(is_discoverable=True))

    return {
        'gender': gender,
        'total': total,
        'age_groups': age_groups,
        'campus': campus,
        'course': course,
        'native_place': native,
        'living_place': living,
        'languages': languages,
        'mother_tongues': mother_tongues,
        'looking_for': looking,
        'verification': verif,
        'discoverable': discoverable,
        'hidden': total - discoverable,
    }

def _text_field_distribution(qs, field, total, split=False):
    items = {}
    for p in qs.filter(**{f'{field}__gt': ''}).only(field):
        val = getattr(p, field) or ''
        if split:
            parts = [v.strip() for v in val.split(',') if v.strip()]
            for part in parts:
                items[part] = items.get(part, 0) + 1
        else:
            items[val] = items.get(val, 0) + 1
    sorted_items = sorted(items.items(), key=lambda x: -x[1])[:20]
    return [{'name': k, 'count': v, 'pct': _pct(v, total)} for k, v in sorted_items]

# ─────────────────────────────────────────────
#  GROWTH
# ─────────────────────────────────────────────

def growth(period='30d'):
    since = _start_of(period)
    users = AuthUser.objects.filter(date_joined__gte=since)
    
    if period == 'today':
        days = 1
        group_by = 'hour'
    elif period == '7d':
        days = 7
        group_by = 'day'
    elif period == '30d':
        days = 30
        group_by = 'day'
    elif period == '90d':
        days = 90
        group_by = 'week'
    else:
        days = 365
        group_by = 'month'

    # Daily/ weekly/ monthly new user counts
    from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncHour
    trunc_map = {
        'hour': TruncDay,  # group by day for today
        'day': TruncDay,
        'week': TruncWeek,
        'month': TruncMonth,
    }
    
    if period == 'today':
        # By hour
        data_points = []
        for h in range(24):
            hr_start = timezone.make_aware(datetime.combine(TODAY, datetime.min.time().replace(hour=h)))
            hr_end = hr_start + timedelta(hours=1)
            c = _count(users.filter(date_joined__gte=hr_start, date_joined__lt=hr_end))
            data_points.append({'label': f'{h}:00', 'count': c})
        return data_points

    trunc = trunc_map[group_by]
    raw = (users.annotate(period=trunc('date_joined'))
            .values('period')
            .annotate(count=Count('id'))
            .order_by('period'))
    
    labels = [r['period'].strftime('%Y-%m-%d') if hasattr(r['period'], 'strftime') else str(r['period']) for r in raw]
    counts = [r['count'] for r in raw]
    return {'labels': labels, 'counts': counts}

# ─────────────────────────────────────────────
#  ENGAGEMENT
# ─────────────────────────────────────────────

def engagement():
    users = AuthUser.objects.all()
    profiles = Profile.objects.all()
    total_users = max(_count(users), 1)
    
    dau = _count(users.filter(last_login__gte=_start_of('today')))
    wau = _count(users.filter(last_login__gte=_start_of('7d')))
    mau = _count(users.filter(last_login__gte=_start_of('30d')))

    total_msgs = _count(Message.objects.all())
    total_matches = _count(MatchRequest.objects.filter(status='accepted'))
    
    img_count = _count(ProfileImage.objects.all())
    profiles_with_photos = _count(profiles.annotate(img_cnt=Count('images')).filter(img_cnt__gt=0))
    profiles_with_bio = _count(profiles.filter(bio__gt=''))
    
    # Completion: fields that indicate a complete profile
    completion_fields = ['profile_pic', 'bio', 'living_place', 'native_place', 'course', 'clg_year', 'interest_tags']
    total_completion = 0
    for p in profiles.all():
        score = 0
        if p.profile_pic: score += 1
        if p.bio and p.bio.strip(): score += 1
        if p.living_place and p.living_place.strip(): score += 1
        if p.native_place and p.native_place.strip(): score += 1
        if p.course and p.course.strip(): score += 1
        if p.clg_year: score += 1
        if p.interest_tags and p.interest_tags.strip(): score += 1
        total_completion += (score / len(completion_fields)) * 100
    avg_completion = round(total_completion / max(_count(profiles), 1), 1)

    conversations = Conversation.objects.all()
    conv_count = _count(conversations)

    # Session count approximation: number of logins tracked via last_login updates
    # We approximate by how many users have logged in recently
    
    return {
        'dau': dau,
        'wau': wau,
        'mau': mau,
        'avg_messages_per_user': round(total_msgs / total_users, 1),
        'avg_matches_per_user': round(total_matches / total_users, 2),
        'avg_completion': avg_completion,
        'avg_photos': round(img_count / max(profiles_with_photos, 1), 1),
        'active_conversations': conv_count,
        'profiles_with_photos': profiles_with_photos,
        'profiles_with_bio': profiles_with_bio,
        'total_users': total_users,
    }

# ─────────────────────────────────────────────
#  FEATURE USAGE
# ─────────────────────────────────────────────

def feature_usage():
    """Rank features by estimated unique users / visits."""
    features = []
    
    # Chat
    chat_users = (Message.objects.values('sender')
                  .annotate(cnt=Count('id')).order_by())
    chat_today = _count(Message.objects.filter(timestamp__gte=_start_of('today')))
    chat_week = _count(Message.objects.filter(timestamp__gte=_start_of('7d')))
    chat_month = _count(Message.objects.filter(timestamp__gte=_start_of('30d')))
    features.append({
        'name': 'Chat', 'icon': 'chat', 'unique_users': chat_users.count(),
        'total': _count(Message.objects.all()),
        'today': chat_today, 'week': chat_week, 'month': chat_month,
    })
    
    # Match Feed (based on match requests)
    match_users = (MatchRequest.objects.values('sender')
                   .annotate(cnt=Count('id')).order_by())
    match_today = _count(MatchRequest.objects.filter(created_at__gte=_start_of('today')))
    match_week = _count(MatchRequest.objects.filter(created_at__gte=_start_of('7d')))
    match_month = _count(MatchRequest.objects.filter(created_at__gte=_start_of('30d')))
    features.append({
        'name': 'Match Feed', 'icon': 'favorite', 'unique_users': match_users.count(),
        'total': _count(MatchRequest.objects.all()),
        'today': match_today, 'week': match_week, 'month': match_month,
    })
    
    # Confessions
    conf_users = (Confession.objects.values('user').distinct().count())
    conf_today = _count(Confession.objects.filter(created_at__gte=_start_of('today')))
    conf_week = _count(Confession.objects.filter(created_at__gte=_start_of('7d')))
    conf_month = _count(Confession.objects.filter(created_at__gte=_start_of('30d')))
    features.append({
        'name': 'Confessions', 'icon': 'mask', 'unique_users': conf_users,
        'total': _count(Confession.objects.all()),
        'today': conf_today, 'week': conf_week, 'month': conf_month,
    })
    
    # Voice Rooms
    voice_users = (VoiceParticipant.objects.values('user').distinct().count())
    voice_today = _count(VoiceParticipant.objects.filter(joined_at__gte=_start_of('today')))
    voice_week = _count(VoiceParticipant.objects.filter(joined_at__gte=_start_of('7d')))
    voice_month = _count(VoiceParticipant.objects.filter(joined_at__gte=_start_of('30d')))
    features.append({
        'name': 'Voice Rooms', 'icon': 'headset_mic', 'unique_users': voice_users,
        'total': _count(VoiceParticipant.objects.all()),
        'today': voice_today, 'week': voice_week, 'month': voice_month,
    })
    
    # Room Finder
    room_users = (RoomListing.objects.values('user').distinct().count())
    room_today = _count(RoomListing.objects.filter(created_at__gte=_start_of('today')))
    room_week = _count(RoomListing.objects.filter(created_at__gte=_start_of('7d')))
    room_month = _count(RoomListing.objects.filter(created_at__gte=_start_of('30d')))
    features.append({
        'name': 'Room Finder', 'icon': 'home', 'unique_users': room_users,
        'total': _count(RoomListing.objects.all()),
        'today': room_today, 'week': room_week, 'month': room_month,
    })
    
    # Giveaway
    giveaway_users = _count(GiveawayEntry.objects.all())
    features.append({
        'name': 'Giveaway', 'icon': 'card_giftcard', 'unique_users': giveaway_users,
        'total': giveaway_users, 'today': 0, 'week': 0, 'month': 0,
    })
    
    # Sparks
    spark_users = (Spark.objects.values('sender').distinct().count())
    spark_today = _count(Spark.objects.filter(created_at__gte=_start_of('today')))
    spark_week = _count(Spark.objects.filter(created_at__gte=_start_of('7d')))
    spark_month = _count(Spark.objects.filter(created_at__gte=_start_of('30d')))
    features.append({
        'name': 'Sparks', 'icon': 'local_fire_department', 'unique_users': spark_users,
        'total': _count(Spark.objects.all()),
        'today': spark_today, 'week': spark_week, 'month': spark_month,
    })
    
    features.sort(key=lambda f: -f['total'])
    for i, f in enumerate(features, 1):
        f['rank'] = i
    return features

# ─────────────────────────────────────────────
#  MATCHING ANALYTICS
# ─────────────────────────────────────────────

def matching_analytics():
    all_reqs = MatchRequest.objects.all()
    total = _count(all_reqs)
    accepted = _count(all_reqs.filter(status='accepted'))
    rejected = _count(all_reqs.filter(status='rejected'))
    pending = _count(all_reqs.filter(status='pending'))
    skipped = _count(all_reqs.filter(status='skipped'))
    
    sparks = Spark.objects.all()
    sparks_sent = _count(sparks)
    
    return {
        'total': total,
        'accepted': accepted,
        'rejected': rejected,
        'pending': pending,
        'skipped': skipped,
        'acceptance_rate': _pct(accepted, total),
        'rejection_rate': _pct(rejected, total),
        'conversion_rate': _pct(accepted, accepted + rejected) if (accepted + rejected) > 0 else 0,
        'sparks_sent': sparks_sent,
    }

# ─────────────────────────────────────────────
#  CHAT ANALYTICS
# ─────────────────────────────────────────────

def chat_analytics():
    msgs = Message.objects.all()
    today_msgs = _count(msgs.filter(timestamp__gte=_start_of('today')))
    week_msgs = _count(msgs.filter(timestamp__gte=_start_of('7d')))
    month_msgs = _count(msgs.filter(timestamp__gte=_start_of('30d')))
    total = _count(msgs)
    
    conversations = Conversation.objects.all()
    conv_count = _count(conversations)
    avg_per_conv = round(total / max(conv_count, 1), 1)
    
    # Most active users
    active = (msgs.values('sender__username')
              .annotate(cnt=Count('id'))
              .order_by('-cnt')[:10])
    most_active_users = [{'name': a['sender__username'] or 'Unknown', 'count': a['cnt']} for a in active]
    
    # Message growth (last 30 days)
    from django.db.models.functions import TruncDate
    growth_data = (msgs.filter(timestamp__gte=_start_of('30d'))
                   .annotate(d=TruncDate('timestamp'))
                   .values('d')
                   .annotate(c=Count('id'))
                   .order_by('d'))
    msg_chart = {
        'labels': [g['d'].strftime('%m/%d') for g in growth_data],
        'counts': [g['c'] for g in growth_data],
    }
    
    return {
        'today': today_msgs,
        'week': week_msgs,
        'month': month_msgs,
        'total': total,
        'conversations': conv_count,
        'avg_per_conversation': avg_per_conv,
        'most_active_users': most_active_users,
        'growth_chart': msg_chart,
    }

# ─────────────────────────────────────────────
#  VOICE ROOM ANALYTICS
# ─────────────────────────────────────────────

def voice_analytics():
    rooms = VoiceRoom.objects.all()
    total_rooms = _count(rooms)
    
    # Active = has participants recently
    active_rooms = _count(rooms.filter(participants__last_heartbeat__gte=_start_of('5m')))
    
    joins = VoiceParticipant.objects.all()
    today_joins = _count(joins.filter(joined_at__gte=_start_of('today')))
    week_joins = _count(joins.filter(joined_at__gte=_start_of('7d')))
    month_joins = _count(joins.filter(joined_at__gte=_start_of('30d')))
    
    # Peak concurrent: max participants at any time (approximate with current count)
    peak = 0
    for r in rooms:
        c = _count(r.participants.filter(last_heartbeat__gte=_start_of('5m')))
        if c > peak:
            peak = c
    
    # Most popular rooms
    popular = []
    for r in rooms:
        cnt = _count(r.participants.all())
        if cnt > 0:
            popular.append({'name': r.name, 'count': cnt, 'slug': r.slug})
    popular.sort(key=lambda x: -x['count'])
    
    return {
        'total_rooms': total_rooms,
        'active_rooms': active_rooms,
        'joins_today': today_joins,
        'joins_week': week_joins,
        'joins_month': month_joins,
        'peak_concurrent': peak,
        'popular_rooms': popular,
    }

# ─────────────────────────────────────────────
#  CONFESSION ANALYTICS
# ─────────────────────────────────────────────

def confession_analytics():
    posts = Confession.objects.all()
    total = _count(posts)
    today = _count(posts.filter(created_at__gte=_start_of('today')))
    week = _count(posts.filter(created_at__gte=_start_of('7d')))
    month = _count(posts.filter(created_at__gte=_start_of('30d')))
    
    comments = ConfessionComment.objects.all()
    comments_today = _count(comments.filter(created_at__gte=_start_of('today')))
    total_comments = _count(comments)
    
    total_likes = _count(ConfessionLike.objects.all())
    reports = _count(ConfessionReport.objects.all())
    flagged = _count(posts.filter(is_flagged=True))
    pending_review = _count(posts.filter(moderation_status='pending_review'))
    rejected = _count(posts.filter(moderation_status='rejected'))
    
    most_liked = posts.order_by('-likes_count')[:5]
    most_liked_list = [{'id': c.id, 'content': c.content[:80], 'likes': c.likes_count} for c in most_liked]
    
    return {
        'total': total,
        'today': today,
        'week': week,
        'month': month,
        'comments_today': comments_today,
        'total_comments': total_comments,
        'total_likes': total_likes,
        'reports': reports,
        'flagged': flagged,
        'pending_review': pending_review,
        'rejected': rejected,
        'most_liked': most_liked_list,
    }

# ─────────────────────────────────────────────
#  ROOM FINDER ANALYTICS
# ─────────────────────────────────────────────

def room_finder_analytics():
    listings = RoomListing.objects.all()
    total = _count(listings)
    active = _count(listings.filter(is_active=True))
    today = _count(listings.filter(created_at__gte=_start_of('today')))
    week = _count(listings.filter(created_at__gte=_start_of('7d')))
    month = _count(listings.filter(created_at__gte=_start_of('30d')))
    
    reqs = RoomRequest.objects.all()
    total_reqs = _count(reqs)
    reqs_today = _count(reqs.filter(created_at__gte=_start_of('today')))
    
    saved = _count(SavedRoomListing.objects.all())
    
    # By campus
    campus = (listings.values('campus').annotate(cnt=Count('id')).filter(campus__gt='').order_by('-cnt')[:10])
    campus_list = [{'name': c['campus'], 'count': c['cnt']} for c in campus]
    
    return {
        'total': total,
        'active': active,
        'today': today,
        'week': week,
        'month': month,
        'total_requests': total_reqs,
        'requests_today': reqs_today,
        'saved': saved,
        'by_campus': campus_list,
    }

# ─────────────────────────────────────────────
#  PROFILE ANALYTICS
# ─────────────────────────────────────────────

def profile_analytics():
    profiles = Profile.objects.all()
    created_today = _count(profiles.filter(created_at__gte=_start_of('today')))
    
    missing_photos = _count(profiles.filter(profile_pic__isnull=True)) + _count(profiles.filter(profile_pic=''))
    missing_bio = _count(profiles.filter(Q(bio__isnull=True) | Q(bio='')))
    pending_verification = _count(profiles.filter(verification_status='pending'))
    
    # Profiles with all key fields filled
    complete = 0
    total = _count(profiles)
    for p in profiles.all():
        if (p.name and p.gender and p.profile_pic and p.age and p.campus 
            and p.bio and p.living_place and p.native_place and p.course 
            and p.clg_year and p.interest_tags and p.looking_for):
            complete += 1
    
    return {
        'created_today': created_today,
        'missing_photos': missing_photos,
        'missing_bio': missing_bio,
        'pending_verification': pending_verification,
        'complete_profiles': complete,
        'total_profiles': total,
        'completion_pct': _pct(complete, total),
    }

# ─────────────────────────────────────────────
#  USER JOURNEY FUNNEL
# ─────────────────────────────────────────────

def user_journey():
    registered = _count(AuthUser.objects.all())
    profiles = Profile.objects.all()
    profile_started = _count(profiles)
    has_photos = _count(profiles.annotate(c=Count('images')).filter(c__gte=2))
    has_bio = _count(profiles.filter(bio__gt=''))
    face_verified = _count(profiles.filter(is_face_verified=True))
    sent_request = (MatchRequest.objects.values('sender').distinct().count())
    got_match = (MatchRequest.objects.filter(status='accepted').values('sender').distinct().count())
    sent_message = (Message.objects.values('sender').distinct().count())
    active = _count(profiles.filter(is_discoverable=True))

    steps = [
        ('Registered', registered, 100),
        ('Profile Started', profile_started, _pct(profile_started, registered)),
        ('Has 2+ Photos', has_photos, _pct(has_photos, registered)),
        ('Has Bio', has_bio, _pct(has_bio, registered)),
        ('Face Verified', face_verified, _pct(face_verified, registered)),
        ('Sent Match Request', sent_request, _pct(sent_request, registered)),
        ('Got a Match', got_match, _pct(got_match, registered)),
        ('Sent a Message', sent_message, _pct(sent_message, registered)),
        ('Active (Discoverable)', active, _pct(active, registered)),
    ]
    return {'steps': steps, 'total': registered}

# ─────────────────────────────────────────────
#  SAFETY & MODERATION
# ─────────────────────────────────────────────

def moderation_analytics():
    profiles = Profile.objects.all()
    user_reports = UserReport.objects.all()
    reports_today = _count(user_reports.filter(created_at__gte=_start_of('today')))
    reports_week = _count(user_reports.filter(created_at__gte=_start_of('7d')))
    
    confession_reports = _count(ConfessionReport.objects.all())
    banned_users = _count(profiles.filter(is_banned=True))
    shadow_banned = _count(BannedIdentifier.objects.filter(is_shadow_ban=True))
    blocked = _count(BlockedUser.objects.all())
    
    pending_confessions = _count(Confession.objects.filter(moderation_status='pending_review'))
    flagged_confessions = _count(Confession.objects.filter(is_flagged=True))
    
    return {
        'reports_today': reports_today,
        'reports_week': reports_week,
        'user_reports': _count(user_reports),
        'confession_reports': confession_reports,
        'banned_users': banned_users,
        'shadow_banned': shadow_banned,
        'blocked': blocked,
        'pending_moderation': pending_confessions,
        'flagged_content': flagged_confessions,
    }

# ─────────────────────────────────────────────
#  SYSTEM HEALTH
# ─────────────────────────────────────────────

def system_health():
    import os
    from django.conf import settings
    
    # Record counts
    total_records = (
        _count(AuthUser.objects.all())
        + _count(Profile.objects.all())
        + _count(ProfileImage.objects.all())
        + _count(Message.objects.all())
        + _count(MatchRequest.objects.all())
        + _count(Confession.objects.all())
        + _count(ConfessionComment.objects.all())
        + _count(Spark.objects.all())
        + _count(BlockedUser.objects.all())
        + _count(RoomListing.objects.all())
        + _count(RoomRequest.objects.all())
        + _count(Conversation.objects.all())
    )
    
    images = _count(ProfileImage.objects.all())
    fcm = _count(FCMToken.objects.all())
    voice_online = _count(VoiceParticipant.objects.filter(last_heartbeat__gte=_start_of('5m')))
    
    # DB size - only works on some backends
    db_size = 'N/A'
    
    return {
        'total_records': total_records,
        'db_size': db_size,
        'image_count': images,
        'fcm_tokens': fcm,
        'voice_online': voice_online,
    }

# ─────────────────────────────────────────────
#  LIVE ACTIVITY (last 50 events)
# ─────────────────────────────────────────────

def live_activity():
    events = []
    
    # Recent registrations
    for u in AuthUser.objects.order_by('-date_joined')[:10]:
        events.append({
            'type': 'registration',
            'icon': 'person_add',
            'text': f'User registered: {u.username}',
            'time': u.date_joined,
        })
    
    # Recent matches
    for m in MatchRequest.objects.filter(status='accepted').order_by('-created_at')[:10]:
        events.append({
            'type': 'match',
            'icon': 'favorite',
            'text': f'Match: {m.sender.username} ↔ {m.receiver.username}',
            'time': m.created_at,
        })
    
    # Recent messages
    for msg in Message.objects.order_by('-timestamp')[:10]:
        events.append({
            'type': 'message',
            'icon': 'chat',
            'text': f'Message: {msg.sender.username} → {msg.receiver.username}',
            'time': msg.timestamp,
        })
    
    # Recent confessions
    for c in Confession.objects.order_by('-created_at')[:5]:
        events.append({
            'type': 'confession',
            'icon': 'mask',
            'text': f'Confession posted (likes: {c.likes_count})',
            'time': c.created_at,
        })
    
    # Recent voice joins
    for vp in VoiceParticipant.objects.order_by('-joined_at')[:5]:
        events.append({
            'type': 'voice',
            'icon': 'headset_mic',
            'text': f'Voice join: {vp.user.username} → {vp.room.name}',
            'time': vp.joined_at,
        })
    
    # Recent room listings
    for rl in RoomListing.objects.order_by('-created_at')[:5]:
        events.append({
            'type': 'listing',
            'icon': 'home',
            'text': f'Room listed: {rl.campus} - ₹{rl.rent}',
            'time': rl.created_at,
        })
    
    events.sort(key=lambda e: e['time'], reverse=True)
    return events[:50]

# ─────────────────────────────────────────────
#  RETENTION (simplified cohort)
# ─────────────────────────────────────────────

def retention():
    """Cohort retention: Day 1, 7, 30 based on last_login from date_joined."""
    users = AuthUser.objects.filter(date_joined__gte=_start_of('30d')).exclude(last_login__isnull=True)
    
    day1 = day7 = day30 = 0
    total = 0
    for u in users:
        total += 1
        delta = (u.last_login - u.date_joined).days
        if delta >= 1:  day1 += 1
        if delta >= 7:  day7 += 1
        if delta >= 30: day30 += 1
    
    return {
        'day1': _pct(day1, max(total, 1)),
        'day7': _pct(day7, max(total, 1)),
        'day30': _pct(day30, max(total, 1)),
        'cohort_size': total,
    }
