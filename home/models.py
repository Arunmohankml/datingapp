from django.db import models
from django.contrib.auth.models import User

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

    def __str__(self):
        return f"{self.name} - {self.user.email}"

    @property
    def campus_display(self):
        if self.campus == 'Ramapuram':
            return 'RMP Campus'
        return self.campus

    @property
    def get_profile_pic_url(self):
        # Ensure we are dealing with a string before checking for URL prefix
        if isinstance(self.profile_pic, str) and (self.profile_pic.startswith('http://') or self.profile_pic.startswith('https://')):
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
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    image = models.URLField(max_length=500, blank=True, null=True)
    campus = models.CharField(max_length=100, blank=True, default='')
    is_anonymous = models.BooleanField(default=True)
    likes_count = models.PositiveIntegerField(default=0)
    is_flagged = models.BooleanField(default=False)
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


class ConfessionComment(models.Model):
    confession = models.ForeignKey(Confession, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    is_anonymous = models.BooleanField(default=True)
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reasons = models.JSONField(default=list) # List of selected reasons
    other_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('confession', 'user')

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
