import os
import re
import random
from django.core.management.base import BaseCommand
from home.models import Question, Option, UserAnswer
from django.conf import settings

class Command(BaseCommand):
    help = "Seed 1000 new questions from questions.txt"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Deleting all existing questions, options, and user answers..."))
        
        # Deleting Question will cascade to Option and UserAnswer
        Question.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS("Database wiped. Reading questions.txt..."))
        
        file_path = os.path.join(settings.BASE_DIR, 'questions.txt')
        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"Could not find {file_path}"))
            return
            
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        questions_data = []
        
        for i in range(len(lines)):
            line = lines[i].strip()
            if not line:
                continue
                
            # Check if line contains "A)" and "B)"
            if "A)" in line and "B)" in line:
                idx_A = line.find("A)")
                if idx_A == 0:
                    prev = i - 1
                    while prev >= 0 and not lines[prev].strip():
                        prev -= 1
                    if prev >= 0:
                        q_text = lines[prev].strip()
                    else:
                        q_text = "Unknown Question"
                    opt_str = line
                else:
                    q_text = line[:idx_A].strip()
                    opt_str = line[idx_A:]
                    
                q_text = re.sub(r'^\d+[\.\)]\s*', '', q_text)
                
                opt_A = opt_str[opt_str.find("A)")+2 : opt_str.find("B)")].strip()
                opt_B_str = opt_str[opt_str.find("B)")+2 :]
                
                idx_C = opt_B_str.find("C)")
                if idx_C != -1:
                    opt_B = opt_B_str[:idx_C].strip()
                    opt_C_str = opt_B_str[idx_C+2:]
                    
                    idx_D = opt_C_str.find("D)")
                    if idx_D != -1:
                        opt_C = opt_C_str[:idx_D].strip()
                        opt_D = opt_C_str[idx_D+2:].strip()
                        options = [opt_A, opt_B, opt_C, opt_D]
                    else:
                        opt_C = opt_C_str.strip()
                        options = [opt_A, opt_B, opt_C]
                else:
                    opt_B = opt_B_str.strip()
                    options = [opt_A, opt_B]
                    
                questions_data.append({
                    "text": q_text,
                    "options": options
                })
        
        self.stdout.write(self.style.SUCCESS(f"Successfully extracted {len(questions_data)} questions."))
        
        # Shuffle the questions array
        self.stdout.write("Shuffling questions...")
        random.shuffle(questions_data)
        
        self.stdout.write("Inserting into database...")
        for q_idx, q in enumerate(questions_data):
            question = Question.objects.create(text=q["text"])
            for opt_text in q["options"]:
                Option.objects.create(question=question, text=opt_text)
                
            if (q_idx + 1) % 100 == 0:
                self.stdout.write(f"Inserted {q_idx + 1} / {len(questions_data)} questions...")
                
        self.stdout.write(self.style.SUCCESS(f"✅ All {len(questions_data)} questions have been seeded and shuffled!"))
