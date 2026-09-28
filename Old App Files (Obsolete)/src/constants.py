import sys
import os
import shutil
import json

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Use the directory where this file is located (src/) and go up one level
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# --- Application Directories ---
if getattr(sys, 'frozen', False):
    # Running as a packaged EXE
    APP_ROOT = os.path.dirname(sys.executable)
else:
    # Running as a script
    # Use the directory where this file is located (src/) and go up one level
    APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Local data directory for models and user builds
if sys.platform == 'win32':
    USER_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local')), "Bookah")
else:
    # Linux / Flatpak / Mac
    USER_DIR = os.path.expanduser("~/.bookah_data")

if not os.path.exists(USER_DIR):
    try:
        os.makedirs(USER_DIR, exist_ok=True)
    except Exception as e:
        import tempfile
        USER_DIR = tempfile.gettempdir()

# Copy bundled models to USER_DIR if missing (Avoids re-training)
try:
    for filename in ['skill_vectors.model', 'description_embeddings.npz']:
        # Use resource_path to find the bundled file (in _MEIPASS or root)
        src = resource_path(filename)
        dst = os.path.join(USER_DIR, filename)
        
        # Only copy if source exists and dest doesn't
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            print(f"[Init] Copied {filename} to {USER_DIR}")
except Exception as e:
    print(f"[Init] Error copying bundled models: {e}")

# 1. System Database (Read-Only bundled version)
JSON_FILE = resource_path('all_skills.json')

# 2. User Database (Writeable, stored in install folder)
USER_BUILDS_FILE = os.path.join(USER_DIR, 'user_builds.json')

# Initialize User Builds file if it doesn't exist
if not os.path.exists(USER_BUILDS_FILE):
    with open(USER_BUILDS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

# 3. AI Models
BEHAVIOR_MODEL_PATH = os.path.join(USER_DIR, 'skill_vectors.model')
SEMANTIC_MODEL_PATH = os.path.join(USER_DIR, 'description_embeddings.npz')

# --- Static Data (Bundled in EXE) ---
DB_FILE = resource_path('master.db') 
AQ_DB_FILE = resource_path('skills_aq.db')
ICON_DIR = resource_path(os.path.join('icons', 'skill_icons'))
ICON_SIZE = 64
PIXMAP_CACHE = {}

PROF_MAP = {
    0: "No Profession", 1: "Warrior", 2: "Ranger", 3: "Monk", 4: "Necromancer",
    5: "Mesmer", 6: "Elementalist", 7: "Assassin", 8: "Ritualist",
    9: "Paragon", 10: "Dervish"
}

PROF_SHORT_MAP = {
    "No Profession": "X", "Warrior": "W", "Ranger": "R", "Monk": "Mo", 
    "Necromancer": "N", "Mesmer": "Me", "Elementalist": "E", 
    "Assassin": "A", "Ritualist": "Rt", "Paragon": "P", "Dervish": "D"
}

ATTR_MAP = {
    -9: "Norn", -8: "Ebon Vanguard", -7: "Delver", -6: "Asuran",
    -5: "Kurzick", -4: "Luxon", -3: "Lightbringer", -2: "Sunspear",
    -1: "No Attribute",
    0: "Fast Casting", 1: "Illusion Magic", 2: "Domination Magic", 3: "Inspiration Magic",
    4: "Blood Magic", 5: "Death Magic", 6: "Soul Reaping", 7: "Curses",
    8: "Air Magic", 9: "Earth Magic", 10: "Fire Magic", 11: "Water Magic",
    12: "Energy Storage", 13: "Healing Prayers", 14: "Smiting Prayers",
    15: "Protection Prayers", 16: "Divine Favor", 17: "Strength", 18: "Axe Mastery",
    19: "Hammer Mastery", 20: "Swordsmanship", 21: "Tactics", 22: "Beast Mastery",
    23: "Expertise", 24: "Wilderness Survival", 25: "Marksmanship", 29: "Dagger Mastery",
    30: "Deadly Arts", 31: "Shadow Arts", 32: "Communing", 33: "Restoration Magic",
    34: "Channeling Magic", 35: "Critical Strikes", 36: "Spawning Power",
    37: "Spear Mastery", 38: "Command", 39: "Motivation", 40: "Leadership",
    41: "Scythe Mastery", 42: "Wind Prayers", 43: "Earth Prayers", 44: "Mysticism"
}

PROF_PRIMARY_ATTR = {
    1: 17, 2: 23, 3: 16, 5: 0, 6: 12, 
    4: 6, 7: 35, 8: 36, 10: 44, 9: 40
}

PROF_ATTRS = {
    1: [17, 18, 19, 20, 21],          # Warrior: Strength, Axe, Hammer, Sword, Tactics
    2: [22, 23, 24, 25],              # Ranger: Beast, Expertise, Wild, Marks
    3: [13, 14, 15, 16],              # Monk: Heal, Smiting, Prot, Divine
    4: [4, 5, 6, 7],                  # Necro: Blood, Death, Soul, Curses
    5: [0, 1, 2, 3],                  # Mesmer: Fast, Illusion, Dom, Insp
    6: [8, 9, 10, 11, 12],            # Ele: Air, Earth, Fire, Water, Energy
    7: [29, 30, 31, 35],              # Assassin: Dagger, Deadly, Shadow, Critical
    8: [32, 33, 34, 36],              # Ritualist: Communing, Resto, Chan, Spawning
    9: [37, 38, 39, 40],              # Paragon: Spear, Command, Motiv, Leadership
    10: [41, 42, 43, 44]              # Dervish: Scythe, Wind, Earth, Mysticism
}
