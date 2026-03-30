import os
import django
import random
import firebase_admin
from firebase_admin import auth, credentials

# 1. Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

from django.contrib.auth.models import User
from home.models import Profile, Question, Option, UserAnswer

# 2. Initialize Firebase
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cert_path = os.path.join(BASE_DIR, 'serviceAccountKey.json')

if not firebase_admin._apps:
    if os.path.exists(cert_path):
        cred = credentials.Certificate(cert_path)
        firebase_admin.initialize_app(cred)
    else:
        print("Firebase serviceAccountKey.json not found! Cannot create real Firebase users.")
        exit(1)

# 3. Candidate Data
FIRST_NAMES_MALE = ["Arjun", "Aditya", "Rohan", "Vikram", "Siddharth", "Ishaan", "Kartik", "Kabir", "Aryan", "Vivaan"]
FIRST_NAMES_FEMALE = ["Ananya", "Ishita", "Sanya", "Tara", "Kiara", "Riya", "Myra", "Avni", "Zara", "Navya"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Malhotra", "Mehta", "Iyer", "Nair", "Reddy", "Singh", "Patel"]

BIOS = [
    "Exploring the campus one coffee at a time ☕. Tech enthusiast.",
    "Bored student looking for someone to grab lunch with.",
    "Into Indie movies and weekend hikes. Let's vibe!",
    "SRM KTR's finest procrastination expert. Just looking for vibes.",
    "Music is my life. Guitar player. Looking for someone with a good playlist.",
    "SRM IST - CSE Department. Coffee addict and code lover.",
    "Dancer by heart, engineer by degree. Join the vibe!",
    "Passionate about startups and high-impact ideas. Let's talk business.",
    "Just looking for a good friend to study (or chill) with.",
    "Foodie. I know all the best spots around campus 🍕."
]

INTERESTS = ["Reading", "Movies", "Cricket", "Coding", "Music", "Photography", "Travel", "Dance", "Cooking", "Gaming"]

def seed():
    print("Seeding 20 test accounts...")
    
    questions = list(Question.objects.prefetch_related('options').all())
    if not questions:
        print("No questions found in DB! Seed questions first.")
        return

    for i in range(20):
        is_male = i < 10
        first_name = FIRST_NAMES_MALE[i] if is_male else FIRST_NAMES_FEMALE[i-10]
        last_name = random.choice(LAST_NAMES)
        full_name = f"{first_name} {last_name}"
        email = f"test_{first_name.lower()}_{random.randint(100,999)}@srmist.edu.in"
        password = "testpassword123"
        gender = "male" if is_male else "female"
        
        print(f"Creating user {i+1}/20: {full_name} ({email})")
        
        try:
            # A. Create Firebase User
            fb_user = auth.create_user(
                email=email,
                password=password,
                display_name=full_name
            )
            
            # B. Create Django User
            django_user = User.objects.create_user(username=email, email=email)
            
            # C. Create/Update Profile
            profile, _ = Profile.objects.get_or_create(user=django_user)
            profile.name = full_name
            profile.gender = gender
            profile.age = random.randint(18, 22)
            profile.clg_year = random.randint(1, 4)
            profile.campus = random.choice(["KTR", "RPM", "VDP", "RMP"])
            profile.branch = random.choice(["CSE", "IT", "ECE", "MECH", "CIVIL", "BIOTECH"])
            profile.bio = random.choice(BIOS)
            profile.interest_tags = random.sample(INTERESTS, 3)
            # Use DiceBear for PFP
            # In Django models, we can store URLs in the image field as a hack, but let's just make sure the UI handles it.
            # profile.profile_pic = f"https://api.dicebear.com/7.x/avataaars/svg?seed={first_name}"
            
            # D. Randomize 50 Answers for the user to enable matching
            sampled_qs = random.sample(questions, 50)
            user_answers = []
            for q in sampled_qs:
                options = q.options.all()
                if options:
                    user_answers.append(UserAnswer(
                        user=django_user,
                        question=q,
                        option=random.choice(options)
                    ))
            
            UserAnswer.objects.bulk_create(user_answers)
            profile.save()
            
        except Exception as e:
            print(f"Failed to create user {full_name}: {e}")

    print("Seeding Complete!")

if __name__ == "__main__":
    seed()
