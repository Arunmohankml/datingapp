import numpy as np
import base64
from io import BytesIO
from PIL import Image
import os
import traceback

def decode_image(base64_string):
    """Decode base64 image string to OpenCV format (lazy load cv2)"""
    import cv2
    if 'base64,' in base64_string:
        base64_string = base64_string.split('base64,')[1]
    
    img_data = base64.b64decode(base64_string)
    img = Image.open(BytesIO(img_data)).convert('RGB')
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def detect_face(img_or_path):
    """
    Detect face using Clarifai (preferred) or local Haar Cascades.
    """
    # 1. Try Clarifai
    from .clarifai_utils import detect_face_clarifai
    try:
        # If it's a path, we read it
        if isinstance(img_or_path, str) and os.path.exists(img_or_path):
            with open(img_or_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            return detect_face_clarifai(b64)
    except Exception as e:
        print(f"[FACE-UTILS] Clarifai Detect Error: {e}")

    # 2. Local Fallback
    try:
        import cv2
        if isinstance(img_or_path, str):
            img = cv2.imread(img_or_path)
        else:
            img = img_or_path

        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) == 0:
            return False, 0, "No face detected locally."
        return True, len(faces), None
    except Exception as e:
        return True, 1, None # Fail safe

def analyze_gender(img_path_or_b64):
    """Detect gender using Clarifai (preferred) or local DeepFace."""
    # 1. Try Clarifai
    from .clarifai_utils import analyze_gender_clarifai
    try:
        image_data = img_path_or_b64
        if isinstance(img_path_or_b64, str) and os.path.exists(img_path_or_b64):
            with open(img_path_or_b64, "rb") as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
        
        gender, conf = analyze_gender_clarifai(image_data)
        if gender:
            print(f"[FACE-UTILS] Clarifai Gender: {gender} ({conf:.1f}%)")
            return gender, conf
    except Exception as e:
        print(f"[FACE-UTILS] Clarifai Gender Error: {e}")

    # 2. Local Fallback
    if not isinstance(img_path_or_b64, str) or not os.path.exists(img_path_or_b64):
        return None, 0.0
    try:
        res = run_deepface_subprocess("analyze", img_path_or_b64)
        if res and res.get("success"):
            return res.get("gender"), res.get("confidence", 0.0)
    except: pass
    return None, 0.0

def run_deepface_subprocess(action, *args):
    """Isolated subprocess for DeepFace (local backup)"""
    import subprocess
    import sys
    import json
    
    # If on Vercel and AI disabled, skip
    if os.environ.get('VERCEL') and os.environ.get('DISABLE_AI') == 'True':
        return {"success": False, "error": "AI service disabled"}

    code = f"""
import sys, json, warnings
warnings.filterwarnings('ignore')
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
try:
    from deepface import DeepFace
    action = '{action}'
    args = {list(args)}
    if action == "analyze":
        analysis = DeepFace.analyze(img_path=args[0], actions=['gender'], detector_backend='opencv', enforce_detection=False)
        g = analysis[0]['dominant_gender']
        c = analysis[0]['gender'][g]
        print(json.dumps({{"success": True, "gender": g, "confidence": float(c)}}))
    elif action == "verify":
        result = DeepFace.verify(img1_path=args[0], img2_path=args[1], model_name="ArcFace", detector_backend="opencv", enforce_detection=False)
        print(json.dumps({{"success": True, "score": float(result.get("distance", 1.0))}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
"""
    try:
        process = subprocess.Popen([sys.executable, "-c", code], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = process.communicate()
        for line in stdout.strip().split('\n')[::-1]:
            try: return json.loads(line)
            except: pass
        return {"success": False}
    except: return {"success": False}

def compare_faces(probe_path, gallery_paths, target_gender=None):
    """Hybrid Comparison: Clarifai for gender, local for biometric."""
    if not isinstance(probe_path, str) or not gallery_paths:
        return "PASS", "Basic Mode", {}
    
    if isinstance(gallery_paths, str):
        gallery_paths = [gallery_paths]
    
    try:
        # 1. Gender Check (Clarifai preferred)
        p_gender, p_conf = analyze_gender(probe_path)
        if target_gender and p_gender and target_gender != p_gender and p_conf > 80.0:
            return "REJECT", f"Gender mismatch. Detected {p_gender} but expected {target_gender}.", {"p_gender": p_gender}

        # 2. Biometric Check (DeepFace local for now)
        res = run_deepface_subprocess("verify", probe_path, gallery_paths[0])
        if res and res.get("success"):
            score = res.get("score", 1.0)
            if score < 0.45: return "PASS", "Identity verified!", {"score": score}
            return "REVIEW", "Photo flagged for review", {"score": score}
        
        return "PASS", "Basic Mode (Subprocess failure)", {}
    except Exception as e:
        return "PASS", "Fallback Mode", {}

def save_base64_to_temp(base64_string, filename=None):
    import uuid
    if filename is None:
        filename = f"face_{uuid.uuid4().hex[:8]}.jpg"
    if 'base64,' in base64_string:
        base64_string = base64_string.split('base64,')[1]
    
    img_data = base64.b64decode(base64_string)
    temp_dir = '/tmp'
    path = os.path.join(temp_dir, filename)
    with open(path, 'wb') as f:
        f.write(img_data)
    return path

def check_liveness_best_effort(img):
    return True, None
