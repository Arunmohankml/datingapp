import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

from django.contrib.auth.models import User
from home.models import Profile, Question, Option, UserAnswer

# 1. Ensure questions
q1, _ = Question.objects.get_or_create(text="Do you like dogs?")
Option.objects.get_or_create(question=q1, text="Yes", weight=1.0)
Option.objects.get_or_create(question=q1, text="No", weight=0.0)

q2, _ = Question.objects.get_or_create(text="Do you like cats?")
Option.objects.get_or_create(question=q2, text="Yes", weight=1.0)
Option.objects.get_or_create(question=q2, text="No", weight=0.0)

q3, _ = Question.objects.get_or_create(text="Do you like anime?")
Option.objects.get_or_create(question=q3, text="Yes", weight=1.0)
Option.objects.get_or_create(question=q3, text="No", weight=0.0)

q4, _ = Question.objects.get_or_create(text="Do you like gym?")
Option.objects.get_or_create(question=q4, text="Yes", weight=1.0)
Option.objects.get_or_create(question=q4, text="No", weight=0.0)

q5, _ = Question.objects.get_or_create(text="Do you like reading?")
Option.objects.get_or_create(question=q5, text="Yes", weight=1.0)
Option.objects.get_or_create(question=q5, text="No", weight=0.0)

print("Questions count:", Question.objects.count())

# 2. Simulate User 1
u1, _ = User.objects.get_or_create(username='u1@test.com', defaults={'email': 'u1@test.com'})
p1, _ = Profile.objects.get_or_create(user=u1, defaults={
    'name': 'Jackson', 'gender': 'male', 'pref_gender': 'female',
    'age': 20, 'pref_age_min': 18, 'pref_age_max': 25
})

# 3. Simulate User 2
u2, _ = User.objects.get_or_create(username='u2@test.com', defaults={'email': 'u2@test.com'})
p2, _ = Profile.objects.get_or_create(user=u2, defaults={
    'name': 'Sarah', 'gender': 'female', 'pref_gender': 'male',
    'age': 20, 'pref_age_min': 18, 'pref_age_max': 25
})

print("Profiles created successfully!")

# Let's mock a POST payload to ProfileForm
from django.http import QueryDict
from home.forms import ProfileForm

qd = QueryDict('', mutable=True)
qd.update({
    'name': 'TestUser', 'gender': 'male', 'age': '20', 
    'clg_year': '2', 'pref_gender': 'female', 'looking_for': 'serious',
    'pref_age_min': '18', 'pref_age_max': '25'
})

form = ProfileForm(data=qd, instance=p1)
print("Form is valid?", form.is_valid())
if not form.is_valid():
    print(form.errors)
