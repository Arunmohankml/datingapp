import json
import re
from io import BytesIO
from html import escape, unescape
from html.parser import HTMLParser
from datetime import timedelta
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Case, Count, Exists, IntegerField, OuterRef, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .campus_config import get_all_campuses, get_campus_by_alias, get_org_groups
from .cloudinary_utils import upload_to_cloudinary
from .models import (
    KnotComment, KnotCommentLike, KnotEngagementNotice, KnotPost, KnotPreference,
    KnotReport, KnotVote, StaffMember,
)
from .pusher_utils import broadcast_event


SORTS = {'newest', 'hot', 'top', 'oldest'}
REPORT_REASONS = {choice[0] for choice in KnotReport.REPORT_CHOICES}
CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
RICH_TEXT_TAGS = {'p', 'div', 'br', 'strong', 'em', 'span', 'ul', 'ol', 'li', 'h2', 'a', 'img'}
COMMENT_MAX_LENGTH = 1200
KNOT_MAX_IMAGES = 4
KNOT_CREATE_COOLDOWN = timedelta(hours=1)
KNOT_IMAGE_TARGET_BYTES = 150 * 1024
KNOT_IMAGE_MAX_DIMENSION = 1280


class _KnotRichTextSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.blocked_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {'script', 'style'}:
            self.blocked_depth += 1
            return
        if self.blocked_depth or tag not in RICH_TEXT_TAGS:
            return
        if tag == 'div':
            tag = 'p'
        attrs = dict(attrs)
        if tag == 'img':
            src = str(attrs.get('src') or '').strip()
            parsed = urlparse(src)
            if parsed.scheme == 'https' and parsed.hostname == 'res.cloudinary.com':
                alt = CONTROL_CHARS.sub('', str(attrs.get('alt') or 'Knot image'))[:120]
                self.parts.append(f'<img src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}">')
            return
        if tag == 'a':
            href = str(attrs.get('href') or '').strip()
            parsed = urlparse(href)
            if parsed.scheme in {'http', 'https'} and parsed.netloc:
                self.parts.append(
                    f'<a href="{escape(href, quote=True)}" target="_blank" rel="nofollow noopener noreferrer">'
                )
            return
        if tag == 'span':
            classes = set(str(attrs.get('class') or '').split())
            if 'knot-inline-heading' in classes:
                self.parts.append('<span class="knot-inline-heading">')
            else:
                self.parts.append('<span>')
            return
        self.parts.append('<br>' if tag == 'br' else f'<{tag}>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {'script', 'style'}:
            self.blocked_depth = max(0, self.blocked_depth - 1)
            return
        if tag == 'div':
            tag = 'p'
        if not self.blocked_depth and tag in RICH_TEXT_TAGS - {'br', 'img', 'div'}:
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        if not self.blocked_depth:
            data = CONTROL_CHARS.sub('', data).replace('\r\n', '\n').replace('\r', '\n')
            data = re.sub(r'[\t\f\v \xa0]+', ' ', data)
            data = re.sub(r'\n(?:[ \t]*\n){2,}', '\n\n', data)
            self.parts.append(escape(data))


def _clean_rich_content(value):
    raw = str(value or '')
    if len(raw) > 20000:
        raise ValidationError('Content formatting is too large.')
    sanitizer = _KnotRichTextSanitizer()
    sanitizer.feed(raw)
    sanitizer.close()
    cleaned = ''.join(sanitizer.parts).strip()
    cleaned = re.sub(r'(?:\s*<br>\s*){3,}', '<br><br>', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?:<p>\s*(?:<br>\s*)?</p>\s*){2,}', '<br><br>', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n(?:[ \t]*\n){2,}', '\n\n', cleaned)
    if len(re.findall(r'<img\b', cleaned, flags=re.IGNORECASE)) > KNOT_MAX_IMAGES:
        raise ValidationError(f'You can add up to {KNOT_MAX_IMAGES} images in one Knot.')
    plain = CONTROL_CHARS.sub('', unescape(strip_tags(cleaned))).replace('\xa0', ' ').strip()
    if not plain:
        raise ValidationError('Content is required.')
    if len(plain) > 5000:
        raise ValidationError('Content must be 5000 characters or fewer.')
    return cleaned, plain


