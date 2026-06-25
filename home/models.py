from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User
from .campus_config import get_campus_by_alias

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Basic Info
    name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=[('male','Male'), ('female','Female'), ('other','Other')])
    profile_pic = models.URLField(max_length=500, blank=True, null=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    clg_year = models.IntegerField(null=True, blank=True)
    campus = models.CharField(max_length=100, default='', blank=True)
    course = models.CharField(max_length=100, default='', blank=True)


    # Places
    living_place = models.CharField(max_length=100, default='', blank=True)
    native_place = models.CharField(max_length=100, default='', blank=True)

    # Language
    languages = models.TextField(default='', blank=True)
    mother_tongues = models.TextField(default='', blank=True)

    # Personal
    bio = models.TextField(blank=True)
    liked_songs = models.TextField(blank=True)
    liked_movies = models.TextField(blank=True)
    fav_shows = models.TextField(blank=True)
    interest_tags = models.TextField(default='', blank=True)
    looking_for = models.CharField(
        max_length=50,
        choices=[
            ('friendship', 'Friendship'),
            ('serious', 'Relationship'),
            ('vibe', 'Just vibing')
        ],
        default='vibe'
    )

    # Preferences
    pref_age_min = models.PositiveIntegerField(default=18)
    pref_age_max = models.PositiveIntegerField(default=25)
    pref_gender = models.CharField(max_length=10, choices=[('male','Male'), ('female','Female'), ('any','Any')], default='any')
    pref_languages = models.TextField(default='', blank=True)
    pref_campus = models.CharField(max_length=100, blank=True)


    # Face Verification (Simplified)
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('manual_review', 'Manual Review'),
        ('rejected', 'Rejected'),
    ]
    verification_image = models.URLField(max_length=500, blank=True, null=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending')
    is_face_verified = models.BooleanField(default=False)

    # System
    is_banned = models.BooleanField(default=False)
    is_discoverable = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                is_complete = True
                if not self.profile_pic:
                    is_complete = False
                elif not self.bio or not self.bio.strip():
                    is_complete = False
                elif not self.living_place or not self.living_place.strip():
                    is_complete = False
                elif not self.native_place or not self.native_place.strip():
                    is_complete = False
                elif not self.course or not self.course.strip():
                    is_complete = False
                elif not self.clg_year:
                    is_complete = False
                elif not self.interest_tags or not self.interest_tags.strip():
                    is_complete = False
                elif not self.looking_for or not self.looking_for.strip():
                    is_complete = False
                elif not self.pref_gender or not self.pref_gender.strip():
                    is_complete = False
                elif self.images.count() < 2:
                    is_complete = False

                if not is_complete or not self.is_face_verified:
                    self.is_discoverable = False
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.user.email}"

    @property
    def display_name(self):
        if self.name and self.name.strip() and self.name.strip().lower() != "no name":
            return self.name
        if self.user and self.user.email:
            email_parts = self.user.email.split('@')
            if email_parts and email_parts[0]:
                return email_parts[0]
        return "No Name"

    @property
    def campus_display(self):
        c = get_campus_by_alias(self.campus)
        return f"{c['org']} {c['code']}" if c else self.campus

    @property
    def get_profile_pic_url(self):
        # Ensure we are dealing with a string before checking for URL prefix
        if isinstance(self.profile_pic, str) and (self.profile_pic.startswith('http://') or self.profile_pic.startswith('https://')):
            if 'res.cloudinary.com' in self.profile_pic:
                # Apply transformations for profile pictures: f_auto,q_auto,w_400
                return self.profile_pic.replace('/upload/', '/upload/f_auto,q_auto,w_400/')
            return self.profile_pic
        # Fallback to a nice avatar placeholder if the URL is broken, relative, or a temporary file object
        name_param = self.name.replace(" ", "+") if self.name else "User"
        return f"https://ui-avatars.com/api/?name={name_param}&background=6366f1&color=fff&size=256"

    @property
    def interest_tags_list(self):
        return self._parse_tags(self.interest_tags)

    @property
    def languages_list(self):
        return self._parse_tags(self.languages)

    @property
    def mother_tongues_list(self):
        return self._parse_tags(self.mother_tongues)

    @property
    def pref_languages_list(self):
        return self._parse_tags(self.pref_languages)

    def _parse_tags(self, raw):
        if not raw:
            return []
        s = str(raw).strip()
        # Aggressively remove Python list/string artifacts
        s = s.replace('[', '').replace(']', '').replace("'", "").replace('"', "")
        
        items = []
        for t in s.split(','):
            clean = t.strip()
            if clean and clean.lower() != 'none' and clean != '[]' and len(clean) > 1:
                items.append(clean)
        return items

