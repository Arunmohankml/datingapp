"""Verification script: check all static asset references resolve."""
import os, re, sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'
STATICFILES_DIR = BASE_DIR / 'staticfiles'
TEMPLATE_DIR = BASE_DIR / 'template'
MANIFEST_PATH = STATICFILES_DIR / 'staticfiles.json'

errors = []

# 1. Check {% static %} references resolve to files in static/
for root, dirs, files in os.walk(TEMPLATE_DIR):
    for f in files:
        if not f.endswith('.html'):
            continue
        path = os.path.join(root, f)
        with open(path, encoding='utf-8', errors='ignore') as fh:
            for i, line in enumerate(fh, 1):
                m = re.search(r"{% static '([^']+)' %}", line)
                if m:
                    ref = m.group(1)
                    full = STATIC_DIR / ref
                    if not full.exists():
                        errors.append(f"MISSING: {path}:{i}  {{{{ static '{ref}' }}}}  -> {full} does not exist")
                    else:
                        print(f"OK: {path}:{i}  {{{{ static '{ref}' }}}}  -> {full}")

# 2. Check favicon.ico exists
if (BASE_DIR / 'static_root' / 'favicon.ico').exists():
    print("OK: static_root/favicon.ico exists  ->  served at /favicon.ico")
else:
    errors.append("MISSING: static_root/favicon.ico")

# 3. Check manifest.json icon refs
manifest_path = TEMPLATE_DIR / 'manifest.json'
if manifest_path.exists():
    with open(manifest_path) as f:
        content = f.read()
    for m in re.finditer(r'"src":\s*"([^"]+)"', content):
        src = m.group(1)
        if src.startswith('/'):
            local_path = BASE_DIR / 'static_root' / src.lstrip('/')
            if not local_path.exists():
                errors.append(f"MISSING: {manifest_path} references {src} but {local_path} does not exist")
            else:
                print(f"OK: manifest.json references {src}")

# 4. Check manifest.json in staticfiles deployment
if MANIFEST_PATH.exists():
    import json
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    paths = manifest.get('paths', {})
    print(f"OK: staticfiles.json manifest exists with {len(paths)} entries")
else:
    errors.append("MISSING: staticfiles/staticfiles.json - run collectstatic")

# 5. Check no leftover broken icon refs in any file
BROKEN_PATTERNS = ['favicon.png', 'banner.png', 'icon-192x192.png', 'icon-512x512.png']
SKIP_FILES = {'verify_static_assets.py'}
for root, dirs, files in os.walk(BASE_DIR):
    skip_dirs = {'venv', '.git', '__pycache__', 'staticfiles', 'scratch', 'backup_ui_redesign_20260524', 'reference'}
    if any(s in root for s in skip_dirs):
        continue
    for f in files:
        if f in SKIP_FILES:
            continue
        if f.endswith(('.html', '.py', '.js', '.json')):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8', errors='ignore') as fh:
                    for i, line in enumerate(fh, 1):
                        for pat in BROKEN_PATTERNS:
                            if pat in line and 'staticfiles' not in path and 'staticfiles.json' not in path:
                                errors.append(f"LEFTOVER BROKEN REF: {path}:{i}  {line.strip()}")
            except Exception:
                pass

print()
if errors:
    print(f"FAILED: {len(errors)} issue(s) found:")
    for e in errors:
        print(f"  X  {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED - no broken static references")
