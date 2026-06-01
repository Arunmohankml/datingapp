with open('scratch/old_complete_profile_utf8.html', 'r', encoding='utf-8') as f:
    content = f.read()

out_lines = []

# Find Face Verification HTML
start_html_idx = content.find('id="face-verification-section"')
if start_html_idx != -1:
    div_start = content.rfind('<div', 0, start_html_idx)
    # Find the matching closing div or just grab a large chunk
    # Let's search for "profile_pic_file" which is the end of the face-verification-section + pfp group
    end_html_idx = content.find('id="gallery-group"')
    if end_html_idx == -1:
        end_html_idx = div_start + 8000
    out_lines.append("=== HTML SECTION ===")
    out_lines.append(content[div_start:end_html_idx])

# Find JS logic
js_marker = 'VERIFICATION & GALLERY LOGIC'
start_js_idx = content.find(js_marker)
if start_js_idx != -1:
    # Go back to '// ───── VERIFICATION & GALLERY LOGIC ─────'
    js_header = '// ───── VERIFICATION & GALLERY LOGIC ─────'
    header_idx = content.find(js_header)
    if header_idx != -1:
        start_js_idx = header_idx
    
    # We want to extract up to the end of verification logic
    # Let's find compareLocally, handleVerificationRetake, showRetakeConfirmationModal, handlePfpSelect, handleGallerySelect etc.
    # In the original file, it goes up to checkStep7Validity or some other part
    # Let's grab 30000 characters from start_js_idx
    out_lines.append("\n\n=== JS SECTION ===")
    out_lines.append(content[start_js_idx:start_js_idx+35000])

with open('scratch/verification_parts.txt', 'w', encoding='utf-8') as out_f:
    out_f.write("\n".join(out_lines))

print("Successfully written to scratch/verification_parts.txt")
