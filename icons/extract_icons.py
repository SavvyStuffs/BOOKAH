import os
from PIL import Image

# ==============================
# CONFIGURATION
# ==============================
DIB_FILE = "iconlib.dib"
TXT_FILE = "iconlib.txt"
OUTPUT_DIR = "skill_icons"

def extract_icons():
    print(f"Reading {TXT_FILE}...")
    try:
        with open(TXT_FILE, 'r') as f:
            skill_ids = [int(line.strip()) for line in f if line.strip().isdigit()]
    except FileNotFoundError:
        print("Error: Could not find iconlib.txt")
        return

    print(f"Loading {DIB_FILE}...")
    try:
        sheet = Image.open(DIB_FILE)
    except IOError:
        print("Error: Could not open iconlib.dib")
        return

    sheet_width, sheet_height = sheet.size
    
    # FIX: The height determines the icon size (24px), not the width
    icon_size = sheet_height 
    
    num_skills = len(skill_ids)
    actual_icons = sheet_width // icon_size
    
    print(f"Sheet Dimensions: {sheet_width}x{sheet_height} px")
    print(f"Detected Icon Size: {icon_size}x{icon_size} px")
    print(f"Skills in text file: {num_skills}")
    print(f"Icons in image file: {actual_icons}")

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("Extracting icons (Horizontal Mode)...")
    count = 0
    
    for index, skill_id in enumerate(skill_ids):
        if index >= actual_icons:
            break
            
        # FIX: Calculate coordinates for Horizontal Strip
        left = index * icon_size
        upper = 0
        right = left + icon_size
        lower = icon_size
        
        try:
            icon = sheet.crop((left, upper, right, lower))
            save_path = os.path.join(OUTPUT_DIR, f"{skill_id}.png")
            icon.save(save_path)
            count += 1
        except Exception as e:
            print(f"Error saving {skill_id}: {e}")

        if count % 100 == 0:
            print(f"Saved {count} icons...", end='\r')

    print(f"\nDone! Extracted {count} icons to '{OUTPUT_DIR}/'")

if __name__ == "__main__":
    extract_icons()