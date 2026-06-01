import os
import django
import pandas as pd
import random
import sys
from django.db import transaction

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

from home.models import Question, Option, UserAnswer

def seed_1500_questions():
    print("--- Starting Optimized Question Bank Migration ---")
    
    # 1. Clear existing data
    print("Clearing existing quiz data...")
    with transaction.atomic():
        UserAnswer.objects.all().delete()
        Option.objects.all().delete()
        Question.objects.all().delete()
    
    # 2. Read Excel files
    base_path = r"c:\Users\USER\Desktop\Projects\DATING APP\questionbank"
    files = [
        "dating_app_500_icebreaker_questions.xlsx",
        "dating_app_500_more_icebreaker_questions_pack2.xlsx",
        "dating_app_500_more_icebreaker_questions_pack3.xlsx"
    ]
    
    raw_data = []
    
    for f in files:
        full_path = os.path.join(base_path, f)
        if not os.path.exists(full_path):
            print(f"Warning: {f} not found. Skipping.")
            continue
            
        print(f"Reading {f}...")
        df = pd.read_excel(full_path)
        
        for _, row in df.iterrows():
            q_text = str(row['question']).strip()
            options = []
            if pd.notna(row.get('option_a')): options.append(str(row['option_a']).strip())
            if pd.notna(row.get('option_b')): options.append(str(row['option_b']).strip())
            if pd.notna(row.get('option_c')): options.append(str(row['option_c']).strip())
            if pd.notna(row.get('option_d')): options.append(str(row['option_d']).strip())
            
            if q_text and options:
                raw_data.append({
                    "text": q_text,
                    "options": options
                })
    
    print(f"Total questions gathered: {len(raw_data)}")
    
    # 3. Shuffle
    print("Shuffling questions...")
    random.shuffle(raw_data)
    
    # 4. Save to DB using bulk_create and transactions
    print("Saving to database...")
    
    with transaction.atomic():
        # Step 4a: Bulk Create Questions
        question_objs = [Question(text=d["text"]) for d in raw_data]
        created_questions = Question.objects.bulk_create(question_objs)
        
        # Step 4b: Bulk Create Options
        option_objs = []
        for i, q_obj in enumerate(created_questions):
            opts = raw_data[i]["options"]
            for idx, opt_text in enumerate(opts):
                option_objs.append(Option(
                    question=q_obj,
                    text=opt_text,
                    weight=float(idx + 1)
                ))
        
        # Batch insert options (6000+ items)
        Option.objects.bulk_create(option_objs, batch_size=500)

    print("--- Migration Complete! ---")
    print(f"✅ Successfully imported and shuffled {len(raw_data)} questions.")
    print("✅ All existing user answers have been reset.")

if __name__ == "__main__":
    seed_1500_questions()
