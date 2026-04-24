import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

import base64
import json
from home.views import verify_face_live
from django.test import RequestFactory
from django.contrib.auth.models import User

req = RequestFactory().post(
    '/api/face/verify-live/',
    data=json.dumps({"image_front": "data:image/jpeg;base64," + base64.b64encode(b'dummy_image_data').decode()}),
    content_type='application/json'
)
req.user = User.objects.first()
resp = verify_face_live(req)
print("RESPONSE:", resp.content)
