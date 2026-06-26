from django import template
import re

register = template.Library()

@register.filter
def cloudinary_optimize(url, params="c_fill,w_560,q_auto:eco,f_webp"):
    if not url or 'cloudinary' not in url:
        return url
    parts = url.split('/image/upload/', 1)
    if len(parts) != 2:
        return url
    return f"{parts[0]}/image/upload/{params}/{parts[1]}"
