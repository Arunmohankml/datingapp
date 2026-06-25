from django import forms
from .models import Profile, ProfileImage
from .campus_config import get_campus_options

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
CAMPUS_CHOICES = [('', 'Select Campus')] + get_campus_options()
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
    ('B.Com', 'B.Com'),
    ('BA', 'BA'),
    ('MA', 'MA'),
    ('B.Arch', 'B.Arch'),
    ('Medical', 'Medical'),
    ('Ph.D', 'Ph.D'),
    ('Other', 'Other'),
]

LOCATION_CHOICES = [
    ('', 'Select Native Place'),
    ('Kochi, Kerala', 'Kochi, Kerala'),
    ('Trivandrum, Kerala', 'Trivandrum, Kerala'),
    ('Calicut, Kerala', 'Calicut, Kerala'),
    ('Chennai, Tamil Nadu', 'Chennai, Tamil Nadu'),
    ('Coimbatore, Tamil Nadu', 'Coimbatore, Tamil Nadu'),
    ('Madurai, Tamil Nadu', 'Madurai, Tamil Nadu'),
    ('Bangalore, Karnataka', 'Bangalore, Karnataka'),
    ('Mysore, Karnataka', 'Mysore, Karnataka'),
    ('Mangalore, Karnataka', 'Mangalore, Karnataka'),
    ('Hubli, Karnataka', 'Hubli, Karnataka'),
    ('Hyderabad, Telangana', 'Hyderabad, Telangana'),
    ('Warangal, Telangana', 'Warangal, Telangana'),
    ('Nizamabad, Telangana', 'Nizamabad, Telangana'),
    ('Karimnagar, Telangana', 'Karimnagar, Telangana'),
    ('Delhi, NCR', 'Delhi, NCR'),
    ('Noida, Uttar Pradesh', 'Noida, Uttar Pradesh'),
    ('Gurgaon, Haryana', 'Gurgaon, Haryana'),
    ('Faridabad, Haryana', 'Faridabad, Haryana'),
    ('Mumbai, Maharashtra', 'Mumbai, Maharashtra'),
    ('Pune, Maharashtra', 'Pune, Maharashtra'),
    ('Nagpur, Maharashtra', 'Nagpur, Maharashtra'),
    ('Nashik, Maharashtra', 'Nashik, Maharashtra'),
    ('Aurangabad, Maharashtra', 'Aurangabad, Maharashtra'),
    ('Vellore, Tamil Nadu', 'Vellore, Tamil Nadu'),
    ('Chengalpattu, Tamil Nadu', 'Chengalpattu, Tamil Nadu'),
    ('Kanchipuram, Tamil Nadu', 'Kanchipuram, Tamil Nadu'),
    ('Trichy, Tamil Nadu', 'Trichy, Tamil Nadu'),
    ('Kozhikode, Kerala', 'Kozhikode, Kerala'),
    ('Kannur, Kerala', 'Kannur, Kerala'),
    ('Kollam, Kerala', 'Kollam, Kerala'),
    ('Malappuram, Kerala', 'Malappuram, Kerala'),
    ('Jaipur, Rajasthan', 'Jaipur, Rajasthan'),
    ('Udaipur, Rajasthan', 'Udaipur, Rajasthan'),
    ('Jodhpur, Rajasthan', 'Jodhpur, Rajasthan'),
    ('Kota, Rajasthan', 'Kota, Rajasthan'),
    ('Kolkata, West Bengal', 'Kolkata, West Bengal'),
    ('Siliguri, West Bengal', 'Siliguri, West Bengal'),
    ('Durgapur, West Bengal', 'Durgapur, West Bengal'),
    ('Asansol, West Bengal', 'Asansol, West Bengal'),
    ('Visakhapatnam, Andhra Pradesh', 'Visakhapatnam, Andhra Pradesh'),
    ('Vijayawada, Andhra Pradesh', 'Vijayawada, Andhra Pradesh'),
    ('Guntur, Andhra Pradesh', 'Guntur, Andhra Pradesh'),
    ('Tirupati, Andhra Pradesh', 'Tirupati, Andhra Pradesh'),
    ('Lucknow, Uttar Pradesh', 'Lucknow, Uttar Pradesh'),
    ('Kanpur, Uttar Pradesh', 'Kanpur, Uttar Pradesh'),
    ('Varanasi, Uttar Pradesh', 'Varanasi, Uttar Pradesh'),
    ('Prayagraj, Uttar Pradesh', 'Prayagraj, Uttar Pradesh'),
    ('Agra, Uttar Pradesh', 'Agra, Uttar Pradesh'),
    ('Meerut, Uttar Pradesh', 'Meerut, Uttar Pradesh'),
    ('Patna, Bihar', 'Patna, Bihar'),
    ('Gaya, Bihar', 'Gaya, Bihar'),
    ('Muzaffarpur, Bihar', 'Muzaffarpur, Bihar'),
    ('Bhagalpur, Bihar', 'Bhagalpur, Bihar'),
    ('Bhopal, Madhya Pradesh', 'Bhopal, Madhya Pradesh'),
    ('Indore, Madhya Pradesh', 'Indore, Madhya Pradesh'),
    ('Jabalpur, Madhya Pradesh', 'Jabalpur, Madhya Pradesh'),
    ('Gwalior, Madhya Pradesh', 'Gwalior, Madhya Pradesh'),
    ('Raipur, Chhattisgarh', 'Raipur, Chhattisgarh'),
    ('Bilaspur, Chhattisgarh', 'Bilaspur, Chhattisgarh'),
    ('Durg, Chhattisgarh', 'Durg, Chhattisgarh'),
    ('Ranchi, Jharkhand', 'Ranchi, Jharkhand'),
    ('Jamshedpur, Jharkhand', 'Jamshedpur, Jharkhand'),
    ('Dhanbad, Jharkhand', 'Dhanbad, Jharkhand'),
    ('Bhubaneswar, Odisha', 'Bhubaneswar, Odisha'),
    ('Cuttack, Odisha', 'Cuttack, Odisha'),
    ('Rourkela, Odisha', 'Rourkela, Odisha'),
    ('Sambalpur, Odisha', 'Sambalpur, Odisha'),
    ('Ahmedabad, Gujarat', 'Ahmedabad, Gujarat'),
    ('Surat, Gujarat', 'Surat, Gujarat'),
    ('Vadodara, Gujarat', 'Vadodara, Gujarat'),
    ('Rajkot, Gujarat', 'Rajkot, Gujarat'),
    ('Gandhinagar, Gujarat', 'Gandhinagar, Gujarat'),
    ('Chandigarh, Punjab', 'Chandigarh, Punjab'),
    ('Amritsar, Punjab', 'Amritsar, Punjab'),
    ('Ludhiana, Punjab', 'Ludhiana, Punjab'),
    ('Jalandhar, Punjab', 'Jalandhar, Punjab'),
    ('Patiala, Punjab', 'Patiala, Punjab'),
    ('Shimla, Himachal Pradesh', 'Shimla, Himachal Pradesh'),
    ('Manali, Himachal Pradesh', 'Manali, Himachal Pradesh'),
    ('Dharamshala, Himachal Pradesh', 'Dharamshala, Himachal Pradesh'),
    ('Dehradun, Uttarakhand', 'Dehradun, Uttarakhand'),
    ('Haridwar, Uttarakhand', 'Haridwar, Uttarakhand'),
    ('Rishikesh, Uttarakhand', 'Rishikesh, Uttarakhand'),
    ('Srinagar, Jammu and Kashmir', 'Srinagar, Jammu and Kashmir'),
    ('Jammu, Jammu and Kashmir', 'Jammu, Jammu and Kashmir'),
    ('Leh, Ladakh', 'Leh, Ladakh'),
    ('Panaji, Goa', 'Panaji, Goa'),
    ('Margao, Goa', 'Margao, Goa'),
    ('Imphal, Manipur', 'Imphal, Manipur'),
    ('Shillong, Meghalaya', 'Shillong, Meghalaya'),
    ('Aizawl, Mizoram', 'Aizawl, Mizoram'),
    ('Kohima, Nagaland', 'Kohima, Nagaland'),
    ('Itanagar, Arunachal Pradesh', 'Itanagar, Arunachal Pradesh'),
    ('Agartala, Tripura', 'Agartala, Tripura'),
    ('Gangtok, Sikkim', 'Gangtok, Sikkim'),
    ('Guwahati, Assam', 'Guwahati, Assam'),
    ('Silchar, Assam', 'Silchar, Assam'),
    ('Dibrugarh, Assam', 'Dibrugarh, Assam'),
    ('Tinsukia, Assam', 'Tinsukia, Assam'),
    ('Port Blair, AN', 'Port Blair, AN'),
    ('Puducherry, Puducherry', 'Puducherry, Puducherry'),
    ('Karaikal, Puducherry', 'Karaikal, Puducherry'),
    ('Daman, D&D', 'Daman, D&D'),
    ('Silvassa, D&D', 'Silvassa, D&D'),
]


class ProfileInitForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['name', 'age', 'gender', 'campus', 'native_place']
        widgets = {
            'gender': forms.Select(choices=GENDER_CHOICES, attrs={'class': 'form-control'}),
            'campus': forms.Select(choices=CAMPUS_CHOICES, attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'min': 18, 'max': 50}),
            'native_place': forms.Select(choices=LOCATION_CHOICES, attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ['name', 'age', 'gender', 'campus', 'native_place']:
            self.fields[field].required = True

    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age is not None:
            if age < 18 or age > 50:
                raise forms.ValidationError("Age must be between 18 and 50.")
        return age


class ProfileForm(forms.ModelForm):
    profile_pic_file = forms.ImageField(required=False, label="Upload Photo", widget=forms.FileInput(attrs={'class': 'form-control'}))
    # Multiselect (JSON) fields as comma-separated strings
    languages = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'English, Tamil, Hindi'})
    )
    mother_tongues = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Hindi, Telugu'})
    )
    interest_tags = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'anime, food, humor'})
    )
    pref_languages = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'English, Hindi'})
    )
    profile_pic_url = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Profile
        fields = [
            'name', 'gender', 'age', 'clg_year', 'campus', 'course',
            'living_place', 'native_place',
            'languages', 'mother_tongues',
            'bio', 'liked_songs', 'liked_movies', 'fav_shows', 'interest_tags', 'looking_for',
            'pref_age_min', 'pref_age_max', 'pref_gender', 'pref_languages', 'is_discoverable',
        ]
        widgets = {
            'gender': forms.Select(choices=GENDER_CHOICES, attrs={'class': 'form-control'}),
            'looking_for': forms.Select(choices=LOOKING_FOR_CHOICES, attrs={'class': 'form-control'}),
            'pref_gender': forms.Select(choices=PREF_GENDER_CHOICES, attrs={'class': 'form-control'}),
            'clg_year': forms.Select(choices=YEAR_CHOICES, attrs={'class': 'form-control'}),
            'campus': forms.Select(choices=CAMPUS_CHOICES, attrs={'class': 'form-control'}),
            'course': forms.Select(choices=COURSE_CHOICES, attrs={'class': 'form-control'}),

            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Write a short bio...'}),
            'liked_songs': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'liked_movies': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'fav_shows': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'pref_age_max': forms.NumberInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make specific fields mandatory for completion
        mandatory_fields = [
            'living_place', 'native_place', 
            'clg_year', 'campus', 'course',
            'pref_age_min', 'pref_age_max', 'pref_gender', 'age', 'interest_tags', 'bio'
        ]
        for field in mandatory_fields:
            if field in self.fields:
                self.fields[field].required = True

        # Convert list fields to comma-separated strings for the form
        if self.instance and self.instance.pk:
            if isinstance(self.instance.languages, list):
                self.initial['languages'] = ', '.join(self.instance.languages)
            if isinstance(self.instance.mother_tongues, list):
                self.initial['mother_tongues'] = ', '.join(self.instance.mother_tongues)
            if isinstance(self.instance.interest_tags, list):
                self.initial['interest_tags'] = ', '.join(self.instance.interest_tags)
            if isinstance(self.instance.pref_languages, list):
                self.initial['pref_languages'] = ', '.join(self.instance.pref_languages)

    def clean_languages(self):
        data = self.cleaned_data.get('languages', '')
        if isinstance(data, list): return ",".join(data)
        tags = [x.strip() for x in data.split(',') if x.strip()]
        return ",".join(tags)

    def clean_mother_tongues(self):
        data = self.cleaned_data.get('mother_tongues', '')
        if isinstance(data, list): return ",".join(data)
        tags = [x.strip() for x in data.split(',') if x.strip()]
        return ",".join(tags)

    def clean_interest_tags(self):
        data = self.cleaned_data.get('interest_tags', '')
        if isinstance(data, list): return ",".join(data)
        tags = [x.strip() for x in data.split(',') if x.strip()]
        return ",".join(tags)

    def clean_pref_languages(self):
        data = self.cleaned_data.get('pref_languages', '')
        if isinstance(data, list): return ",".join(data)
        tags = [x.strip() for x in data.split(',') if x.strip()]
        return ",".join(tags)

    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age is not None:
            if age < 18 or age > 50:
                raise forms.ValidationError("Age must be between 18 and 50.")
        return age

    def clean(self):
        cleaned_data = super().clean()
        pfp_url = cleaned_data.get('profile_pic_url')
        pfp_file = cleaned_data.get('profile_pic_file')
        
        if not pfp_url and not pfp_file:
            # We don't raise a field-specific error because we want to catch both
            raise forms.ValidationError("Profile picture is required.")
        return cleaned_data

class ProfileEditForm(forms.ModelForm):
    profile_pic_file = forms.ImageField(required=False, label="Upload Photo", widget=forms.FileInput(attrs={'class': 'form-control'}))
    languages = forms.CharField(required=False, widget=forms.HiddenInput())
    mother_tongues = forms.CharField(required=False, widget=forms.HiddenInput())
    interest_tags = forms.CharField(required=False, widget=forms.HiddenInput())
    pref_languages = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Profile
        fields = [
            'name', 'bio', 'age', 'languages', 'mother_tongues', 'interest_tags', 
            'living_place', 'native_place',
            'clg_year', 'campus', 'course',
            'pref_age_min', 'pref_age_max', 'pref_gender', 'pref_languages',
            'looking_for', 'is_discoverable'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'pref_gender': forms.Select(choices=PREF_GENDER_CHOICES, attrs={'class': 'form-control'}),
            'looking_for': forms.Select(choices=LOOKING_FOR_CHOICES, attrs={'class': 'form-control'}),
            'pref_age_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'pref_age_max': forms.NumberInput(attrs={'class': 'form-control'}),
            'clg_year': forms.Select(choices=YEAR_CHOICES, attrs={'class': 'form-control'}),
            'campus': forms.Select(choices=CAMPUS_CHOICES, attrs={'class': 'form-control', 'disabled': 'disabled'}),
            'course': forms.Select(choices=COURSE_CHOICES, attrs={'class': 'form-control'}),

        }

    def clean_languages(self):
        data = self.cleaned_data.get('languages', '')
        tags = [x.strip() for x in data.split(',') if x.strip()]
        return ",".join(tags)

    def clean_mother_tongues(self):
        data = self.cleaned_data.get('mother_tongues', '')
        tags = [x.strip() for x in data.split(',') if x.strip()]
        return ",".join(tags)

    def clean_interest_tags(self):
        data = self.cleaned_data.get('interest_tags', '')
        tags = [x.strip() for x in data.split(',') if x.strip()]
        return ",".join(tags)

    def clean_pref_languages(self):
        data = self.cleaned_data.get('pref_languages', '')
        tags = [x.strip() for x in data.split(',') if x.strip()]
        return ",".join(tags)

    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age is not None:
            if age < 18 or age > 50:
                raise forms.ValidationError("Age must be between 18 and 50.")
        return age

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TextField values are handled perfectly by Django's default logic now.

class ProfileImageForm(forms.ModelForm):
    image_file = forms.ImageField(required=True, label="Gallery Photo", widget=forms.FileInput(attrs={'class': 'form-control'}))
    class Meta:
        model = ProfileImage
        fields = ['image_file']
