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
    branch = models.CharField(max_length=100, default='', blank=True)

    # Places
    living_place = models.CharField(max_length=100, default='', blank=True)
    native_place = models.CharField(max_length=100, default='', blank=True)

    # Language
    languages = models.JSONField(default=list)
    mother_tongues = models.JSONField(default=list)

    # Personal
    bio = models.TextField(blank=True)
    liked_songs = models.TextField(blank=True)
    liked_movies = models.TextField(blank=True)
    fav_shows = models.TextField(blank=True)
    interest_tags = models.JSONField(default=list)
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
    pref_languages = models.JSONField(default=list)
    pref_campus = models.CharField(max_length=100, blank=True)
    pref_branch = models.CharField(max_length=100, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.user.email}"

    @property
    def get_profile_pic_url(self):
        # Ensure we are dealing with a string before checking for URL prefix
        if isinstance(self.profile_pic, str) and (self.profile_pic.startswith('http://') or self.profile_pic.startswith('https://')):
            return self.profile_pic
        # Fallback to a nice avatar placeholder if the URL is broken, relative, or a temporary file object
        name_param = self.name.replace(" ", "+") if self.name else "User"
        return f"https://ui-avatars.com/api/?name={name_param}&background=6366f1&color=fff&size=256"

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
