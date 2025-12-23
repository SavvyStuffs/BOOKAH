import sys
import os

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

DB_FILE = resource_path('master.db') 
JSON_FILE = resource_path('all_skills.json')
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
