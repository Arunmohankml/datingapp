from django import forms
from .models import Profile

# ✅ Move choices outside Meta
GENDER_CHOICES = [
    ('male', 'Male'),
    ('female', 'Female'),
    ('other', 'Other'),
]

LOOKING_FOR_CHOICES = [
    ('friendship', 'Friendship'),
    ('serious', 'Relationship'),
    ('vibe', 'Just vibing'),
]

PREF_GENDER_CHOICES = [
    ('male', 'Male'),
    ('female', 'Female'),
    ('any', 'Any'),
]

YEAR_CHOICES = [('', 'Select Year')] + [(y, str(y)) for y in range(1, 6)]
CAMPUS_CHOICES = [
    ('', 'Select Campus'),
    ('Kattankulathur (KTR)', 'Kattankulathur (KTR)'),
    ('Ramapuram', 'Ramapuram'),
    ('Vadapalani', 'Vadapalani'),
    ('NCR Modinagar', 'NCR Modinagar'),
    ('Tiruchirappalli', 'Tiruchirappalli'),
    ('SRM AP', 'SRM AP'),
]
COURSE_CHOICES = [
    ('', 'Select Course'),
    ('B.Tech', 'B.Tech'),
    ('M.Tech', 'M.Tech'),
    ('MBA', 'MBA'),
    ('BBA', 'BBA'),
    ('BCA', 'BCA'),
    ('MCA', 'MCA'),
    ('B.Sc', 'B.Sc'),
    ('M.Sc', 'M.Sc'),
    ('BA', 'BA'),
    ('MA', 'MA'),
    ('Ph.D', 'Ph.D'),
    ('Other', 'Other'),
]
BRANCH_CHOICES = [
    ('', 'Select Branch'),
    ('CSE', 'Computer Science (CSE)'),
    ('ECE', 'Electronics & Comm. (ECE)'),
    ('EEE', 'Electrical & Electronics (EEE)'),
    ('Mechanical', 'Mechanical Engineering'),
    ('Civil', 'Civil Engineering'),
    ('IT', 'Information Technology (IT)'),
    ('Biotech', 'Biotechnology'),
    ('AI/ML', 'AI & Machine Learning'),
    ('Data Science', 'Data Science'),
    ('Cyber Security', 'Cyber Security'),
    ('Other', 'Other'),
]

class ProfileForm(forms.ModelForm):
    # Multiselect (JSON) fields as comma-separated strings
    languages = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'English, Tamil, Hindi'})
    )
    mother_tongues = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Hindi, Telugu'})
    )
    interest_tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'anime, food, humor'})
    )
    pref_languages = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'English, Hindi'})
    )

    class Meta:
        model = Profile
        fields = [
            'name', 'gender', 'profile_pic', 'age', 'clg_year', 'campus', 'course', 'branch',
            'living_place', 'native_place',
            'languages', 'mother_tongues',
            'bio', 'liked_songs', 'liked_movies', 'fav_shows', 'interest_tags', 'looking_for',
            'pref_age_min', 'pref_age_max', 'pref_gender', 'pref_languages',
            'pref_campus', 'pref_branch'
        ]
        widgets = {
            'gender': forms.Select(choices=GENDER_CHOICES, attrs={'class': 'form-control'}),
            'looking_for': forms.Select(choices=LOOKING_FOR_CHOICES, attrs={'class': 'form-control'}),
            'pref_gender': forms.Select(choices=PREF_GENDER_CHOICES, attrs={'class': 'form-control'}),
            'clg_year': forms.Select(choices=YEAR_CHOICES, attrs={'class': 'form-control'}),
            'campus': forms.Select(choices=CAMPUS_CHOICES, attrs={'class': 'form-control'}),
            'course': forms.Select(choices=COURSE_CHOICES, attrs={'class': 'form-control'}),
            'branch': forms.Select(choices=BRANCH_CHOICES, attrs={'class': 'form-control'}),
            'pref_campus': forms.Select(choices=[('any', 'Any Campus')] + [c for c in CAMPUS_CHOICES if c[0] != ''], attrs={'class': 'form-control'}),
            'pref_branch': forms.Select(choices=[('any', 'Any Branch')] + [c for c in BRANCH_CHOICES if c[0] != ''], attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write a short bio...'}),
            'liked_songs': forms.Textarea(attrs={'rows': 2}),
            'liked_movies': forms.Textarea(attrs={'rows': 2}),
            'fav_shows': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_languages(self):
        data = self.cleaned_data.get('languages', '')
        if isinstance(data, list): return data
        return [x.strip() for x in data.split(',') if x.strip()]

    def clean_mother_tongues(self):
        data = self.cleaned_data.get('mother_tongues', '')
        if isinstance(data, list): return data
        return [x.strip() for x in data.split(',') if x.strip()]

    def clean_interest_tags(self):
        data = self.cleaned_data.get('interest_tags', '')
        if isinstance(data, list): return data
        return [x.strip() for x in data.split(',') if x.strip()]

    def clean_pref_languages(self):
        data = self.cleaned_data.get('pref_languages', '')
        if isinstance(data, list): return data
        return [x.strip() for x in data.split(',') if x.strip()]
