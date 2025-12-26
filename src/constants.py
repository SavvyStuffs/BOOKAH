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

# --- Persistent User Data ---
USER_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Bookah")
if not os.path.exists(USER_DIR):
    os.makedirs(USER_DIR)

# 1. Writable JSON Database
JSON_FILE = os.path.join(USER_DIR, 'all_skills.json')
if not os.path.exists(JSON_FILE):
    # Copy bundled version to Documents on first run
    default_json = resource_path('all_skills.json')
    if os.path.exists(default_json):
        shutil.copy(default_json, JSON_FILE)

# 2. AI Models (Stored in Documents so they can be updated/retrained)
BEHAVIOR_MODEL_PATH = os.path.join(USER_DIR, 'skill_vectors.model')
SEMANTIC_MODEL_PATH = os.path.join(USER_DIR, 'description_embeddings.pt')

# Pre-seed models if bundled
if not os.path.exists(BEHAVIOR_MODEL_PATH):
    bundled_bm = resource_path('skill_vectors.model')
    if os.path.exists(bundled_bm): shutil.copy(bundled_bm, BEHAVIOR_MODEL_PATH)

if not os.path.exists(SEMANTIC_MODEL_PATH):
    bundled_sm = resource_path('description_embeddings.pt')
    if os.path.exists(bundled_sm): shutil.copy(bundled_sm, SEMANTIC_MODEL_PATH)

# --- Static Data (Bundled in EXE) ---
DB_FILE = resource_path('master.db') 
AQ_DB_FILE = resource_path('skills_aq.db')
ICON_DIR = resource_path('icons/skill_icons')
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
    1: 17, 2: 23, 3: 16, 5: 3, 6: 12, 
    4: 6, 7: 30, 8: 36, 10: 44, 9: 40
}
