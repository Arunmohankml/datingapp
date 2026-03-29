import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

from django.contrib.auth.models import User
from home.models import Question, Option, Profile, UserAnswer, MatchRequest, Message

# No wiping needed as the db is fresh.

# 2. Generate 1000 Questions
print("Generating 1000 questions...")

topics = [
    "Cats", "Dogs", "Reading", "Running", "Hiking", "Swimming", "Camping", "Video Games",
    "Board Games", "Cooking", "Baking", "Eating Out", "Coffee", "Tea", "Wine", "Beer",
    "Cocktails", "Movies", "Theater", "Concerts", "Festivals", "Museums", "Art Galleries",
    "Photography", "Painting", "Writing", "Poetry", "History", "Science", "Technology",
    "Programming", "Startups", "Investing", "Crypto", "Politics", "Volunteering",
    "Road Trips", "Flying", "Cruises", "Beach Vacations", "Mountain Cabins", "City Breaks",
    "Yoga", "Meditation", "Astrology", "Tarot", "Horror Movies", "Sci-Fi", "Fantasy",
    "Rom-Coms", "Thrillers", "Documentaries", "Reality TV", "Anime", "Manga", "Comics",
    "Marvel", "DC", "Star Wars", "Star Trek", "Harry Potter", "Lord of the Rings",
    "Pop Music", "Rock Music", "Hip Hop", "R&B", "Jazz", "Classical Music", "EDM",
    "Country Music", "Playing Guitar", "Playing Piano", "Singing", "Dancing", "Clubbing",
    "House Parties", "Dinner Parties", "Quiet Nights In", "Early Mornings", "Late Nights",
    "Winter", "Summer", "Spring", "Autumn", "Snow", "Rain", "Thunderstorms", "Sunny Days",
    "Spicy Food", "Sweet Food", "Salty Food", "Vegetarian Food", "Vegan Food", "Sushi",
    "Pizza", "Burgers", "Tacos", "Pasta", "Steak", "Salads", "Fast Food", "Fine Dining",
    "Thrifting", "High Fashion", "Streetwear", "Minimalism", "Tattoos", "Piercings",
    "Dyeing Hair", "Working Out", "CrossFit", "Powerlifting", "Bodybuilding", "Martial Arts",
    "Boxing", "Wrestling", "UFC", "Basketball", "Football", "Soccer", "Baseball",
    "Hockey", "Tennis", "Golf", "Surfing", "Skateboarding", "Snowboarding", "Skiing",
    "Motorcycles", "Sports Cars", "Off-Roading", "Boating", "Fishing", "Hunting",
    "Gardening", "Houseplants", "DIY Projects", "Woodworking", "Knitting", "Sewing",
    "Pottery", "Sculpting"
]

actions = [
    "Do you enjoy",
    "Are you interested in",
    "How do you feel about",
    "What's your stance on",
    "Do you spend time",
    "Are you passionate about",
    "Do you like",
    "Are you a fan of",
    "Do you frequently engage in",
    "Is a dealbreaker for you if someone doesn't like",
]

adjectives = [
    "casual", "competitive", "intense", "relaxing", "frequent", "occasional", "rare", "daily"
]

# Generate unique questions
unique_questions = set()
while len(unique_questions) < 1000:
    action = random.choice(actions)
    topic = random.choice(topics)
    
    if "dealbreaker" in action:
        q_text = f"{action} {topic}?"
    elif "spend time" in action or "engage in" in action:
        adj = random.choice(adjectives)
        q_text = f"{action} {adj} {topic}?"
    else:
        q_text = f"{action} {topic}?"
        
    unique_questions.add(q_text)

# Save to DB
questions_list = list(unique_questions)
db_questions = []

for q_text in questions_list:
    q = Question(text=q_text)
    db_questions.append(q)

# Bulk create questions
Question.objects.bulk_create(db_questions)
print("Created 1000 questions.")

# Now fetch them and create options
all_qs = Question.objects.all()
options_to_create = []

for q in all_qs:
    # We create 4 standard options for each to represent weights
    options_to_create.extend([
        Option(question=q, text="Absolutely Love It", weight=1.0),
        Option(question=q, text="It's Okay", weight=0.6),
        Option(question=q, text="Not Really", weight=0.3),
        Option(question=q, text="Hate It", weight=0.0)
    ])

# Batch size 1000 to avoid memory issues
batch_size = 1000
for i in range(0, len(options_to_create), batch_size):
    Option.objects.bulk_create(options_to_create[i:i+batch_size])

print("Created 4000 options.")
print("All Done! The database now has 1000 valid questions and 0 fake accounts.")
