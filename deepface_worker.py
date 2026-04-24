import sys
import json
import warnings
warnings.filterwarnings('ignore')
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

try:
    from deepface import DeepFace
    
    action = sys.argv[1]
    
    if action == "analyze":
        img = sys.argv[2]
        analysis = DeepFace.analyze(img_path=img, actions=['gender'], detector_backend='mtcnn', enforce_detection=False)
        gender_dict = analysis[0].get('gender', {})
        dominant = analysis[0].get('dominant_gender')
        conf = gender_dict.get(dominant, 0.0) if isinstance(gender_dict, dict) else 0.0
        print(json.dumps({"success": True, "gender": dominant, "confidence": conf}))
        
    elif action == "verify":
        img1 = sys.argv[2]
        img2 = sys.argv[3]
        result = DeepFace.verify(
            img1_path=img1, 
            img2_path=img2, 
            model_name="ArcFace",
            detector_backend="retinaface", 
            enforce_detection=True,
            align=True,
            distance_metric="cosine"
        )
        print(json.dumps({"success": True, "score": result.get("distance", 1.0)}))
        
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
