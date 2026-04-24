import requests
import json
import os
import base64
from django.conf import settings

CLARIFAI_PAT = getattr(settings, 'CLARIFAI_PAT', 'bb334e5763b94a07a014211842acd857')
USER_ID = 'clarifai'
APP_ID = 'main'

def clarifai_predict(model_id, image_data, model_version_id=""):
    """
    Generic Clarifai prediction helper.
    image_data can be a URL or base64 string.
    """
    if not CLARIFAI_PAT:
        return None

    headers = {
        "Authorization": f"Key {CLARIFAI_PAT}",
        "Content-Type": "application/json"
    }

    if image_data.startswith('http'):
        input_data = {"data": {"image": {"url": image_data}}}
    else:
        if 'base64,' in image_data:
            image_data = image_data.split('base64,')[1]
        input_data = {"data": {"image": {"base64": image_data}}}

    payload = {
        "user_app_id": {"user_id": USER_ID, "app_id": APP_ID},
        "inputs": [input_data]
    }

    url = f"https://api.clarifai.com/v2/models/{model_id}/versions/{model_version_id}/outputs" if model_version_id else f"https://api.clarifai.com/v2/models/{model_id}/outputs"
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[CLARIFAI] Prediction error: {e}")
        return None

def detect_face_clarifai(image_data):
    """
    Detect faces using Clarifai's Face Detection model.
    Returns (success, face_count, error_message)
    """
    # model_id = 'face-detection'
    # Actually, Clarifai's 'main' app has 'face-detection'
    res = clarifai_predict('face-detection', image_data)
    if not res:
        return False, 0, "Clarifai API unreachable"

    outputs = res.get('outputs', [])
    if not outputs:
        return False, 0, "No response from Clarifai"

    regions = outputs[0].get('data', {}).get('regions', [])
    face_count = len(regions)

    if face_count == 0:
        return False, 0, "No face detected by Clarifai. Please ensure your face is clearly visible."
    
    return True, face_count, None

def analyze_gender_clarifai(image_data):
    """
    Detect gender using Clarifai's Demographics model.
    Returns (gender, confidence)
    """
    # model_id = 'demographics-recognition' (handles age, gender, multicultural appearance)
    res = clarifai_predict('demographics-recognition', image_data)
    if not res:
        return None, 0.0

    outputs = res.get('outputs', [])
    if not outputs:
        return None, 0.0

    regions = outputs[0].get('data', {}).get('regions', [])
    if not regions:
        return None, 0.0

    # Get gender from the first face detected
    concepts = regions[0].get('data', {}).get('concepts', [])
    gender_concepts = [c for c in concepts if c.get('name') in ['masculine', 'feminine']]
    
    if not gender_concepts:
        return None, 0.0

    # Clarifai returns 'masculine'/'feminine'. We map to 'male'/'female'
    top_gender = max(gender_concepts, key=lambda x: x.get('value', 0))
    gender_name = 'male' if top_gender['name'] == 'masculine' else 'female'
    confidence = top_gender.get('value', 0) * 100.0

    return gender_name, confidence

def compare_faces_clarifai(image1_url, image2_url):
    """
    Compare two faces using Clarifai.
    Since Clarifai doesn't have a direct 'compare' endpoint like Amazon Rekognition,
    we would typically index one face and search for the other, or compare embeddings.
    
    For now, we'll stick to local DeepFace subprocess for comparison if biometric is needed,
    but use Clarifai for the heavy 'detection' and 'gender' checks to save memory.
    """
    # Placeholder for biometric comparison via Clarifai if we set up a Search app
    return None
