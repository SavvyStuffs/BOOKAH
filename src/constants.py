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
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Application Directories ---
if getattr(sys, 'frozen', False):
    APP_ROOT = os.path.dirname(sys.executable)
    
    if sys.platform.startswith('linux'):
        USER_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "Bookah_Linux")
    else:
        USER_DIR = os.path.join(APP_ROOT, "data")
else:
    APP_ROOT = os.path.abspath(".")
    USER_DIR = os.path.join(APP_ROOT, "data")

if not os.path.exists(USER_DIR):
    os.makedirs(USER_DIR)

# 1. System Database (Read-Only bundled version)
JSON_FILE = resource_path('all_skills.json')

# 2. User Database (Writeable, stored in install folder)
USER_BUILDS_FILE = os.path.join(USER_DIR, 'user_builds.json')

# Initialize User Builds file if it doesn't exist
if not os.path.exists(USER_BUILDS_FILE):
    with open(USER_BUILDS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

# 3. AI Models
BEHAVIOR_MODEL_PATH = resource_path('skill_vectors.model')
SEMANTIC_MODEL_PATH = resource_path('description_embeddings.pt')

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
    -9: "Norn Rank", -8: "Ebon Vanguard Rank", -7: "Dwarven Rank", -6: "Asuran Rank",
    -5: "Kurzick Rank", -4: "Luxon Rank", -3: "Lightbringer Rank", -2: "Sunspear Rank",
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