class Question(models.Model):
    text = models.CharField(max_length=255)

    def __str__(self):
        return self.text

class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=100)
    weight = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.question.text} - {self.text} ({self.weight})"

class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    option = models.ForeignKey(Option, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "question")

class MatchRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('skipped', 'Skipped'),
    )
    sender = models.ForeignKey(User, related_name='sent_requests', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_requests', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.status})"

class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    # Flags for per-user deletion
    sender_deleted = models.BooleanField(default=False)
    receiver_deleted = models.BooleanField(default=False)
    
    # Reply feature
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

    def __str__(self):
        return f"From {self.sender.username} to {self.receiver.username} at {self.timestamp}"

class ProfileImage(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="images")
    image = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.profile.name}"

    @property
    def get_image_url(self):
        # Ensure we are dealing with a string before checking for URL prefix
        if isinstance(self.image, str) and (self.image.startswith('http://') or self.image.startswith('https://')):
            if 'res.cloudinary.com' in self.image:
                # Apply transformations for gallery images: f_auto,q_auto,w_800
                return self.image.replace('/upload/', '/upload/f_auto,q_auto,w_800/')
            return self.image
        # Fallback for old/broken/temporary gallery images
        return "https://placehold.co/600x600/6366f1/ffffff?text=Image+Not+Found"


