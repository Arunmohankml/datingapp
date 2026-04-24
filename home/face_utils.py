import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image
import os

# We will try to use DeepFace for verification, fallback to OpenCV if not available yet
try:
    from deepface import DeepFace
    HAS_DEEPFACE = True
except ImportError:
    HAS_DEEPFACE = False

def decode_image(base64_string):
    """Decode base64 image string to OpenCV format"""
    if 'base64,' in base64_string:
        base64_string = base64_string.split('base64,')[1]
    
    img_data = base64.b64decode(base64_string)
    img = Image.open(BytesIO(img_data)).convert('RGB')
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def detect_face(img):
    """
    Detect face using OpenCV's Haar Cascades with multiple fallback attempts.
    Returns (success, face_count, error_message)
    """
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Try progressively looser detection parameters
    attempts = [
        (1.1, 5),   # strict
        (1.1, 3),   # medium
        (1.2, 3),   # loose
        (1.3, 2),   # very loose (webcam with gesture)
    ]
    
    faces = []
    for scale, neighbors in attempts:
        faces = face_cascade.detectMultiScale(gray, scale, neighbors)
        if len(faces) > 0:
            break
    
    if len(faces) == 0:
        # safe_print can't be used here without import, so just skip or use a simpler log
        # print(f"[FACE-DETECT] No face found after {len(attempts)} attempts.") 
        return False, 0, "No face detected. Please ensure your face is clearly visible and well-lit."
    if len(faces) > 3:
        return False, len(faces), "Too many faces detected. Please ensure only you are in the photo."
    
    return True, len(faces), None

def check_liveness_best_effort(img):
    """
    Perform basic anti-spoofing checks.
    - Laplacian variance for blur detection (replays often look blurry or have moire)
    - Reflection/Texture analysis (placeholder)
    """
    # Blur detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Typical threshold for a real face in good lighting is > 100
    # Screen replays often have lower variance due to pixelation/blur
    if variance < 40:
        return False, "Low image quality or possible screen replay detected. Please use a real camera in good lighting."
    
    return True, None

# --- Configurable Thresholds ---
# ArcFace and Facenet512 cosine thresholds tuned for high leniency
THRESHOLDS = {
    "ArcFace": {"pass": 0.60, "review": 0.85},
    "Facenet512": {"pass": 0.55, "review": 0.80}
}

def run_deepface_subprocess(action, *args):
    """
    Runs DeepFace in an isolated subprocess to guarantee 100% stability.
    Prevents TensorFlow from hogging memory or crashing the Django server.
    """
    import subprocess
    import sys
    import json
    
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
        img = args[0]
        analysis = DeepFace.analyze(img_path=img, actions=['gender'], detector_backend='mtcnn', enforce_detection=False)
        gender_dict = analysis[0].get('gender', {{}})
        dominant = analysis[0].get('dominant_gender')
        conf = gender_dict.get(dominant, 0.0) if isinstance(gender_dict, dict) else 0.0
        print(json.dumps({{"success": True, "gender": dominant, "confidence": float(conf)}}))
        
    elif action == "verify":
        img1 = args[0]
        img2 = args[1]
        result = DeepFace.verify(
            img1_path=img1, 
            img2_path=img2, 
            model_name="ArcFace",
            detector_backend="mtcnn", 
            enforce_detection=True,
            align=True,
            distance_metric="cosine"
        )
        print(json.dumps({{"success": True, "score": float(result.get("distance", 1.0))}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
"""
    import os
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    
    try:
        # Run subprocess
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = process.communicate()
        
        # Parse last JSON line from stdout
        for line in stdout.strip().split('\n')[::-1]:
            clean_line = line.strip()
            if not clean_line: continue
            try:
                data = json.loads(clean_line)
                return data
            except:
                pass
        
        # If no JSON found, return the error
        error_msg = stderr.strip() or stdout.strip()
        return {"success": False, "error": "No JSON found in output", "raw": error_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}

def analyze_gender(img_path_or_array):
    """Detect gender and confidence using robust isolated process"""
    if not isinstance(img_path_or_array, str):
        # We need a file path for subprocess
        return None, 0.0
        
    try:
        res = run_deepface_subprocess("analyze", img_path_or_array)
        if res and res.get("success"):
            return res.get("gender"), res.get("confidence", 0.0)
        else:
            print(f"[FACE-UTILS] Gender analysis failed: {res.get('error')}")
            return None, 0.0
    except Exception as e:
        print(f"[FACE-UTILS] Subprocess failed: {e}")
        return None, 0.0

def compare_faces(probe_path, gallery_paths, target_gender=None):
    """
    Final optimized comparison:
    1. Check gender (must match target_gender if provided, only reject if confidence > 80%).
    2. Check biometric. PASS < 0.45. Any score >= 0.45 is flagged for REVIEW, never REJECT.
    """
    if not isinstance(probe_path, str) or not gallery_paths:
        return "PASS", "Basic Mode (AI Offline)", {}
    
    if isinstance(gallery_paths, str):
        gallery_paths = [gallery_paths]
    
    print(f"[FACE-UTILS] Starting robust final comparison (Target Gender: {target_gender})")
    
    try:
        # 1. Gender Check
        p_gender, p_conf = analyze_gender(probe_path)
        print(f"[FACE-UTILS] PFP Gender Detected: {p_gender} (Conf: {p_conf:.1f}%)")

        if target_gender and p_gender:
            if target_gender != p_gender and p_conf > 80.0:
                print(f"[FACE-UTILS] REJECTING: Gender mismatch ({p_gender} vs {target_gender})")
                return "REJECT", "Profile photo could not be verified. Please upload your own clear photo.", {
                    "p_gender": p_gender, "t_gender": target_gender, "score": None
                }

        # 2. Biometric Check
        best_score = 1.0
        try:
            res = run_deepface_subprocess("verify", probe_path, gallery_paths[0])
            if res and res.get("success"):
                best_score = res.get("score", 1.0)
                print(f"[FACE-UTILS] Face distance: {best_score:.4f}")
            else:
                error_msg = res.get("error", "") if res else "Unknown error"
                print(f"[FACE-UTILS] Biometric subprocess failed: {error_msg}")
                # HARD REJECT if no face or any error
                return "REJECT", "No face detected in the photo, or verification failed. Please upload a clear photo of yourself.", {
                    "p_gender": p_gender, "score": None
                }
        except Exception as e:
            print(f"[FACE-UTILS] Exception in biometric check: {e}")
            return "REJECT", "Verification error. Please upload a clear photo of your face.", {"p_gender": p_gender, "score": None}

        # Logic
        if best_score < 0.45:
            return "PASS", "Identity verified!", {"score": best_score, "p_gender": p_gender}
        
        return "REVIEW", "Photo flagged for review", {"score": best_score, "p_gender": p_gender}

    except Exception as e:
        print(f"[FACE-UTILS] Critical Error: {e}")
        return "PASS", "Fallback", {}

def save_base64_to_temp(base64_string, filename=None):
    """Helper to save base64 to a temporary file for processing"""
    import uuid
    if filename is None:
        filename = f"face_compare_{uuid.uuid4().hex[:8]}.jpg"
    
    if 'base64,' in base64_string:
        base64_string = base64_string.split('base64,')[1]
    
    img_data = base64.b64decode(base64_string)
    temp_dir = os.environ.get('TEMP', '/tmp') if os.name == 'nt' else '/tmp'
    path = os.path.join(temp_dir, filename)
    with open(path, 'wb') as f:
        f.write(img_data)
    return path
