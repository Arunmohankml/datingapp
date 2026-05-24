import json
import re

def parse_questions(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    questions = []
    
    for i in range(len(lines)):
        line = lines[i].strip()
        if not line:
            continue
            
        # Check if line contains "A)" and "B)"
        if "A)" in line and "B)" in line:
            # It has options!
            idx_A = line.find("A)")
            if idx_A == 0:
                # Options are on this line, question is on a previous line
                prev = i - 1
                while prev >= 0 and not lines[prev].strip():
                    prev -= 1
                if prev >= 0:
                    q_text = lines[prev].strip()
                else:
                    q_text = "Unknown Question"
                opt_str = line
            else:
                # Question is on the same line before A)
                q_text = line[:idx_A].strip()
                opt_str = line[idx_A:]
                
            # Clean question text (remove numbering if like "1. " or "101. ")
            q_text = re.sub(r'^\d+[\.\)]\s*', '', q_text)
            
            # Extract options
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
                
            questions.append({
                "text": q_text,
                "options": options
            })
            
    return questions

q = parse_questions(r"c:\Users\USER\Desktop\Projects\DATING APP\questions.txt")
print(f"Total parsed: {len(q)}")
print("First 2:", json.dumps(q[:2], indent=2))
print("Last 2:", json.dumps(q[-2:], indent=2))