class WallStroke(models.Model):
    """Anonymous wall drawing stroke — no user identity stored."""
    points = models.JSONField()  # List of {x, y} coordinates
    color = models.CharField(max_length=20, default='#ffffff')
    brush_size = models.FloatField(default=2.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Stroke {self.id} ({self.color}) at {self.created_at}"


class WallImage(models.Model):
    """Admin-uploaded images on the wall."""
    image_url = models.URLField(max_length=1000)
    x = models.FloatField()
    y = models.FloatField()
    width = models.FloatField()
    height = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"WallImage {self.id} at ({self.x}, {self.y})"


class Confession(models.Model):
    MODERATION_STATUS = [
        ('approved',       'Approved'),
        ('pending_review', 'Pending Review'),
        ('rejected',       'Rejected'),
        ('flagged',        'Flagged'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    image = models.URLField(max_length=500, blank=True, null=True)
    campus = models.CharField(max_length=100, blank=True, default='')
    is_anonymous = models.BooleanField(default=True)
    likes_count = models.PositiveIntegerField(default=0)
    is_flagged = models.BooleanField(default=False)
    poster_fingerprint = models.CharField(max_length=100, blank=True, null=True)
    # ── Moderation ──
    moderation_status = models.CharField(
        max_length=20, choices=MODERATION_STATUS, default='approved', db_index=True
    )
    moderation_reason = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        name = "Anonymous" if self.is_anonymous else (self.user.profile.name if self.user else "Deleted")
        return f"Confession #{self.id} by {name}"

    @property
    def display_name(self):
        if self.is_anonymous:
            return "Anonymous"
        if self.user and hasattr(self.user, 'profile'):
            return self.user.profile.name
        return "Unknown"

    @property
    def display_pic(self):
        if self.is_anonymous:
            return "https://ui-avatars.com/api/?name=A&background=6366f1&color=fff&size=128"
        if self.user and hasattr(self.user, 'profile'):
            return self.user.profile.get_profile_pic_url
        return "https://ui-avatars.com/api/?name=U&background=6366f1&color=fff&size=128"

    @property
    def campus_display(self):
        c = get_campus_by_alias(self.campus)
        return f"{c['org']} {c['code']}" if c else self.campus


class ConfessionComment(models.Model):
    confession = models.ForeignKey(Confession, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    is_anonymous = models.BooleanField(default=True)
    poster_fingerprint = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    @property
    def display_name(self):
        if self.is_anonymous:
            return "Anonymous"
        if self.user and hasattr(self.user, 'profile'):
            return self.user.profile.name
        return "Unknown"

    @property
    def display_pic(self):
        if self.is_anonymous:
            return "https://ui-avatars.com/api/?name=A&background=64748b&color=fff&size=128"
        if self.user and hasattr(self.user, 'profile'):
            return self.user.profile.get_profile_pic_url
        return "https://ui-avatars.com/api/?name=U&background=64748b&color=fff&size=128"


class ConfessionLike(models.Model):
    confession = models.ForeignKey(Confession, on_delete=models.CASCADE, related_name='likes')
    session_key = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('confession', 'session_key')

class ConfessionReport(models.Model):
    confession = models.ForeignKey(Confession, on_delete=models.CASCADE, related_name='reports')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    reporter_fingerprint = models.CharField(max_length=100, blank=True, null=True)
    reasons = models.JSONField(default=list) # List of selected reasons
    other_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # unique_together removed to allow multiple reports from same fingerprint/user on different confessions
        # or even multiple reports on same confession if needed, though usually restricted.
        pass

class UserReport(models.Model):
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_reports')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_reports')
    reasons = models.JSONField(default=list)
    other_reason = models.TextField(blank=True)
    chat_snapshot = models.JSONField(default=list) # Store recent messages for context
    created_at = models.DateTimeField(auto_now_add=True)

class Spark(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sparks_sent')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sparks_received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender.username} sparked {self.receiver.username}"

class BlockedUser(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocking')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')

class Announcement(models.Model):
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

class FavoriteMovie(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_movies')
    tmdb_id = models.IntegerField()
    title = models.CharField(max_length=255)
    poster_url = models.URLField(max_length=500, blank=True, null=True)
    release_year = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

class FavoriteSong(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_songs')
    itunes_track_id = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    album = models.CharField(max_length=255, blank=True)
    artwork_url = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

class FCMToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.CharField(max_length=500, unique=True)
    device_type = models.CharField(max_length=20, default='web')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Token for {self.user.username} ({self.device_type})"

class BannedIdentifier(models.Model):
    fingerprint  = models.CharField(max_length=100, unique=True)
    reason       = models.TextField(blank=True)
    is_shadow_ban = models.BooleanField(
        default=False,
        help_text="Shadow ban: user can post but posts are never shown publicly."
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        kind = "Shadow" if self.is_shadow_ban else "Hard"
        return f"{kind} Ban: {self.fingerprint}"


class ConfessionRateLimit(models.Model):
    """Tracks confession submissions per fingerprint/IP for rate limiting."""
    identifier   = models.CharField(max_length=200, db_index=True)  # fingerprint or IP
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['submitted_at']

    def __str__(self):
        return f"RateLimit {self.identifier} @ {self.submitted_at}"


class RoomListing(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_listings')
    campus = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    distance_from_campus = models.CharField(max_length=50, blank=True)
    rent = models.PositiveIntegerField()
    advance = models.PositiveIntegerField(default=0)
    
    ROOM_TYPE_CHOICES = [
        ('1bhk', '1 BHK'),
        ('2bhk', '2 BHK'),
        ('3bhk', '3 BHK'),
        ('pg', 'PG'),
        ('hostel', 'Hostel'),
        ('shared', 'Shared Room'),
        ('flatmate', 'Flatmate Needed')
    ]
    room_type = models.CharField(max_length=50, choices=ROOM_TYPE_CHOICES)
    
    FURNISHED_CHOICES = [
        ('fully', 'Fully Furnished'),
        ('semi', 'Semi Furnished'),
        ('unfurnished', 'Unfurnished')
    ]
    furnished_status = models.CharField(max_length=50, choices=FURNISHED_CHOICES)
    
    current_occupants = models.PositiveIntegerField(default=0)
    needed_occupants = models.PositiveIntegerField(default=1)
    
    GENDER_CHOICES = [
        ('boys', 'Boys Only'),
        ('girls', 'Girls Only'),
        ('any', 'Any')
    ]
    gender_preference = models.CharField(max_length=20, choices=GENDER_CHOICES, default='any')
    food_preference = models.CharField(max_length=100, blank=True)
    smoking_drinking_preference = models.CharField(max_length=100, blank=True)
    languages_preferred = models.CharField(max_length=200, blank=True)
    
    available_from_date = models.DateField(null=True, blank=True)
    custom_note = models.TextField(blank=True)
    contact_info = models.CharField(max_length=100, blank=True, help_text="Phone number or Instagram ID")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.room_type} at {self.location} by {self.user.username}"

    @property
    def campus_display(self):
        c = get_campus_by_alias(self.campus)
        return f"{c['org']} {c['code']}" if c else self.campus


class RoomImage(models.Model):
    listing = models.ForeignKey(RoomListing, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Image for {self.listing.id}"


class SavedRoomListing(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_room_listings')
    listing = models.ForeignKey(RoomListing, on_delete=models.CASCADE, related_name='saved_by_users')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'listing')
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.username} saved {self.listing.id}"


class Conversation(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations_initiated')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations_received')
    source = models.CharField(max_length=50, default='match') # e.g. roomie_available_room, roomie_room_request, match
    listing_id = models.PositiveIntegerField(null=True, blank=True)
    request_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user1', 'user2')

    def __str__(self):
        return f"Chat: {self.user1.username} & {self.user2.username} ({self.source})"


class RoomRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_requests')
    title = models.CharField(max_length=70)
    campus = models.CharField(max_length=100)
    looking_near = models.CharField(max_length=200)
    min_rent = models.PositiveIntegerField()
    max_rent = models.PositiveIntegerField()
    
    preferred_room_type = models.CharField(max_length=50) # e.g., PG, flat, hostel, apartment, any
    sharing_preference = models.CharField(max_length=50) # e.g., single, 2 sharing, 3 sharing, any
    needed_amenities = models.CharField(max_length=200, blank=True) # comma-separated list like "WiFi,AC"
    move_in_date = models.DateField()
    extra_note = models.CharField(max_length=110, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"RoomRequest: {self.title[:20]} by {self.user.username}"

    @property
    def campus_display(self):
        c = get_campus_by_alias(self.campus)
        return f"{c['org']} {c['code']}" if c else self.campus


class StaffMember(models.Model):
    """Staff moderators who can access limited admin features."""
    email = models.EmailField(unique=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

    @property
    def user_profile(self):
        """Return the Profile if this email matches a registered user."""
        try:
            user = User.objects.get(email=self.email)
            return user.profile
        except (User.DoesNotExist, Profile.DoesNotExist):
            return None


class GiveawayEntry(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    instagram_username = models.CharField(max_length=100)
    followed_confirmed = models.BooleanField(default=False)
    shared_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - @{self.instagram_username}"


class GiveawayState(models.Model):
    """Tracks the current state of the giveaway for admin control"""
    is_active = models.BooleanField(default=False)
    winner_selection_in_progress = models.BooleanField(default=False)
    current_winner_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('first', 'First Winner'),
            ('second', 'Second Winner'),
        ],
        default='none'
    )
    # For scripted/manual winner setting
    manual_first_winner_email = models.EmailField(blank=True, null=True)
    manual_second_winner_email = models.EmailField(blank=True, null=True)
    # Timer controls
    show_timer = models.BooleanField(default=False)
    timer_duration = models.PositiveIntegerField(default=30)  # seconds
    timer_end_time = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Giveaway State: {self.get_current_winner_type_display()}"

    class Meta:
        verbose_name = "Giveaway State"
        verbose_name_plural = "Giveaway States"


class GiveawayWinner(models.Model):
    """Tracks winners of the giveaway"""
    WINNER_TYPES = [
        ('first', 'First Prize (₹1000)'),
        ('second', 'Second Prize (₹500)'),
    ]
    
    winner_type = models.CharField(max_length=10, choices=WINNER_TYPES, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='giveaway_wins')
    instagram_username = models.CharField(max_length=100)
    won_at = models.DateTimeField(auto_now_add=True)
    won_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                              related_name='giveaway_wins_awarded',
                              help_text="Admin who selected this winner")

    def __str__(self):
        return f"{self.get_winner_type_display()}: {self.user.email}"

    @property
    def display_name(self):
        """Return the profile's full name if set, never the IG handle."""
        try:
            profile = self.user.profile
            name = (getattr(profile, 'name', '') or '').strip()
        except Exception:
            name = ''
        return name if name else 'Winner'

    class Meta:
        verbose_name = "Giveaway Winner"
        verbose_name_plural = "Giveaway Winners"


class VoiceRoom(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    max_capacity = models.PositiveIntegerField(default=8)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Voice Room"
        verbose_name_plural = "Voice Rooms"


class VoiceParticipant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(VoiceRoom, on_delete=models.CASCADE, related_name='participants')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_muted = models.BooleanField(default=False)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    session_peer_id = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        unique_together = ('user', 'room')
        verbose_name = "Voice Participant"
        verbose_name_plural = "Voice Participants"

    def __str__(self):
        return f"{self.user.username} in {self.room.name}"


class BugReport(models.Model):
    BUG_CATEGORIES = [
        ('login', 'Login/Auth'), ('profile', 'Profile'), ('matching', 'Matching'),
        ('chat', 'Chat'), ('voice', 'Voice Room'), ('roomfinder', 'Room Finder'),
        ('confessions', 'Confessions'), ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('reviewing', 'Reviewing'),
        ('fixed', 'Fixed'), ('closed', 'Closed'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bug_reports')
    category = models.CharField(max_length=20, choices=BUG_CATEGORIES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    screenshot = models.URLField(blank=True, null=True)
    device_info = models.JSONField(blank=True, null=True)
    page_url = models.URLField(blank=True, max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_reply = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title[:60]}"


class FeatureSuggestion(models.Model):
    SUGGESTION_CATEGORIES = [
        ('matching', 'Matching'), ('social', 'Social'), ('chat', 'Chat'),
        ('profile', 'Profile'), ('other', 'Other'),
    ]
    PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('under_review', 'Under Review'),
        ('accepted', 'Accepted'), ('rejected', 'Rejected'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='suggestions')
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=SUGGESTION_CATEGORIES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    votes = models.IntegerField(default=0)
    admin_reply = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-votes', '-created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title[:60]}"


class SupportTicket(models.Model):
    TICKET_CATEGORIES = [
        ('account', 'Account Issue'), ('verification', 'Verification Issue'),
        ('report_user', 'Report User'), ('technical', 'Technical Issue'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'), ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=TICKET_CATEGORIES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    unread = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.subject[:60]}"


class TicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Msg by {self.sender.username} on {self.ticket.subject[:40]}"


class FeedbackNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedback_notifications')
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif for {self.user.username}: {self.message[:50]}"


CONTENT_TYPE_CHOICES = [
    ('vlog', 'Vlog'),
    ('blog', 'Blog'),
    ('photography', 'Photography'),
    ('art', 'Art'),
    ('music', 'Music'),
    ('fitness', 'Fitness'),
    ('tech', 'Tech'),
    ('fashion', 'Fashion'),
    ('other', 'Other'),
]

class CampusSpotlight(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='spotlights')
    instagram_handle = models.CharField(max_length=100)
    content_type = models.CharField(max_length=50, choices=CONTENT_TYPE_CHOICES)
    note = models.TextField(max_length=200, blank=True)
    cover_image = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.user.profile.name} (@{self.instagram_handle})"


class Event(models.Model):
    EVENT_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    FEE_TYPE = [
        ('free', 'Free'),
        ('paid', 'Paid'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=200)
    poster = models.URLField(max_length=500, blank=True)
    description = models.TextField()
    campus = models.CharField(max_length=100, blank=True)
    event_date = models.DateField()
    last_reg_date = models.DateField(blank=True, null=True)
    fee_type = models.CharField(max_length=10, choices=FEE_TYPE, default='free')
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    reg_link = models.URLField(max_length=500, blank=True)
    page_link = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=EVENT_STATUS, default='pending')
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-event_date', '-created_at']

    def __str__(self):
        return self.title

    @property
    def campus_display(self):
        c = get_campus_by_alias(self.campus)
        return f"{c['org']} {c['code']}" if c else self.campus

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.campus} {self.title}") if self.campus else slugify(self.title)
            if not base:
                base = f"event-{self.id or 'new'}"
            self.slug = base
            # ensure uniqueness
            qs = Event.objects.filter(slug=self.slug)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                import time
                self.slug = f"{base}-{int(time.time())}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('event_detail', args=[self.slug])


class Advertisement(models.Model):
    title = models.CharField(max_length=200, blank=True)
    image_url = models.URLField(max_length=500)
    link_url = models.URLField(max_length=500)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title or f"Ad #{self.id}"
