from django.core.management.base import BaseCommand
from home.models import Question, Option

class Command(BaseCommand):
    help = "Seed 50 questions with options"

    def handle(self, *args, **kwargs):
        questions_data = [
            {"text": "Favorite color?", "options": ["Red", "Blue", "Green"]},
            {"text": "Dream vacation?", "options": ["Beach", "Mountains", "City"]},
            # ... add 50
            {"text": "Favorite color?", "options": ["Red", "Blue", "Green", "Black"]},
            {"text": "Dream vacation?", "options": ["Beach", "Mountains", "City", "Countryside"]},
            {"text": "Coffee or tea?", "options": ["Coffee", "Tea", "Both", "Neither"]},
            {"text": "Morning or night person?", "options": ["Morning", "Night", "Depends", "Both"]},
            {"text": "Favorite season?", "options": ["Summer", "Winter", "Spring", "Autumn"]},
            {"text": "Pet preference?", "options": ["Dog", "Cat", "Both", "Neither"]},
            {"text": "Ideal first date?", "options": ["Dinner", "Movie", "Walk", "Adventure"]},
            {"text": "Favorite cuisine?", "options": ["Italian", "Indian", "Chinese", "Mexican"]},
            {"text": "Introvert or extrovert?", "options": ["Introvert", "Extrovert", "Ambivert", "Depends"]},
            {"text": "Do you like reading?", "options": ["Yes", "No", "Sometimes", "Only audiobooks"]},

            {"text": "Favorite movie genre?", "options": ["Action", "Romance", "Comedy", "Horror"]},
            {"text": "Sweet or savory snacks?", "options": ["Sweet", "Savory", "Both", "Depends"]},
            {"text": "Are you into sports?", "options": ["Yes", "No", "Sometimes", "Only watching"]},
            {"text": "Dream car?", "options": ["Sports car", "SUV", "Bike", "Luxury sedan"]},
            {"text": "Favorite music genre?", "options": ["Pop", "Rock", "Hip-hop", "Classical"]},
            {"text": "Would you rather travel to space or deep sea?", "options": ["Space", "Deep sea", "Neither", "Both"]},
            {"text": "Texting or calling?", "options": ["Texting", "Calling", "Depends", "Both"]},
            {"text": "Do you like surprises?", "options": ["Yes", "No", "Sometimes", "Depends on surprise"]},
            {"text": "Favorite ice cream flavor?", "options": ["Chocolate", "Vanilla", "Strawberry", "Cookies & Cream"]},
            {"text": "Workout preference?", "options": ["Gym", "Yoga", "Running", "None"]},

            {"text": "Beach or mountains?", "options": ["Beach", "Mountains", "Both", "Neither"]},
            {"text": "Do you believe in love at first sight?", "options": ["Yes", "No", "Maybe", "Not sure"]},
            {"text": "Favorite social media app?", "options": ["Instagram", "Twitter", "Snapchat", "Facebook"]},
            {"text": "Biggest turn-on?", "options": ["Confidence", "Humor", "Looks", "Kindness"]},
            {"text": "Biggest dealbreaker?", "options": ["Lying", "Disrespect", "Arrogance", "Smoking"]},
            {"text": "How do you spend weekends?", "options": ["Party", "Relax at home", "Travel", "Work"]},
            {"text": "Cooking skills?", "options": ["Pro", "Beginner", "Average", "Burns water"]},
            {"text": "Do you believe in astrology?", "options": ["Yes", "No", "Sometimes", "A little"]},
            {"text": "Morning routine?", "options": ["Workout", "Scroll phone", "Breakfast", "Sleep in"]},
            {"text": "Night routine?", "options": ["Netflix", "Reading", "Gaming", "Sleep"]},

            {"text": "Favorite type of books?", "options": ["Fiction", "Non-fiction", "Self-help", "Fantasy"]},
            {"text": "Do you play video games?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Board games or card games?", "options": ["Board games", "Card games", "Both", "Neither"]},
            {"text": "Concerts or clubs?", "options": ["Concerts", "Clubs", "Both", "Neither"]},
            {"text": "Do you like tattoos?", "options": ["Yes", "No", "Depends", "On others only"]},
            {"text": "Do you like piercings?", "options": ["Yes", "No", "Depends", "On others only"]},
            {"text": "Favorite alcoholic drink?", "options": ["Beer", "Wine", "Whiskey", "Cocktail"]},
            {"text": "Do you dance?", "options": ["Yes", "No", "Sometimes", "Only when drunk"]},
            {"text": "Favorite pizza topping?", "options": ["Pepperoni", "Veggies", "Cheese", "Chicken"]},
            {"text": "Sunrise or sunset?", "options": ["Sunrise", "Sunset", "Both", "Neither"]},

            {"text": "How often do you exercise?", "options": ["Daily", "Weekly", "Rarely", "Never"]},
            {"text": "Do you meditate?", "options": ["Yes", "No", "Sometimes", "Want to start"]},
            {"text": "Favorite TV show genre?", "options": ["Drama", "Comedy", "Thriller", "Reality"]},
            {"text": "Do you enjoy cooking together?", "options": ["Yes", "No", "Sometimes", "Depends"]},
            {"text": "Do you like long drives?", "options": ["Yes", "No", "Sometimes", "Depends"]},
            {"text": "Favorite festival?", "options": ["Christmas", "Diwali", "Eid", "New Year"]},
            {"text": "Do you believe in fate?", "options": ["Yes", "No", "Sometimes", "Not sure"]},
            {"text": "Do you want kids?", "options": ["Yes", "No", "Maybe", "Not sure"]},
            {"text": "Are you religious?", "options": ["Yes", "No", "Spiritual", "Agnostic"]},
            {"text": "Favorite kind of weather?", "options": ["Rainy", "Sunny", "Snowy", "Windy"]},

            {"text": "Do you like spicy food?", "options": ["Yes", "No", "Sometimes", "Mild only"]},
            {"text": "Are you a planner or spontaneous?", "options": ["Planner", "Spontaneous", "Both", "Depends"]},
            {"text": "Do you snore?", "options": ["Yes", "No", "Sometimes", "Don’t know"]},
            {"text": "Do you enjoy hiking?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Do you like board games?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Do you like karaoke?", "options": ["Yes", "No", "Sometimes", "Only with friends"]},
            {"text": "Favorite fast food?", "options": ["Burger", "Pizza", "Fries", "Sandwich"]},
            {"text": "Do you like road trips?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Dream job?", "options": ["Entrepreneur", "Artist", "Scientist", "Traveler"]},
            {"text": "Do you believe in ghosts?", "options": ["Yes", "No", "Maybe", "Not sure"]},

            {"text": "Do you like museums?", "options": ["Yes", "No", "Sometimes", "Depends"]},
            {"text": "Favorite subject in school?", "options": ["Math", "Science", "History", "Art"]},
            {"text": "Do you believe in second chances?", "options": ["Yes", "No", "Depends", "Not sure"]},
            {"text": "Do you cook at home?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Favorite fruit?", "options": ["Apple", "Banana", "Mango", "Grapes"]},
            {"text": "Favorite vegetable?", "options": ["Carrot", "Potato", "Spinach", "Broccoli"]},
            {"text": "Do you like picnics?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Do you like swimming?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Do you watch anime?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Favorite dessert?", "options": ["Cake", "Ice cream", "Brownie", "Donut"]},

            {"text": "Do you like gardening?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Favorite outdoor activity?", "options": ["Cycling", "Running", "Picnic", "Hiking"]},
            {"text": "Do you believe in luck?", "options": ["Yes", "No", "Sometimes", "Not sure"]},
            {"text": "Do you like art?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Favorite drink?", "options": ["Juice", "Soda", "Coffee", "Water"]},
            {"text": "Do you like writing?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Do you like poetry?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Favorite holiday activity?", "options": ["Traveling", "Shopping", "Resting", "Partying"]},
            {"text": "Do you prefer city or village?", "options": ["City", "Village", "Both", "Depends"]},
            {"text": "Do you like theme parks?", "options": ["Yes", "No", "Sometimes", "Rarely"]},

            {"text": "Favorite chocolate?", "options": ["Milk", "Dark", "White", "All"]},
            {"text": "Do you believe in soulmates?", "options": ["Yes", "No", "Maybe", "Not sure"]},
            {"text": "Do you like shopping?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Favorite hobby?", "options": ["Music", "Reading", "Gaming", "Sports"]},
            {"text": "Do you like camping?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Favorite indoor activity?", "options": ["Cooking", "Reading", "Watching TV", "Gaming"]},
            {"text": "Do you like painting?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Do you like fashion?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Do you watch web series?", "options": ["Yes", "No", "Sometimes", "Rarely"]},
            {"text": "Do you sing?", "options": ["Yes", "No", "Sometimes", "Only in shower"]}
        ]

        for q in questions_data:
            question = Question.objects.create(text=q["text"])
            for opt in q["options"]:
                Option.objects.create(question=question, text=opt)

        self.stdout.write(self.style.SUCCESS("✅ 50 questions added!"))