def _normalize_plain_spacing(text, keep_line_breaks=False):
    text = CONTROL_CHARS.sub('', strip_tags(str(text or ''))).replace('\r\n', '\n').replace('\r', '\n')
    text = text.replace('\xa0', ' ')
    text = re.sub(r'[ \t\f\v]+', ' ', text)
    if keep_line_breaks:
        text = re.sub(r' *\n *', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
    else:
        text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _plain_content_for_display(value, keep_line_breaks=False):
    """Convert sanitized Knot HTML into readable plain text for excerpts/schema."""
    return _normalize_plain_spacing(unescape(strip_tags(str(value or ''))), keep_line_breaks=keep_line_breaks)


def _is_moderator(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_staff or user.is_superuser or user.email in settings.ADMIN_EMAILS or StaffMember.objects.filter(email=user.email).exists()


def _json_body(request):
    try:
        return json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return None


def _clean_text(value, field, max_length, required=True):
    text = _normalize_plain_spacing(value)
    if required and not text:
        raise ValidationError(f'{field} is required.')
    if len(text) > max_length:
        raise ValidationError(f'{field} must be {max_length} characters or fewer.')
    return text


def _clean_comment_text(value):
    text = _normalize_plain_spacing(value, keep_line_breaks=True)
    if not text:
        raise ValidationError('Comment is required.')
    if len(text) > COMMENT_MAX_LENGTH:
        raise ValidationError(f'Comment must be {COMMENT_MAX_LENGTH} characters or fewer.')
    return text


def _clean_link(value):
    link = str(value or '').strip()
    if not link:
        return ''
    if urlparse(link).scheme not in {'http', 'https'}:
        raise ValidationError('Link must start with http:// or https://.')
    URLValidator(schemes=['http', 'https'])(link)
    if len(link) > 1000:
        raise ValidationError('Link is too long.')
    return link


def _error(message, status=400, details=None):
    payload = {'success': False, 'error': message}
    if details:
        payload['details'] = details
    return JsonResponse(payload, status=status)


def _profile_snapshot(user):
    profile = getattr(user, 'profile', None)
    campus = get_campus_by_alias(getattr(profile, 'campus', ''))
    if not profile or not campus:
        return '', ''
    return campus['org'], campus['name']


def _rate_limited(model, user, since, limit):
    return model.objects.filter(user=user, created_at__gte=since).count() >= limit


def _optimized_knot_image(image_file):
    image_file.seek(0)
    with Image.open(image_file) as source:
        if getattr(source, 'is_animated', False) or source.format == 'GIF':
            image_file.seek(0)
            return image_file

        image = source
        if image.mode not in ('RGB', 'L'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode in ('RGBA', 'LA'):
                background.paste(image.convert('RGBA'), mask=image.convert('RGBA').getchannel('A'))
            else:
                background.paste(image.convert('RGB'))
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        else:
            image = image.copy()

    if max(image.size) > KNOT_IMAGE_MAX_DIMENSION:
        image.thumbnail((KNOT_IMAGE_MAX_DIMENSION, KNOT_IMAGE_MAX_DIMENSION), Image.Resampling.LANCZOS)

    best = None
    best_size = None
    quality_steps = (82, 76, 70, 64, 58, 52)
    for _ in range(4):
        for quality in quality_steps:
            output = BytesIO()
            image.save(output, format='WEBP', quality=quality, method=6, optimize=True)
            size = output.tell()
            if best is None or size < best_size:
                output.seek(0)
                best = output
                best_size = size
            if size <= KNOT_IMAGE_TARGET_BYTES:
                output.seek(0)
                output.name = 'knot-image.webp'
                return output
        width, height = image.size
        if width <= 720 and height <= 720:
            break
        image = image.resize((max(1, int(width * .85)), max(1, int(height * .85))), Image.Resampling.LANCZOS)

    best.seek(0)
    best.name = 'knot-image.webp'
    return best


def _safe_push(user, title, body, url):
    if not user:
        return
    try:
        from .views import send_push_to_user
        send_push_to_user(user, title, body, url)
    except Exception as exc:
        print(f'Knots push skipped: {exc}')


def _safe_in_app_notify(user, title, body, url, payload=None):
    if not user:
        return
    data = {'title': title, 'body': body, 'url': url}
    if payload:
        data.update(payload)
    try:
        broadcast_event(f'chat_{user.id}', 'knot_activity', data)
    except Exception as exc:
        print(f'Knots in-app notification skipped: {exc}')


def _notify_after_commit(user, title, body, url, payload=None):
    transaction.on_commit(lambda: (
        _safe_push(user, title, body, url),
        _safe_in_app_notify(user, title, body, url, payload),
    ))


def _annotated_posts(user):
    is_authenticated = bool(user and user.is_authenticated)
    voted = KnotVote.objects.filter(post=OuterRef('pk'), user=user) if is_authenticated else None
    recent = timezone.now() - timedelta(days=7)
    annotations = {
        'upvote_count': Count('votes', distinct=True),
        'comment_count': Count('comments', distinct=True),
        'recent_vote_count': Count('votes', filter=Q(votes__created_at__gte=recent), distinct=True),
        'recent_comment_count': Count('comments', filter=Q(comments__created_at__gte=recent), distinct=True),
        'user_has_voted': Exists(voted) if is_authenticated else Value(False, output_field=BooleanField()),
    }
    return KnotPost.objects.select_related('user__profile').annotate(**annotations)


def _annotated_comments(user):
    is_authenticated = bool(user and user.is_authenticated)
    liked = KnotCommentLike.objects.filter(comment=OuterRef('pk'), user=user) if is_authenticated else None
    return KnotComment.objects.select_related('user__profile', 'post', 'parent').annotate(
        like_count=Count('likes', distinct=True),
        reply_count=Count('replies', distinct=True),
        user_has_liked=Exists(liked) if is_authenticated else Value(False, output_field=BooleanField()),
    )


def _comment_payload(comment, user):
    profile = getattr(comment.user, 'profile', None)
    is_moderator = _is_moderator(user)
    is_authenticated = bool(user and user.is_authenticated)
    return {
        'id': comment.id,
        'post_id': comment.post_id,
        'parent_id': comment.parent_id,
        'content': 'Comment deleted' if comment.is_deleted else comment.content,
        'is_deleted': comment.is_deleted,
        'name': profile.display_name if profile else comment.user.username,
        'avatar': profile.get_profile_pic_thumb_url if profile else '',
        'profile_url': f'/profile/{comment.user_id}/',
        'campus': profile.campus_display if profile else '',
        'created_at': comment.created_at.isoformat(),
        'updated': comment.updated_at > comment.created_at + timedelta(seconds=2),
        'like_count': comment.like_count,
        'reply_count': comment.reply_count,
        'liked': comment.user_has_liked,
        'can_manage': not comment.is_deleted and is_authenticated and (comment.user_id == user.id or is_moderator),
        'can_admin_delete': is_moderator,
        'can_report': not comment.is_deleted and is_authenticated and comment.user_id != user.id,
        'is_author_anonymous': comment.post.is_anonymous if comment.post else False,
    }


@require_GET
def knots_feed(request):
    if request.user.is_authenticated:
        preference, _ = KnotPreference.objects.get_or_create(user=request.user)
        default_sort = preference.sort
        default_colleges = preference.colleges
        default_campuses = preference.campuses
    else:
        preference = None
        default_sort = 'newest'
        default_colleges = []
        default_campuses = []
    filters_submitted = request.GET.get('filters') == '1'
    sort = request.GET.get('sort', default_sort)
    if sort not in SORTS:
        sort = 'newest'

    valid_campuses = {item['code']: item for item in get_all_campuses()}
    valid_colleges = set(get_org_groups())
    if filters_submitted:
        colleges = [value for value in request.GET.getlist('colleges') if value in valid_colleges]
        campuses = [value for value in request.GET.getlist('campuses') if value in valid_campuses]
    else:
        colleges = [value for value in default_colleges if value in valid_colleges]
        campuses = [value for value in default_campuses if value in valid_campuses]

    if preference and (preference.sort != sort or preference.colleges != colleges or preference.campuses != campuses):
        preference.sort, preference.colleges, preference.campuses = sort, colleges, campuses
        preference.save(update_fields=['sort', 'colleges', 'campuses', 'updated_at'])

    posts = _annotated_posts(request.user)
    search = _clean_text(request.GET.get('q', ''), 'Search', 120, required=False)
    if search:
        posts = posts.filter(Q(title__icontains=search) | Q(content__icontains=search))
    if colleges:
        posts = posts.filter(college__in=colleges)
    if campuses:
        posts = posts.filter(campus__in=[valid_campuses[code]['name'] for code in campuses])

    if sort == 'oldest':
        posts = posts.order_by('created_at')
    elif sort == 'top':
        posts = posts.order_by('-upvote_count', '-comment_count', '-created_at')
    elif sort == 'hot':
        now = timezone.now()
        posts = posts.annotate(
            recency_score=Case(
                When(created_at__gte=now - timedelta(days=1), then=Value(60)),
                When(created_at__gte=now - timedelta(days=7), then=Value(25)),
                When(created_at__gte=now - timedelta(days=30), then=Value(8)),
                default=Value(0), output_field=IntegerField(),
            )
        ).order_by('-recency_score', '-recent_vote_count', '-recent_comment_count', '-upvote_count', '-comment_count', '-created_at')
    else:
        posts = posts.order_by('-created_at')

    page_obj = Paginator(posts, 12).get_page(request.GET.get('page', 1))
    feed_items = []
    for index, post in enumerate(page_obj.object_list, start=1):
        post.plain_excerpt = _plain_content_for_display(post.content)
        post_url = f'/knots/{post.id}/{post.slug}/'
        feed_items.append({
            '@type': 'ListItem',
            'position': index,
            'url': request.build_absolute_uri(post_url),
            'name': post.title,
            'description': post.plain_excerpt[:260],
        })
    feed_schema_json = json.dumps({
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'name': 'Knots campus discussion threads',
        'description': 'Public campus discussion threads on KnotSpot for student questions, advice, and college life.',
        'url': request.build_absolute_uri(request.path),
        'itemListElement': feed_items,
    }, ensure_ascii=False)
    selected_campuses = [valid_campuses[code] for code in campuses]
    sort_options = [('newest','Newest'),('hot','Hot'),('top','Top'),('oldest','Oldest')]
    return render(request, 'knots/feed.html', {
        'posts': page_obj, 'current_sort': sort, 'search_query': search,
        'selected_colleges': colleges, 'selected_campuses': selected_campuses,
        'selected_campus_codes': campuses, 'campus_groups': get_org_groups(),
        'selected_filter_count': len(colleges) + len(campuses),
        'is_moderator': _is_moderator(request.user), 'sort_options': sort_options,
        'login_url': settings.LOGIN_URL if hasattr(settings, 'LOGIN_URL') else '/login/',
        'feed_schema_json': feed_schema_json,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def knot_form(request, post_id=None):
    post = get_object_or_404(KnotPost, id=post_id) if post_id else None
    if post and post.user_id != request.user.id and not _is_moderator(request.user):
        return _error('You cannot edit this Knot.', 403) if request.method == 'POST' else redirect('knots_feed')

    if request.method == 'GET':
        try:
            college, campus = _profile_snapshot(request.user) if not post else (post.college, post.campus)
        except ValidationError:
            college = campus = ''
        return render(request, 'knots/form.html', {
            'post': post, 'categories': KnotPost.CATEGORY_CHOICES,
            'profile_college': college, 'profile_campus': campus,
            'is_admin_edit': bool(post and post.user_id != request.user.id),
            'campus_groups': get_org_groups(),
            'hide_bottom_nav': True,
        })

    data = _json_body(request)
    if data is None:
        return _error('Invalid JSON body.')
    try:
        title = _clean_text(data.get('title'), 'Title', 180)
        content, _plain_content = _clean_rich_content(data.get('content_html', data.get('content')))
        link = _clean_link(data.get('link'))
        category = str(data.get('category') or '').strip()
        if category and category not in dict(KnotPost.CATEGORY_CHOICES):
            raise ValidationError('Choose a valid category.')
        is_anonymous = bool(data.get('is_anonymous', False))
        location_supplied = 'college' in data or 'campus' in data
        college = str(data.get('college') or '').strip()
        campus = str(data.get('campus') or '').strip()
        valid_colleges = set(get_org_groups())
        if college and college not in valid_colleges:
            raise ValidationError('Choose a valid college.')
        campus_record = get_campus_by_alias(campus) if campus else None
        if campus and not campus_record:
            raise ValidationError('Choose a valid campus.')
        if campus_record:
            if college and campus_record['org'] != college:
                raise ValidationError('Choose a campus from the selected college.')
            college = college or campus_record['org']
            campus = campus_record['name']
        if not post:
            if _rate_limited(KnotPost, request.user, timezone.now() - KNOT_CREATE_COOLDOWN, 1):
                return _error('You can post only one Knot per hour. Try again later.', 429)
            if not location_supplied and not college and not campus:
                profile_college, profile_campus = _profile_snapshot(request.user)
                college, campus = profile_college, profile_campus
            duplicate = KnotPost.objects.filter(
                user=request.user, title__iexact=title,
                created_at__gte=timezone.now() - timedelta(minutes=2),
            ).exists()
            if duplicate:
                return _error('This Knot was already posted.', 409)
            post = KnotPost.objects.create(
                user=request.user, title=title, content=content, link=link,
                category=category, college=college, campus=campus,
                is_anonymous=is_anonymous,
            )
            status = 201
        else:
            post.title, post.content, post.link, post.category = title, content, link, category
            post.is_anonymous = is_anonymous
            if 'college' in data:
                post.college = college
            if 'campus' in data:
                post.campus = campus
            post.save(update_fields=['title', 'content', 'link', 'category', 'is_anonymous', 'college', 'campus', 'updated_at'])
            status = 200
    except ValidationError as exc:
        return _error(exc.messages[0])
    return JsonResponse({'success': True, 'data': {'id': post.id, 'url': f'/knots/{post.id}/{post.slug}/'}}, status=status)


@login_required
@require_POST
def knot_image_upload(request):
    image_file = request.FILES.get('image')
    if not image_file:
        return _error('Choose an image to upload.')
    if image_file.size > 8 * 1024 * 1024:
        return _error('Image must be 8 MB or smaller.')
    if image_file.content_type not in {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}:
        return _error('Upload a JPG, PNG, WebP or GIF image.')
    try:
        with Image.open(image_file) as candidate:
            if candidate.width * candidate.height > 20_000_000:
                return _error('Image dimensions are too large.')
            candidate.verify()
        image_file.seek(0)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return _error('The selected file is not a valid image.')

    rate_key = f'knot-image-upload:{request.user.id}:{timezone.now().strftime("%Y%m%d%H%M")}'
    upload_count = cache.get(rate_key, 0)
    if upload_count >= 10:
        return _error('Too many image uploads. Try again in a minute.', 429)
    cache.set(rate_key, upload_count + 1, 90)

    optimized_image = _optimized_knot_image(image_file)
    uploaded = upload_to_cloudinary(optimized_image, folder='knotspot/knot_images', optimize=False)
    if not uploaded:
        return _error('Image upload failed. Try again.', 502)
    return JsonResponse({'success': True, 'data': {'url': uploaded}}, status=201)


@require_GET
def knot_detail(request, post_id, slug=None):
    post = get_object_or_404(_annotated_posts(request.user), id=post_id)
    if slug != post.slug:
        return redirect('knot_detail_slug', post_id=post.id, slug=post.slug)
    post.plain_excerpt = _plain_content_for_display(post.content, keep_line_breaks=True)
    comments = _annotated_comments(request.user).filter(post=post, parent__isnull=True).order_by('created_at', 'id')
    page_obj = Paginator(comments, 20).get_page(request.GET.get('page', 1))
    post_schema_json = json.dumps({
        '@context': 'https://schema.org',
        '@type': 'DiscussionForumPosting',
        'headline': post.title,
        'articleBody': post.plain_excerpt,
        'url': request.build_absolute_uri(f'/knots/{post.id}/{post.slug}/'),
        'datePublished': post.created_at.isoformat(),
        'dateModified': post.updated_at.isoformat(),
        'commentCount': post.comment_count,
        'author': {
            '@type': 'Person',
            'name': post.display_name,
        },
        'publisher': {
            '@type': 'Organization',
            'name': 'KnotSpot',
            'url': 'https://knotspot.online/',
        },
    }, ensure_ascii=False)
    return render(request, 'knots/detail.html', {
        'post': post, 'comments': page_obj, 'is_moderator': _is_moderator(request.user),
        'hide_bottom_nav': True,
        'login_url': settings.LOGIN_URL if hasattr(settings, 'LOGIN_URL') else '/login/',
        'post_schema_json': post_schema_json,
    })


@login_required
@require_POST
def knot_delete(request, post_id):
    post = get_object_or_404(KnotPost, id=post_id)
    if post.user_id != request.user.id and not _is_moderator(request.user):
        return _error('You cannot delete this Knot.', 403)
    post.delete()
    return JsonResponse({'success': True, 'data': {'deleted': True}})


@login_required
@require_POST
def knot_vote(request, post_id):
    post = get_object_or_404(KnotPost, id=post_id)
    vote = KnotVote.objects.filter(post=post, user=request.user).first()
    if vote:
        vote.delete()
        active = False
    else:
        try:
            KnotVote.objects.create(post=post, user=request.user)
        except IntegrityError:
            pass
        active = True
    count = post.votes.count()
    if active and post.user_id != request.user.id:
        for threshold in (100, 50, 25, 10, 5):
            if count >= threshold:
                notice, created = KnotEngagementNotice.objects.get_or_create(post=post, threshold=threshold)
                if created:
                    _notify_after_commit(post.user, 'Your Knot is getting noticed', f'{threshold} students upvoted “{post.title[:80]}”.', f'/knots/{post.id}/{post.slug}/')
                break
    return JsonResponse({'success': True, 'data': {'active': active, 'count': count}})


@login_required
@require_POST
def knot_report(request, post_id):
    post = get_object_or_404(KnotPost, id=post_id)
    if post.user_id == request.user.id:
        return _error('You cannot report your own Knot.')
    data = _json_body(request) or {}
    reason = data.get('reason', 'other')
    if reason not in REPORT_REASONS:
        return _error('Choose a valid report reason.')
    details = _clean_text(data.get('details', ''), 'Details', 500, required=False)
    _, created = KnotReport.objects.get_or_create(
        reporter=request.user, post=post, defaults={'reason': reason, 'details': details}
    )
    if not created:
        return _error('You already reported this Knot.', 409)
    return JsonResponse({'success': True, 'data': {'reported': True}}, status=201)


@login_required
@require_POST
def knot_comment_create(request, post_id):
    post = get_object_or_404(KnotPost, id=post_id)
    data = _json_body(request)
    if data is None:
        return _error('Invalid JSON body.')
    try:
        content = _clean_comment_text(data.get('content'))
    except ValidationError as exc:
        return _error(exc.messages[0])
    if _rate_limited(KnotComment, request.user, timezone.now() - timedelta(minutes=1), 10):
        return _error('You are commenting too quickly. Wait a moment and try again.', 429)
    parent = None
    if data.get('parent_id'):
        parent = get_object_or_404(KnotComment, id=data['parent_id'], post=post)
    duplicate = KnotComment.objects.filter(
        user=request.user, post=post, content=content,
        created_at__gte=timezone.now() - timedelta(seconds=30),
    ).exists()
    if duplicate:
        return _error('This comment was already posted.', 409)
    comment = KnotComment.objects.create(post=post, user=request.user, parent=parent, content=content)
    target = parent.user if parent else post.user
    if target.id != request.user.id:
        actor = getattr(request.user, 'profile', None)
        actor_name = actor.display_name if actor else request.user.username
        title = 'New reply to your comment' if parent else 'New comment on your Knot'
        kind = 'knot_reply' if parent else 'knot_comment'
        _notify_after_commit(target, title, f'{actor_name}: {content[:100]}', f'/knots/{post.id}/{post.slug}/#comment-{comment.id}', {
            'kind': kind,
            'post_id': post.id,
            'comment_id': comment.id,
            'actor_id': request.user.id,
            'actor_name': actor_name,
        })
    comment = _annotated_comments(request.user).get(id=comment.id)
    return JsonResponse({'success': True, 'data': _comment_payload(comment, request.user)}, status=201)


@login_required
@require_POST
def knot_comment_edit(request, comment_id):
    comment = get_object_or_404(KnotComment, id=comment_id)
    if comment.is_deleted:
        return _error('A deleted comment cannot be edited.', 409)
    if comment.user_id != request.user.id and not _is_moderator(request.user):
        return _error('You cannot edit this comment.', 403)
    data = _json_body(request) or {}
    try:
        comment.content = _clean_comment_text(data.get('content'))
    except ValidationError as exc:
        return _error(exc.messages[0])
    comment.save(update_fields=['content', 'updated_at'])
    return JsonResponse({'success': True, 'data': {'id': comment.id, 'content': comment.content}})


@login_required
@require_POST
def knot_comment_delete(request, comment_id):
    comment = get_object_or_404(KnotComment, id=comment_id)
    data = _json_body(request) or {}
    force_delete = bool(data.get('force'))
    is_moderator = _is_moderator(request.user)
    if force_delete and not is_moderator:
        return _error('Only admins can permanently delete comment threads.', 403)
    if comment.user_id != request.user.id and not is_moderator:
        return _error('You cannot delete this comment.', 403)
    if force_delete:
        comment.delete()
        return JsonResponse({'success': True, 'data': {'deleted': True, 'soft_deleted': False, 'hard_deleted': True}})
    if comment.replies.exists():
        comment.content = ''
        comment.is_deleted = True
        comment.save(update_fields=['content', 'is_deleted', 'updated_at'])
        soft_deleted = True
    else:
        comment.delete()
        soft_deleted = False
    return JsonResponse({'success': True, 'data': {'deleted': True, 'soft_deleted': soft_deleted}})


@login_required
@require_POST
def knot_comment_like(request, comment_id):
    comment = get_object_or_404(KnotComment, id=comment_id, is_deleted=False)
    like = KnotCommentLike.objects.filter(comment=comment, user=request.user).first()
    if like:
        like.delete()
        active = False
    else:
        try:
            KnotCommentLike.objects.create(comment=comment, user=request.user)
        except IntegrityError:
            pass
        active = True
    return JsonResponse({'success': True, 'data': {'active': active, 'count': comment.likes.count()}})


@login_required
@require_POST
def knot_comment_report(request, comment_id):
    comment = get_object_or_404(KnotComment, id=comment_id, is_deleted=False)
    if comment.user_id == request.user.id:
        return _error('You cannot report your own comment.')
    data = _json_body(request) or {}
    reason = data.get('reason', 'other')
    if reason not in REPORT_REASONS:
        return _error('Choose a valid report reason.')
    details = _clean_text(data.get('details', ''), 'Details', 500, required=False)
    _, created = KnotReport.objects.get_or_create(
        reporter=request.user, comment=comment, defaults={'reason': reason, 'details': details}
    )
    if not created:
        return _error('You already reported this comment.', 409)
    return JsonResponse({'success': True, 'data': {'reported': True}}, status=201)


@require_GET
def knot_replies_api(request, comment_id):
    parent = get_object_or_404(KnotComment, id=comment_id)
    replies = _annotated_comments(request.user).filter(parent=parent).order_by('created_at', 'id')[:50]
    return JsonResponse({'success': True, 'data': [_comment_payload(reply, request.user) for reply in replies]})


@require_GET
def knot_thread(request, comment_id):
    root = get_object_or_404(_annotated_comments(request.user), id=comment_id)
    replies = _annotated_comments(request.user).filter(parent=root).order_by('created_at', 'id')
    page_obj = Paginator(replies, 30).get_page(request.GET.get('page', 1))
    return render(request, 'knots/thread.html', {
        'post': root.post, 'root_comment': root, 'comments': page_obj,
        'is_moderator': _is_moderator(request.user), 'hide_bottom_nav': True,
    })


@login_required
@require_POST
def knot_preferences(request):
    data = _json_body(request)
    if data is None:
        return _error('Invalid JSON body.')
    preference, _ = KnotPreference.objects.get_or_create(user=request.user)
    valid_colleges = set(get_org_groups())
    valid_campuses = {item['code'] for item in get_all_campuses()}
    sort = data.get('sort', preference.sort)
    colleges = data.get('colleges', preference.colleges)
    campuses = data.get('campuses', preference.campuses)
    if sort not in SORTS or not isinstance(colleges, list) or not isinstance(campuses, list):
        return _error('Invalid preferences.')
    preference.sort = sort
    preference.colleges = [value for value in colleges if value in valid_colleges]
    preference.campuses = [value for value in campuses if value in valid_campuses]
    preference.save()
    return JsonResponse({'success': True, 'data': {
        'sort': preference.sort, 'colleges': preference.colleges, 'campuses': preference.campuses,
    }})
