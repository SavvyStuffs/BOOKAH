import sys
import os
import json
import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from collections import Counter
from PyQt6.QtCore import QThread, pyqtSignal
import math

# GUI Imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QComboBox, QLabel, QScrollArea, 
    QFrame, QGridLayout, QLineEdit, QSplitter, 
    QTabWidget, QCheckBox, QPushButton, QSizePolicy,
    QFileDialog, QMessageBox, QLayout, QStyle, QDialog, 
    QListWidget, QInputDialog, QStyledItemDelegate, QListWidgetItem 

)
from PyQt6.QtCore import Qt, QMimeData, QSize, pyqtSignal, QPoint, QUrl, QRect, QTimer
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont, QAction, QIcon

# Attempt to import WebEngine for the Map Tab
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

class TeamManagerDialog(QDialog):
    def __init__(self, parent=None, engine=None):
        super().__init__(parent)
        self.setWindowTitle("Team Build Manager")
        self.resize(400, 300)
        self.engine = engine
        self.parent_window = parent # Reference to MainWindow to get current build
        
        layout = QVBoxLayout(self)
        
        # Header with Plus button
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Teams:</b>"))
        header.addStretch()

        self.btn_export = QPushButton("Export")
        self.btn_export.setFixedSize(60, 24)
        self.btn_export.setToolTip("Export Selected Team Builds")
        self.btn_export.clicked.connect(self.export_team)
        header.addWidget(self.btn_export)

        self.btn_add_folder = QPushButton("+")
        self.btn_add_folder.setFixedSize(24, 24)
        self.btn_add_folder.setToolTip("Import Team from Folder")
        self.btn_add_folder.setStyleSheet("font-weight: bold; color: #00AAFF;")
        self.btn_add_folder.clicked.connect(self.add_from_folder)
        header.addWidget(self.btn_add_folder)
        layout.addLayout(header)
        
        # Search Bar
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Search teams...")
        self.edit_search.textChanged.connect(self.refresh_list)
        layout.addWidget(self.edit_search)
        
        self.list_widget = QListWidget()
        self.refresh_list()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("Add Current Build to Team")
        self.btn_add.clicked.connect(self.add_team)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_edit = QPushButton("Edit Team")
        self.btn_edit.clicked.connect(self.edit_team)
        btn_layout.addWidget(self.btn_edit)
        
        self.btn_load = QPushButton("Open Team")
        self.btn_load.clicked.connect(self.load_team)
        btn_layout.addWidget(self.btn_load)
        
        self.btn_del = QPushButton("Delete Team")
        self.btn_del.clicked.connect(self.remove_team)
        self.btn_del.setStyleSheet("background-color: #552222;")
        btn_layout.addWidget(self.btn_del)
        
        layout.addLayout(btn_layout)

    def refresh_list(self):
        self.list_widget.clear()
        search_text = self.edit_search.text().lower()
        teams = sorted(list(self.engine.teams))
        filtered_teams = [t for t in teams if search_text in t.lower()]
        self.list_widget.addItems(filtered_teams)
        
    def export_team(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Export", "Please select a team to export.")
            return
        team_name = item.text()
        # Set the combo box in parent so export_team_builds knows what to export
        idx = self.parent_window.combo_team.findText(team_name)
        if idx != -1:
            self.parent_window.combo_team.setCurrentIndex(idx)
            self.parent_window.export_team_builds()

    def add_from_folder(self):
        # Open directory dialog
        folder_path = QFileDialog.getExistingDirectory(self, "Select Team Build Folder")
        if folder_path:
            # Use logic from main window
            self.parent_window.process_folder_drop(folder_path)
            self.refresh_list()
        
    def edit_team(self):
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        dlg = TeamEditorDialog(team_name, self.engine, self)
        dlg.exec()

    def add_team(self):
        # Save current build as a new Team Build entry
        name, ok = QInputDialog.getText(self, "New Team Build", "Enter Team Name:")
        if ok and name:
            code = self.parent_window.edit_code.text()
            if not code:
                QMessageBox.warning(self, "Error", "No build code to save!")
                return
                
            decoder = GuildWarsTemplateDecoder(code)
            decoded = decoder.decode()
            if not decoded: return

            entry = {
                "build_code": code,
                "primary_profession": str(decoded['profession']['primary']),
                "secondary_profession": str(decoded['profession']['secondary']),
                "skill_ids": decoded['skills'],
                "category": "User Team",
                "team": name
            }
            
            # Append to engine data and save
            self.engine.builds.append(Build(
                code=entry['build_code'],
                primary_prof=entry['primary_profession'],
                secondary_prof=entry['secondary_profession'],
                skill_ids=entry['skill_ids'],
                category=entry['category'],
                team=entry['team']
            ))
            self.engine.teams.add(name)
            
            # Persist to JSON
            self.save_to_json(entry)
            self.refresh_list()
            
    def load_team(self):
        # Load selected team build into main window
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        
        # Load first build found
        for b in self.engine.builds:
            if b.team == team_name:
                self.parent_window.load_code(code_str=b.code)
                self.close()
                return

    def remove_team(self):
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        
        confirm = QMessageBox.question(self, "Confirm", f"Delete all builds for team '{team_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            # Remove from memory
            self.engine.builds = [b for b in self.engine.builds if b.team != team_name]
            self.engine.teams.discard(team_name)
            
            # Remove from JSON
            self.remove_from_json(team_name)
            self.refresh_list()

    def save_to_json(self, entry):
        try:
            data = []
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data.append(entry)
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving: {e}")

    def remove_from_json(self, team_name):
        try:
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                new_data = [d for d in data if d.get('team') != team_name]
                
                with open(JSON_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, indent=4)
        except Exception as e:
            print(f"Error removing: {e}")

class TeamEditorDialog(QDialog):
    def __init__(self, team_name, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Team: {team_name}")
        self.resize(500, 400)
        self.team_name = team_name
        self.engine = engine
        
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.refresh_list()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        self.btn_del = QPushButton("Remove Selected Build")
        self.btn_del.clicked.connect(self.remove_build)
        btn_layout.addWidget(self.btn_del)
        
        layout.addLayout(btn_layout)

    def refresh_list(self):
        self.list_widget.clear()
        self.team_builds = [b for b in self.engine.builds if b.team == self.team_name]
        
        for i, b in enumerate(self.team_builds):
            # Try to describe the build
            p1 = PROF_MAP.get(int(b.primary_prof), "X")
            p2 = PROF_MAP.get(int(b.secondary_prof), "X")
            item_text = f"#{i+1}: {p1}/{p2} - {b.code}"
            self.list_widget.addItem(item_text)

        def remove_build(self):

            row = self.list_widget.currentRow()

            if row < 0: return

            

            build_to_remove = self.team_builds[row]

            

            # Remove from engine

            if build_to_remove in self.engine.builds:

                self.engine.builds.remove(build_to_remove)

                

            # Remove from JSON

            self.remove_specific_build_from_json(build_to_remove.code)

            

            self.refresh_list()

            

        def remove_specific_build_from_json(self, code):

            try:

                if os.path.exists(JSON_FILE):

                    with open(JSON_FILE, 'r', encoding='utf-8') as f:

                        data = json.load(f)

                    

                    # Remove FIRST match of code and team (in case of dupes)

                    new_data = []

                    removed = False

                    for d in data:

                        if not removed and d.get('build_code') == code and d.get('team') == self.team_name:

                            removed = True # Skip this one

                        else:

                            new_data.append(d)

                    

                    with open(JSON_FILE, 'w', encoding='utf-8') as f:

                        json.dump(new_data, f, indent=4)

            except Exception as e:

                print(f"Error removing build: {e}")

    

class LocationManagerDialog(QDialog):
    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self.setWindowTitle("Locations")
        self.resize(450, 600)
        self.db_path = db_path
        
        layout = QVBoxLayout(self)
        
        # Search Bar
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Search locations...")
        self.edit_search.textChanged.connect(self.refresh_list)
        layout.addWidget(self.edit_search)
        
        self.tabs = QTabWidget()
        
        self.list_zones = QListWidget()
        self.list_missions = QListWidget()
        
        self.tabs.addTab(self.list_zones, "Explorable Zones")
        self.tabs.addTab(self.list_missions, "Missions")
        
        layout.addWidget(self.tabs)
        
        btn_layout = QHBoxLayout()
        self.btn_select = QPushButton("Select Location")
        self.btn_select.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_select)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.refresh_list()

    def refresh_list(self):
        self.list_zones.clear()
        self.list_missions.clear()
        search_text = self.edit_search.text().lower()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Load Explorable Zones
            cursor.execute("SELECT name FROM locations WHERE type = 'Location' ORDER BY name ASC")
            zones = [row[0] for row in cursor.fetchall() if search_text in row[0].lower()]
            self.list_zones.addItems(zones)
            
            # Load Missions
            cursor.execute("SELECT name FROM locations WHERE type = 'Mission' ORDER BY name ASC")
            missions = [row[0] for row in cursor.fetchall() if search_text in row[0].lower()]
            self.list_missions.addItems(missions)
            
            conn.close()
        except Exception as e:
            print(f"Error loading locations: {e}")

    def get_selected_location(self):
        # Check active tab
        if self.tabs.currentIndex() == 0:
            item = self.list_zones.currentItem()
        else:
            item = self.list_missions.currentItem()
        return item.text() if item else None

    

    # =============================================================================

    # CONFIGURATION

    # =============================================================================
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

# =============================================================================
# DATA MODELS & BACKEND
# =============================================================================

@dataclass
class Skill:
    id: int
    name: str
    icon_filename: str
    profession: int = 0
    description: str = ""
    attribute: int = -1
    energy: int = 0
    activation: float = 0.0
    recharge: float = 0.0
    adrenaline: int = 0
    is_elite: bool = False
    is_pve_only: bool = False
    health_cost: int = 0
    aftercast: float = 0.75  # Default standard aftercast
    combo_req: int = 0       # 0=None, 1=Lead, 2=Offhand, 3=Dual (Assassin)
    is_touch: bool = False   # Requires melee range
    campaign: int = 0        # 0=Core, 1=Prophecies, etc.
    in_pre: bool = False     # Available in Pre-Searing
    stats: List = field(default_factory=list)
    original_description: str = ""

    def __post_init__(self):
        if not self.original_description:
            self.original_description = self.description

    def get_profession_str(self):
        return PROF_MAP.get(self.profession, f"Unknown ({self.profession})")

    def get_attribute_str(self):
        if self.attribute == -1: return "None"
        return ATTR_MAP.get(self.attribute, f"Unknown ({self.attribute})")

    def get_description_for_rank(self, rank: int) -> str:
        """
        Dynamically substitutes variables in the description based on the provided attribute rank.
        Uses self.stats to find patterns and values.
        """
        if not self.stats:
            return self.description
            
        # Ensure rank is within bounds (0-21)
        rank = max(0, min(rank, 21))
        
        # Start with the ORIGINAL description, not the potentially already modified one
        current_desc = self.original_description
        
        for stat in self.stats:
            # Helper to safely convert to int
            def safe_int(val):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return 0

            val_0 = safe_int(stat[2])
            val_15 = safe_int(stat[17])
            val_target = safe_int(stat[2 + rank]) # rank 0 is at index 2
            
            # Identify the pattern in the text
            pattern = ""
            if val_0 == val_15:
                pattern = str(val_0)
            else:
                pattern = f"{val_0}..{val_15}"
            
            # Prepare replacement string with blue color
            # Using basic HTML color attribute which works in QT labels
            replacement = f'<span style="color: #55AAFF;">{val_target}</span>'
            
            # Find and replace ONLY the first occurrence
            if pattern in current_desc:
                current_desc = current_desc.replace(pattern, replacement, 1)
            else:
                # Fallback: Try checking up to rank 21 if rank 15 didn't match
                val_21 = safe_int(stat[23])
                alt_pattern = f"{val_0}..{val_21}"
                if alt_pattern in current_desc:
                    current_desc = current_desc.replace(alt_pattern, replacement, 1)
                    
        return current_desc
@dataclass
class Build:
    code: str
    primary_prof: str
    secondary_prof: str
    skill_ids: List[int]
    category: str
    team: str
    attributes: List[List[int]] = None 

# =============================================================================
# HAMILTONIAN PHYSICS ENGINE (v2.0)
# =============================================================================

class SystemContext:
    """
    Represents the instantaneous state of the build (The 'Scratchpad').
    Tracks entropy, resource flow, and mechanic states (occupancy).
    """
    def __init__(self, primary_prof_id=0):
        # --- Profession Physics Config ---
        # Casters: Monk(3), Necro(4), Mesmer(5), Ele(6), Rit(8)
        self.is_caster = primary_prof_id in [3, 4, 5, 6, 8]
        
        # Energy Capacity
        self.max_energy_capacity = 60 if self.is_caster else 30
        self.base_regen = 1.33 if self.is_caster else 0.66
        
        # --- Real-time State ---
        self.net_energy_cost = 0
        self.energy_drain_per_sec = 0.0
        
        self.stance_count = 0
        self.weapon_spell_count = 0
        self.hex_count = 0
        self.active_enchantments = 0
        self.knockdowns = False
        self.hexes_applied = False
        
        self.combo_stages = set()
        self.conditions_applied = set()
        
        # --- Weapon Tracking ---
        self.primary_weapon = None
        self.WEAPON_MAP = {
            18: "Axe", 19: "Hammer", 20: "Sword",      # Warrior
            25: "Bow",                                 # Ranger
            29: "Dagger",                              # Assassin
            37: "Spear",                               # Paragon
            41: "Scythe"                               # Dervish
        }

    def ingest_skill(self, skill):
        """
        Reads a skill row from the DB and updates the System Context.
        DB Index: 0:id, 1:name, 2:desc, 3:nrg, 4:act, 5:rech, 6:adr, 7:hp, 8:aft, 9:combo, 10:elite, 11:attr
        """
        name = skill[1].lower()
        desc = skill[2].lower() if skill[2] else ""
        nrg = skill[3] or 0
        rech = skill[5] or 0.0
        attr = skill[11] or -1
        
        # 1. Physics: Energy Entropy
        if rech > 0:
            self.energy_drain_per_sec += (nrg / rech)
            
        # 2. Law of Occupancy & Mechanics
        if "stance" in desc and "form" not in name: self.stance_count += 1
        if "weapon spell" in desc: self.weapon_spell_count += 1
        if "hex" in desc and "spell" in desc: 
            self.hex_count += 1
            self.hexes_applied = True
        if "enchantment" in desc: self.active_enchantments += 1
        if "knock down" in desc or "knocks down" in desc: self.knockdowns = True
        
        # 3. Causal Detection (With Negative Lookbehind)
        conditions = ['burning', 'bleeding', 'dazed', 'deep wound', 'weakness', 'poison']
        for c in conditions:
            if c in desc and ("target" in desc or "foe" in desc):
                idx = desc.find(c)
                if idx != -1:
                    start = max(0, idx - 20)
                    pre_text = desc[start:idx]
                    negatives = ["remove", "end", "lose", "cure", "reduced", "less"]
                    if not any(neg in pre_text for neg in negatives):
                        self.conditions_applied.add(c)
                
        # 4. Combo Stages
        if skill[9]: self.combo_stages.add(skill[9])
        
        # 5. Weapon Locking
        if attr in self.WEAPON_MAP:
            if self.primary_weapon is None:
                self.primary_weapon = self.WEAPON_MAP[attr]

    def calculate_efficiency(self, candidate_skill):
        """ Calculates variable efficiency modifiers (Smart Logic). """
        name = candidate_skill[1].lower()
        
        # Logic: Mystic Regeneration
        if "mystic regeneration" in name:
            if self.active_enchantments == 0: return 0.1, "Useless (No Enchants)"
            if self.active_enchantments < 3: return 0.5, "Weak Heal"
            return 1.5, "Strong Synergy"
            
        return 1.0, "OK"

class HamiltonianEngine:
    """
    Connects to master.db to perform causal analysis and system dynamics checks.
    Treats the build as a thermodynamic system of Energy, Health, and Time.
    """
    def __init__(self, db_path):
        self.db_path = db_path
        self.mode = "pve"

    def set_mode(self, mode_str):
        self.mode = mode_str.lower()

    def _get_table(self):
        return "skills_pvp" if self.mode == 'pvp' else "skills"

    # --- MECHANIC CHECKS ---
    def check_weapon_compatibility(self, candidate_attr, context):
        if context.primary_weapon is None: return True, "OK"
        if candidate_attr not in context.WEAPON_MAP: return True, "OK"
        candidate_weapon = context.WEAPON_MAP[candidate_attr]
        if candidate_weapon != context.primary_weapon:
            return False, f"Weapon Conflict ({candidate_weapon} vs {context.primary_weapon})"
        return True, "OK"

    def check_combo_viability(self, candidate_req, active_stages):
        if candidate_req == 0: return True
        if candidate_req == 1: return True
        if candidate_req == 2: return 1 in active_stages
        if candidate_req == 3: return (1 in active_stages) or (2 in active_stages)
        return True

    def check_occupancy_viability(self, candidate_row, context):
        desc = candidate_row[2].lower()
        if "stance" in desc and context.stance_count >= 1: return False, "Stance Clog"
        if "weapon spell" in desc and context.weapon_spell_count >= 1: return False, "Weapon Spell Clog"
        return True, "OK"

    def check_causal_viability(self, candidate_row, context):
        desc = candidate_row[2].lower()
        if "remove a hex" in desc and not context.hexes_applied: return False, "No Hexes to Shatter"
        if "knocked down foe" in desc and not context.knockdowns: return False, "No Knockdowns present"
        return True, "OK"

    def check_energy_entropy(self, candidate_row, context):
        nrg = candidate_row[3] or 0
        rech = candidate_row[5] or 0.0
        if nrg > 30: return False, "Skill Cost > 30 (Impossible)"
        if rech > 0:
            candidate_eps = nrg / rech
            total_drain = context.energy_drain_per_sec + candidate_eps
            limit = 4.0 if context.is_caster else 2.5
            if total_drain > limit: return True, f"⚠️ High Drain ({total_drain:.1f} EPS)"
        return True, "OK"

    def check_hamiltonian_stability(self, skill_a_data, skill_b_data, context):
        e_a, rech_a, hp_a = skill_a_data[3] or 0, skill_a_data[5] or 0.0, skill_a_data[7] or 0
        e_b, act_b, hp_b = skill_b_data[3] or 0, skill_b_data[4] or 0.0, skill_b_data[7] or 0
        rech_b = skill_b_data[5] or 0.0
        aft_b = skill_b_data[8] or 0.75

        burst_cost = e_a + e_b
        cap = context.max_energy_capacity
        if burst_cost > cap: return False, f"Burst > Capacity ({burst_cost}/{cap})"
        if burst_cost > (cap * 0.8): return True, f"⚠️ Heavy Burst ({burst_cost}e)"

        total_hp = hp_a + hp_b
        if total_hp > 50 and (rech_a < 8 or rech_b < 8): return False, f"Suicide Loop (-{total_hp} HP)"

        cycle_b = act_b + aft_b
        # Relaxed Timing Clog to a Warning to prevent empty suggestion lists
        if rech_a > 0 and (rech_a + 0.25) < cycle_b: 
            return True, f"⚠️ Timing Clog (Wait {cycle_b - rech_a:.1f}s)"

        return True, "Stable"

    # --- MAIN LOOP ---
    def find_synergies(self, active_skill_ids: List[int], primary_prof_id: int = 0, debug_mode: bool = False, stop_check=None) -> List[tuple[int, str]]:
        if not active_skill_ids: return []

        try:
            conn = sqlite3.connect(self.db_path)
            table = self._get_table()
            
            cols = "skill_id, name, description, energy_cost, activation, recharge, adrenaline, health_cost, aftercast, combo_req, is_elite, attribute, target_type"
            placeholders = ','.join(['?'] * len(active_skill_ids))
            
            q_active = f"SELECT {cols} FROM {table} WHERE skill_id IN ({placeholders})"
            cursor = conn.execute(q_active, active_skill_ids)
            active_skills_data = cursor.fetchall()
            
            # Fetch Tags for active skills
            q_tags = f"SELECT skill_id, tag FROM skill_tags WHERE skill_id IN ({placeholders})"
            cursor = conn.execute(q_tags, active_skill_ids)
            skill_tags_map = {}
            for sid, tag in cursor.fetchall():
                if sid not in skill_tags_map: skill_tags_map[sid] = set()
                skill_tags_map[sid].add(tag)
            
            context = SystemContext(primary_prof_id)
            for s in active_skills_data:
                context.ingest_skill(s)

            synergies = []
            # REMOVED 'Knockdown', 'Hexed' (Covered by Laws of Gravity & Hexes)
            conditions = ['Burning', 'Bleeding', 'Dazed', 'Deep Wound', 'Weakness', 'Poison', 'Enchanted']
            existing_ids = set(active_skill_ids)

            for root in active_skills_data:
                if stop_check and stop_check(): return []
                
                root_id = root[0]
                root_name = root[1].lower()
                root_desc = root[2].lower() if root[2] else ""
                root_hp_cost = root[7] or 0
                root_target_type = root[12] if len(root) > 12 else 0
                root_tags = skill_tags_map.get(root_id, set())
                
                # --- Mechanic Identification ---
                is_hex_prov = 'Type_Hex' in root_tags
                # Hex Consumer: Must not target ally (Type 3) unless it's a specific mechanic that uses ally hexes offensively?
                # "Shatter Hex" (Target Ally, Type 3) -> Defensive/Niche. Not a synergy for "Empathy".
                is_hex_cons = ("hexed foe" in root_desc or "remove a hex" in root_desc or "shatter" in root_desc) and root_target_type != 3
                
                is_ench_prov = 'Type_Enchantment' in root_tags
                is_ench_cons = "while you are enchanted" in root_desc or "for each enchantment" in root_desc or "extend" in root_desc and "enchantment" in root_desc
                
                is_spirit_prov = 'Type_Spirit' in root_tags
                is_spirit_cons = "near a spirit" in root_desc or "earshot of a spirit" in root_desc or "destroy" in root_desc and "spirit" in root_desc
                
                is_signet_prov = 'Type_Signet' in root_tags
                is_signet_cons = "equipped signet" in root_desc or "signet you control" in root_desc or "recharge" in root_desc and "signet" in root_desc
                
                is_corpse_cons = 'Type_Corpse_Exploit' in root_tags or "exploit" in root_desc and "corpse" in root_desc
                
                is_kd_prov = 'Control_Knockdown' in root_tags
                is_kd_cons = "knocked down foe" in root_desc or "against a knocked down" in root_desc
                
                is_int_prov = 'Control_Interrupt' in root_tags
                is_int_cons = "if you interrupt" in root_desc or "whenever you interrupt" in root_desc or "after you interrupt" in root_desc
                
                is_heal_prov = 'Type_Healing' in root_tags
                is_heal_cons = "whenever you heal" in root_desc or "heal bonus" in root_desc
                
                is_degen_prov = 'Type_Degeneration' in root_tags
                is_degen_cons = "suffers from degeneration" in root_desc or "whenever target suffers degeneration" in root_desc # Rare but possible
                
                is_nrg_prov = 'Type_Energy_Management' in root_tags
                is_nrg_cons = "energy lost" in root_desc # Or generally high cost, but user said handled elsewhere.
                
                is_phys_prov = 'Type_Attack_Physical' in root_tags
                is_phys_cons = "physical damage" in root_desc and ("deal" not in root_desc) or "attack skill" in root_desc
                
                is_ranged_prov = 'Type_Attack_Ranged' in root_tags
                is_ranged_cons = "projectile" in root_desc or "bow attack" in root_desc
                
                is_cond_prov = 'Type_Condition' in root_tags
                is_cond_cons = "if target is" in root_desc or "against" in root_desc and any(x in root_desc for x in ["bleeding", "burning", "poison", "disease", "blinded", "dazed", "weakness", "cripple", "deep wound"])
                
                is_buff_prov = 'Type_Buff' in root_tags
                is_stance_prov = 'Type_Stance' in root_tags

                # --- 1. LAW OF AUGMENTATION (Heal Boost) ---
                
                # 1. LAW OF AUGMENTATION (Downstream)
                # If we Heal, look for skills that boost Healing.
                if "heal" in root_desc and ("target ally" in root_desc or "party" in root_desc):
                    q_boost = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%whenever you heal%' OR description LIKE '%healing prayers%' OR description LIKE '%50% extra health%')
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_boost, list(existing_ids), root, context, synergies, debug_mode, "Boosts Healing", stop_check)

                # --- 2. LAW OF ENCHANTMENT ---
                if is_ench_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%for each enchantment%' OR description LIKE '%while you are enchanted%' OR description LIKE '%extend%enchantment%') AND description NOT LIKE '%remove%' AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Uses Enchantment", stop_check)
                if is_ench_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Enchantment') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Enchantment", stop_check)

                # --- 3. LAW OF MULTIPLICATION (AoE Synergy) ---
                if ("adjacent" in root_desc or "nearby" in root_desc) and ("attack" in root_desc or "strike" in root_desc or "shoot" in root_desc):
                     q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%adjacent%' OR description LIKE '%nearby%') AND (description LIKE '%deal%damage%' OR description LIKE '%strike%') AND (skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Weapon_Spell' OR tag='Type_Enchantment')) AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                     self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "AoE Payload", stop_check)

                # --- 4. LAW OF SPIRITUALISM ---
                if is_spirit_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%near a spirit%' OR description LIKE '%earshot of a spirit%' OR description LIKE '%destroy%spirit%' OR description LIKE '%spirit%loses health%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Uses Spirits", stop_check)
                if is_spirit_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Spirit') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Creates Spirits", stop_check)

                # --- 5. LAW OF GRAVITY ---
                if is_kd_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%knocked down foe%' OR description LIKE '%against a knocked down%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Punishes Knockdown", stop_check)
                if is_kd_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Control_Knockdown') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Knockdown", stop_check)

                # --- 6. LAW OF DISRUPTION ---
                if is_int_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%if you interrupt%' OR description LIKE '%whenever you interrupt%' OR description LIKE '%after you interrupt%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Rewards Interrupt", stop_check)
                if is_int_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Control_Interrupt') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Interrupt", stop_check)

                # --- 7. LAW OF THE DEAD ---
                if is_corpse_cons:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%death nova%' OR (description LIKE '%create%' AND description LIKE '%corpse%')) AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Corpses", stop_check)

                # --- 8. LAW OF HEXES ---
                if is_hex_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%hexed foe%' OR description LIKE '%remove a hex%' OR description LIKE '%shatter%') AND description NOT LIKE '%remove%hex%from%ally%' AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Shatters/Uses Hex", stop_check)
                if is_hex_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Hex') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Hex", stop_check)

                # --- 9. LAW OF SIGNETS ---
                if is_signet_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%equipped signet%' OR description LIKE '%signet you control%' OR description LIKE '%recharge%signet%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Uses Signets", stop_check)
                if is_signet_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Signet') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Signet", stop_check)

                # 5. LAW OF SPIRITUALISM
                # Provider: Creates spirits -> Consumer: Uses spirits
                if "spirit" in root[1].lower() or "create a" in root_desc and "spirit" in root_desc:
                    q_spirit_down = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%near a spirit%' OR description LIKE '%earshot of a spirit%' OR description LIKE '%destroy%spirit%' OR description LIKE '%spirit%loses health%')
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_spirit_down, list(existing_ids), root, context, synergies, debug_mode, "Uses Spirits", stop_check)
                
                # Consumer: Uses spirits -> Provider: Creates spirits
                if "near a spirit" in root_desc or "earshot of a spirit" in root_desc or "destroy" in root_desc and "spirit" in root_desc:
                    q_spirit_up = f"""
                        SELECT {cols} FROM {table}
                        WHERE (name LIKE '%spirit%' OR (description LIKE '%create a%' AND description LIKE '%spirit%'))
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_spirit_up, list(existing_ids), root, context, synergies, debug_mode, "Creates Spirits", stop_check)

                # 6. LAW OF GRAVITY (Knockdown Punishers)
                # Provider: Knocks down -> Consumer: Strikes knocked down
                if "knocks down" in root_desc or "knock down" in root_desc:
                    q_kd_down = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%knocked down foe%' OR description LIKE '%against a knocked down%')
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_kd_down, list(existing_ids), root, context, synergies, debug_mode, "Punishes Knockdown", stop_check)
                
                # Consumer -> Provider
                if "knocked down foe" in root_desc or "against a knocked down" in root_desc:
                    q_kd_up = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%knocks down%' OR description LIKE '%knock down%')
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_kd_up, list(existing_ids), root, context, synergies, debug_mode, "Provides Knockdown", stop_check)

                # 7. LAW OF DISRUPTION (Interrupt Rewards)
                # Consumer: If you interrupt -> Provider: Interrupts
                if "if you interrupt" in root_desc or "whenever you interrupt" in root_desc:
                    q_int_up = f"""
                        SELECT s.{cols.replace(', ', ', s.')} FROM {table} s
                        JOIN skill_tags t ON s.skill_id = t.skill_id
                        WHERE (t.tag = 'Control_Interrupt' OR s.description LIKE '%interrupts a skill%' OR s.description LIKE '%interruption%')
                        AND s.skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    # Need to adjust _process_matches query or just use standard query if joining is complex in helper
                    # Simplified: Use subquery for tag check or just text check + tag check in post-process?
                    # Let's stick to text for simplicity in query string, but 'Control_Interrupt' is powerful.
                    # Actually, I can join in the query string passed to _process_matches.
                    
                    q_int_up = f"""
                        SELECT DISTINCT {cols} FROM {table} 
                        WHERE (skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Control_Interrupt') 
                               OR description LIKE '%interrupts a skill%' OR description LIKE '%interruption%')
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_int_up, list(existing_ids), root, context, synergies, debug_mode, "Provides Interrupt", stop_check)

                # 8. LAW OF THE DEAD (Corpse Exploitation)
                # Consumer: Exploit corpse -> Provider: Creates corpses (minions/deaths)
                if "exploit" in root_desc and "corpse" in root_desc:
                    q_dead_up = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%death nova%' OR description LIKE '%create%' AND description LIKE '%corpse%')
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_dead_up, list(existing_ids), root, context, synergies, debug_mode, "Provides Corpses", stop_check)

                # --- 9. LAW OF HEXES ---
                if is_hex_prov: 
                    q_hex_down = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%hexed foe%' OR description LIKE '%remove a hex%' OR description LIKE '%shatter%')
                        AND description NOT LIKE '%remove%hex%from%ally%'
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_hex_down, list(existing_ids), root, context, synergies, debug_mode, "Shatters/Uses Hex", stop_check)

                # 10. LAW OF SIGNETS
                # Provider: Is Signet -> Consumer: Uses Signets
                if is_signet_prov:
                    q_sig_down = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%equipped signet%' OR description LIKE '%signet you control%' OR description LIKE '%recharge%signet%')
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_sig_down, list(existing_ids), root, context, synergies, debug_mode, "Uses Signets", stop_check)
                
                # Consumer -> Provider
                if "equipped signet" in root_desc or "signet you control" in root_desc:
                    q_sig_up = f"""
                        SELECT {cols} FROM {table}
                        WHERE name LIKE '%signet%'
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_sig_up, list(existing_ids), root, context, synergies, debug_mode, "Provides Signet", stop_check)

                # 11. LAW OF HEALING (Standardized)
                if is_heal_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%whenever you heal%' OR description LIKE '%heal bonus%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Boosts Healing", stop_check)
                    
                    # LAW OF STACKING (Healers need multiple heals)
                    q_stack = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Healing') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q_stack, list(existing_ids), root, context, synergies, debug_mode, "Healing Redundancy", stop_check)

                # --- 12. LAW OF CHAINS (Combos) ---
                root_combo = root[9] or 0
                if "lead attack" in root_desc: # Root provides Lead
                    q = f"SELECT {cols} FROM {table} WHERE combo_req = 1 AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Combo: Off-Hand", stop_check)
                elif root_combo == 1: # Root is Off-Hand (provides Off-Hand state)
                    q = f"SELECT {cols} FROM {table} WHERE combo_req = 2 AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Combo: Dual", stop_check)

                # --- 13. LAW OF THE LEGION (Spirit Stacking) ---
                if is_spirit_prov:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Spirit') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Spirit Army", stop_check)

                # 14. LAW OF DEGENERATION (Entropy)
                if is_degen_prov:
                    # Rare consumer? Just general pressure. Maybe skills that trigger on degen?
                    pass 
                if is_degen_cons: # e.g. "suffers from degeneration"
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Degeneration') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Causes Degeneration", stop_check)

                # 13. LAW OF ENERGY
                if is_nrg_prov:
                    # Suggest expensive skills?
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Energy_Consumer') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Uses Energy", stop_check)
                if is_nrg_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Energy_Management') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Energy", stop_check)

                # 14. LAW OF PHYSICAL ATTACKS
                if is_phys_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%physical damage%' OR description LIKE '%attack skill%') AND description LIKE '%bonus%' AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Boosts Physical", stop_check)
                if is_phys_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Attack_Physical') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Physical Attack", stop_check)

                # 15. LAW OF RANGED ATTACKS
                if is_ranged_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%projectile%' OR description LIKE '%bow attack%') AND description LIKE '%bonus%' AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Boosts Ranged", stop_check)
                if is_ranged_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Attack_Ranged') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Ranged Attack", stop_check)

                # --- 16. LAW OF CONDITIONS ---
                if is_cond_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%if target is%' OR description LIKE '%against%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Feeds on Conditions", stop_check)
                if is_cond_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Condition') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Conditions", stop_check)

                # --- 17. LAW OF UTILITY ---
                if is_buff_prov:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Buff') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Buff Redundancy", stop_check)

                # --- 18. LAW OF STANCES ---
                if is_stance_prov:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Stance') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Stance Choice", stop_check)

                # --- B. CONDITION SEARCH ---
                for cond in conditions:
                    cond_l = cond.lower()
                    
                    # DOWNSTREAM (Forward)
                    if cond_l in root_desc and ("target" in root_desc or "foe" in root_desc):
                        q_down = f"""
                            SELECT {cols} FROM {table}
                            WHERE description LIKE ? 
                            AND (description LIKE '%bonus%' OR description LIKE '%additional%' OR description LIKE '%if target%')
                            AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                        """
                        self._process_matches(conn, q_down, [f'%{cond}%'] + list(existing_ids), 
                                           root, context, synergies, debug_mode, f"Feeds on {cond}", stop_check, 
                                           check_negative_context=False)

                    # UPSTREAM (Reverse)
                    is_consumer = False
                    if cond_l in root_desc and ("bonus" in root_desc or "if target" in root_desc or "additional" in root_desc):
                        is_consumer = True
                        
                        # LOGIC FIX: If the skill actually APPLIES the condition, do not treat it as a consumer.
                        # Look for provider phrases preceding the condition.
                        idx = root_desc.find(cond_l)
                        if idx != -1:
                            start = max(0, idx - 40) # Look back ~40 chars
                            pre_text = root_desc[start:idx]
                            providers = ["begins", "suffers", "suffer", "causes", "inflicts", "induces"]
                            if any(p in pre_text for p in providers):
                                is_consumer = False
                    
                    if is_consumer:
                        q_up = f"""
                            SELECT {cols} FROM {table}
                            WHERE description LIKE ? 
                            AND description NOT LIKE '%bonus%' 
                            AND description NOT LIKE '%if target%'
                            AND description NOT LIKE '%remove%'  
                            AND description NOT LIKE '%lose%'
                            AND description NOT LIKE '%cure%'
                            AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                        """
                        self._process_matches(conn, q_up, [f'%{cond}%'] + list(existing_ids), 
                                           root, context, synergies, debug_mode, f"Provides {cond}", stop_check, 
                                           check_negative_context=True, target_cond=cond_l)

        except Exception as e:
            print(f"Physics Engine Error: {e}")
            return []
        finally:
            if 'conn' in locals(): conn.close()

        return synergies

    def _process_matches(self, conn, query, params, root, context, results_list, debug_mode, reason_prefix, stop_check, check_negative_context=False, target_cond=""):
        matches = conn.execute(query, params).fetchall()
        
        for m in matches:
            if stop_check and stop_check(): return 
            
            fail_reasons = []

            # Negative Context Check
            if check_negative_context and target_cond:
                desc = m[2].lower()
                idx = desc.find(target_cond)
                if idx != -1:
                    start = max(0, idx - 20)
                    pre_text = desc[start:idx]
                    negatives = ["remove", "end", "lose", "cure", "reduced", "less"]
                    if any(neg in pre_text for neg in negatives):
                        continue

            # A. Mechanic Checks
            if not self.check_combo_viability(m[9], context.combo_stages): fail_reasons.append("Combo Invalid")
            
            valid, r = self.check_weapon_compatibility(m[11], context)
            if not valid: fail_reasons.append(r)
            
            valid, r = self.check_occupancy_viability(m, context)
            if not valid: fail_reasons.append(r)
            
            valid, r = self.check_causal_viability(m, context)
            if not valid: fail_reasons.append(r)
            
            valid, r = self.check_energy_entropy(m, context)
            if not valid: fail_reasons.append(r)
            
            # B. Physics Checks
            stable, phys_r = self.check_hamiltonian_stability(root, m, context)
            if not stable: fail_reasons.append(phys_r)

            # C. Output
            if not fail_reasons:
                eff, eff_r = context.calculate_efficiency(m)
                if eff < 0.5: 
                    if debug_mode: results_list.append((m[0], f"[DEBUG: Low Eff] {eff_r}"))
                    continue
                
                reason_str = reason_prefix
                if "⚠️" in phys_r: reason_str += f" | {phys_r}"
                results_list.append((m[0], reason_str))
            
            elif debug_mode:
                reason_str = f"[DEBUG] {', '.join(fail_reasons)}"
                results_list.append((m[0], reason_str))

    def _process_matches(self, conn, query, params, root, context, results_list, debug_mode, reason_prefix, stop_check, check_negative_context=False, target_cond=""):
        matches = conn.execute(query, params).fetchall()
        
        for m in matches:
            if stop_check and stop_check(): return 
            
            fail_reasons = []

            # --- NEW: Negative Context Check (Python Side) ---
            # If we are looking for a Provider, ensure it's not a "Fake" provider (e.g. "duration of burning is reduced")
            if check_negative_context and target_cond:
                desc = m[2].lower()
                # Find the condition word
                idx = desc.find(target_cond)
                if idx != -1:
                    # Look at the 20 chars BEFORE the condition
                    start = max(0, idx - 20)
                    pre_text = desc[start:idx]
                    # Words that indicate this is NOT a source
                    negatives = ["remove", "end", "lose", "cure", "reduced", "less"]
                    if any(neg in pre_text for neg in negatives):
                        # Skip this skill silently (it's a false positive)
                        continue

            # A. Mechanic Checks
            if not self.check_combo_viability(m[9], context.combo_stages): fail_reasons.append("Combo Invalid")
            
            valid, r = self.check_weapon_compatibility(m[11], context)
            if not valid: fail_reasons.append(r)
            
            valid, r = self.check_occupancy_viability(m, context)
            if not valid: fail_reasons.append(r)
            
            valid, r = self.check_causal_viability(m, context)
            if not valid: fail_reasons.append(r)
            
            valid, r = self.check_energy_entropy(m, context)
            if not valid: fail_reasons.append(r)
            
            # B. Physics Checks
            stable, phys_r = self.check_hamiltonian_stability(root, m, context)
            if not stable: fail_reasons.append(phys_r)

            # C. Output
            if not fail_reasons:
                eff, eff_r = context.calculate_efficiency(m)
                if eff < 0.5: 
                    if debug_mode: results_list.append((m[0], f"[DEBUG: Low Eff] {eff_r}"))
                    continue
                
                reason_str = reason_prefix
                if "⚠️" in phys_r: reason_str += f" | {phys_r}"
                results_list.append((m[0], reason_str))
            
            elif debug_mode:
                reason_str = f"[DEBUG] {', '.join(fail_reasons)}"
                results_list.append((m[0], reason_str))

class GuildWarsTemplateDecoder:
    def __init__(self, code):
        self.code = code.strip()
        self.base64_map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        self.binary_stream = ""
        self.pos = 0

    def _base64_to_binary_stream(self):
        stream = []
        for char in self.code:
            if char not in self.base64_map: continue
            val = self.base64_map.index(char)
            bin_str = f"{val:06b}"
            stream.append(bin_str[::-1])
        self.binary_stream = "".join(stream)

    def _read_bits(self, length):
        if self.pos + length > len(self.binary_stream): return 0 
        chunk = self.binary_stream[self.pos : self.pos + length]
        self.pos += length
        reversed_chunk = chunk[::-1]
        return int(reversed_chunk, 2)

    def decode(self):
        try:
            self._base64_to_binary_stream()
            template_type = self._read_bits(4)
            version = self._read_bits(4)
            prof_bit_code = self._read_bits(2)
            prof_bits = (prof_bit_code * 2) + 4
            primary_prof = self._read_bits(prof_bits)
            secondary_prof = self._read_bits(prof_bits)
            count_attributes = self._read_bits(4)
            attr_bit_code = self._read_bits(4)
            attr_id_bits = attr_bit_code + 4
            attributes = []
            for _ in range(count_attributes):
                attributes.append([self._read_bits(attr_id_bits), self._read_bits(4)])
            skill_bit_code = self._read_bits(4)
            skill_id_bits = skill_bit_code + 8
            skills = [self._read_bits(skill_id_bits) for _ in range(8)]
            return {
                "header": {"type": template_type, "version": version},
                "profession": {"primary": primary_prof, "secondary": secondary_prof},
                "attributes": attributes,
                "skills": skills
            }
        except: return None

class GuildWarsTemplateEncoder:
    def __init__(self, data):
        self.data = data
        self.base64_map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        self.binary_stream = ""

    def _write_bits(self, value, length):
        v = int(value)
        if v >= (1 << length): v = (1 << length) - 1
        bin_str = f"{v:0{length}b}"
        self.binary_stream += bin_str[::-1]

    def _get_min_bits_for_value(self, value):
        v = int(value)
        if v == 0: return 0
        return v.bit_length()

    def encode(self):
        header = self.data.get('header', {'type': 14, 'version': 0})
        self._write_bits(header.get('type', 14), 4)
        self._write_bits(header.get('version', 0), 4)
        prof = self.data.get('profession', {'primary': 0, 'secondary': 0})
        prim, sec = int(prof.get('primary', 0)), int(prof.get('secondary', 0))
        max_prof_id = max(prim, sec)
        prof_bits_needed = max(4, self._get_min_bits_for_value(max_prof_id))
        prof_bit_code = max(0, math.ceil((prof_bits_needed - 4) / 2))
        if prof_bit_code > 3: prof_bit_code = 3 
        real_prof_bits = (prof_bit_code * 2) + 4
        self._write_bits(prof_bit_code, 2)
        self._write_bits(prim, real_prof_bits)
        self._write_bits(sec, real_prof_bits)
        attrs = self.data.get('attributes', [])
        self._write_bits(len(attrs), 4)
        if len(attrs) > 0:
            max_attr_id = max([int(a[0]) for a in attrs])
            attr_bits_needed = max(4, self._get_min_bits_for_value(max_attr_id))
            attr_bit_code = max(0, attr_bits_needed - 4)
            if attr_bit_code > 15: attr_bit_code = 15
        else: attr_bit_code = 0
        self._write_bits(attr_bit_code, 4)
        for attr in attrs:
            self._write_bits(attr[0], attr_bit_code + 4)
            self._write_bits(attr[1], 4)
        skills = self.data.get('skills', [0]*8)
        max_skill_id = max([int(s) for s in skills])
        skill_bits_needed = max(8, self._get_min_bits_for_value(max_skill_id))
        skill_bit_code = max(0, skill_bits_needed - 8)
        if skill_bit_code > 15: skill_bit_code = 15
        self._write_bits(skill_bit_code, 4)
        for sid in skills: self._write_bits(sid, skill_bit_code + 8)
        remainder = len(self.binary_stream) % 6
        if remainder != 0: self.binary_stream += "0" * (6 - remainder)
        b64 = ""
        for i in range(0, len(self.binary_stream), 6):
            chunk = self.binary_stream[i : i + 6]
            b64 += self.base64_map[int(chunk[::-1], 2)]
        return b64

class SkillRepository:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._cache = {}

    def get_skill(self, skill_id: int, is_pvp: bool = False) -> Optional[Skill]:
        cache_key = (skill_id, is_pvp)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        target_table = "skills_pvp" if is_pvp else "skills"
        
        # 1. ATTEMPT: Fetch Everything (Optimistic)
        # This works if the table has all columns.
        query_full = f"""
            SELECT skill_id, name, profession, attribute, 
                   energy_cost, activation, recharge, adrenaline, is_pve_only,
                   description, is_elite,
                   health_cost, aftercast, combo_req, is_touch, campaign, in_pre
            FROM {target_table}
            WHERE skill_id=?
        """
        
        try:
            self.cursor.execute(query_full, (skill_id,))
            row = self.cursor.fetchone()
            
            if row:
                return self._create_skill_object(row, is_pvp, cache_key)
                
        except sqlite3.OperationalError:
            # 2. FALLBACK: HYBRID FETCH
            # The PvP table is missing columns. We must stitch data together.
            if is_pvp:
                return self._fetch_hybrid_skill(skill_id, cache_key)
            else:
                print(f"Critical DB Error: Main 'skills' table corrupted.")
                
        return None

    def _fetch_hybrid_skill(self, skill_id, cache_key):
        """
        Fetches Text/Basic Stats from PvP table (for UI),
        but fills missing Physics Data from PvE table (for Engine).
        """
        # A. Get Display Data from PvP Table (Safe Columns Only)
        query_safe = """
            SELECT skill_id, name, profession, attribute, 
                   energy_cost, activation, recharge, adrenaline, is_pve_only,
                   description, is_elite
            FROM skills_pvp
            WHERE skill_id=?
        """
        self.cursor.execute(query_safe, (skill_id,))
        pvp_row = self.cursor.fetchone()
        
        if not pvp_row:
            return None
            
        # B. Get Missing Physics Data from Main Skills Table
        query_phys = """
            SELECT health_cost, aftercast, combo_req, is_touch, campaign, in_pre
            FROM skills
            WHERE skill_id=?
        """
        self.cursor.execute(query_phys, (skill_id,))
        phys_row = self.cursor.fetchone()
        
        # Fallback if somehow main table is missing it too
        phys_data = phys_row if phys_row else (0, 0.75, 0, 0, 0, 0)
        
        # pvp_row has indices 0-10. phys_data has 0-5.
        # Combined we get 17 columns: 
        # 0-10 from pvp_row, 11-16 from phys_data
        merged_row = list(pvp_row) + list(phys_data)
        return self._create_skill_object(merged_row, True, cache_key)

    def _create_skill_object(self, row, is_pvp, cache_key):
        skill = Skill(
            id=row[0], 
            name=row[1], 
            icon_filename=f"{row[0]}.jpg", 
            profession=int(row[2] or 0),
            attribute=int(row[3] or -1),
            energy=int(row[4] or 0),
            activation=float(row[5] or 0.0),
            recharge=float(row[6] or 0.0),
            adrenaline=int(row[7] or 0),
            is_pve_only=bool(row[8]),
            description=row[9] or "",
            is_elite=bool(row[10]),
            # Physics Columns
            health_cost=int(row[11] or 0),
            aftercast=float(row[12] or 0.75), 
            combo_req=int(row[13] or 0),
            is_touch=bool(row[14]),
            campaign=int(row[15] or 0),
            in_pre=bool(row[16])
        )
        
        # Load stats if available (Phase 1)
        try:
            # Schema: skill_id, stat_name, ranks 0-21, variable_index
            # We want to order by variable_index to ensure correct matching order
            q_stats = "SELECT * FROM skill_stats WHERE skill_id=? ORDER BY variable_index"
            self.cursor.execute(q_stats, (skill.id,))
            stats = self.cursor.fetchall()
            skill.stats = stats
        except Exception as e:
            print(f"Error loading stats for skill {skill.id}: {e}")
            
        self._cache[cache_key] = skill
        return skill

    def get_all_skills_by_ids(self, ids: List[int], is_pvp: bool = False) -> List[Skill]:
        skills = []
        for sid in ids:
            s = self.get_skill(sid, is_pvp=is_pvp)
            if s:
                skills.append(s)
        return skills

    def get_all_skill_ids(self, is_pvp: bool = False) -> List[int]:
        target_table = "skills_pvp" if is_pvp else "skills"
        try:
            self.cursor.execute(f"SELECT skill_id FROM {target_table}")
            return [row[0] for row in self.cursor.fetchall()]
        except:
            return []

class AttributeEditor(QFrame):
    """
    GUI Panel for managing attribute point distribution.
    Shows attributes for the current primary/secondary professions.
    """
    attributes_changed = pyqtSignal(dict) # Emits {attr_id: rank}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333; border-radius: 4px;")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(2)
        
        self.title = QLabel("Attributes (0/200)")
        self.title.setStyleSheet("font-weight: bold; color: #aaa; border: none;")
        self.layout.addWidget(self.title)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none;")
        self.scroll_content = QWidget()
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.scroll.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll)
        
        self.attr_widgets = {} # {attr_id: (label, spinbox)}
        self.current_points = 0
        self.max_points = 200
        self.current_distribution = {} # {attr_id: rank}
        
        # Mapping of profession to its attributes
        self.PROF_ATTRS = {
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

    def set_professions(self, primary_id, secondary_id, active_skills: List[Skill] = None):
        # Clear existing widgets
        for i in reversed(range(self.grid.count())): 
            self.grid.itemAt(i).widget().setParent(None)
        self.attr_widgets.clear()
        
        relevant_attrs = []
        if primary_id in self.PROF_ATTRS:
            relevant_attrs.extend(self.PROF_ATTRS[primary_id])
        if secondary_id in self.PROF_ATTRS:
            # Add secondary attrs, skipping duplicates
            for aid in self.PROF_ATTRS[secondary_id]:
                if aid not in relevant_attrs:
                    is_primary_of_another = False
                    for pid, primary_aid in PROF_PRIMARY_ATTR.items():
                        if aid == primary_aid and pid != secondary_id:
                            is_primary_of_another = True
                            break
                    
                    if not is_primary_of_another:
                        relevant_attrs.append(aid)
        
        # Check for PvE attributes (negative IDs) in active skills
        if active_skills:
            for s in active_skills:
                if s.attribute < 0 and s.attribute != -1: # -1 is None
                    if s.attribute not in relevant_attrs:
                        relevant_attrs.append(s.attribute)

        # Sort: Standard attributes first (by name), then PvE attributes
        # ATTR_MAP has names for negatives now
        
        # Split into standard and pve
        std_attrs = [a for a in relevant_attrs if a >= 0]
        pve_attrs = [a for a in relevant_attrs if a < 0]
        
        std_attrs.sort(key=lambda x: ATTR_MAP.get(x, ""))
        pve_attrs.sort(key=lambda x: ATTR_MAP.get(x, ""))
        
        final_attrs = std_attrs + pve_attrs
        
        for row, aid in enumerate(final_attrs):
            name = ATTR_MAP.get(aid, f"Attr {aid}")
            lbl = QLabel(name)
            lbl.setStyleSheet("color: #ccc; font-size: 11px; border: none;")
            
            spin = QComboBox()
            
            # Range: 0-12 for standard, 0-10 for PvE
            limit = 12 if aid >= 0 else 10
            spin.addItems([str(i) for i in range(limit + 1)])
            
            spin.setFixedWidth(45)
            spin.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
            
            # Set previous value if it existed
            prev_val = self.current_distribution.get(aid, 0)
            spin.setCurrentIndex(min(prev_val, limit))
            
            spin.currentIndexChanged.connect(lambda _, a=aid: self._on_attr_changed(a))
            
            # Highlight PvE attributes
            if aid < 0:
                lbl.setStyleSheet("color: #FFAA00; font-size: 11px; border: none; font-weight: bold;")
            
            self.grid.addWidget(lbl, row, 0)
            self.grid.addWidget(spin, row, 1)
            self.attr_widgets[aid] = (lbl, spin)
            
        self._update_total()

    def _on_attr_changed(self, attr_id):
        val = int(self.attr_widgets[attr_id][1].currentText())
        self.current_distribution[attr_id] = val
        self._update_total()
        self.attributes_changed.emit(self.current_distribution)

    def _update_total(self):
        # Calculate point cost (GW formula)
        costs = [0, 1, 3, 6, 10, 15, 21, 28, 37, 48, 61, 77, 97]
        
        total = 0
        for aid, (lbl, spin) in self.attr_widgets.items():
            if aid < 0: continue # PvE attributes cost 0 points
            
            rank = int(spin.currentText())
            if rank < len(costs):
                total += costs[rank]
        
        self.current_points = total
        self.title.setText(f"Attributes ({total}/{self.max_points})")
        
        if total > self.max_points:
            self.title.setStyleSheet("font-weight: bold; color: #ff5555; border: none;")
        else:
            self.title.setStyleSheet("font-weight: bold; color: #aaa; border: none;")

    def get_distribution(self):
        return {aid: int(spin.currentText()) for aid, (lbl, spin) in self.attr_widgets.items()}
    
    def set_distribution(self, dist):
        self.current_distribution = dist
        for aid, rank in dist.items():
            if aid in self.attr_widgets:
                self.attr_widgets[aid][1].setCurrentIndex(min(rank, 12))
        self._update_total()

class SynergyEngine:
    def __init__(self, json_path):
        self.builds: List[Build] = []
        self.professions = set()
        self.categories = set()
        self.teams = set()
        self.load_data(json_path)

    def load_data(self, json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for entry in data:
                    code = entry.get('build_code', '')
                    attrs = []
                    if code:
                        decoded = GuildWarsTemplateDecoder(code).decode()
                        if decoded:
                            attrs = decoded.get('attributes', [])

                    category = entry.get('category', 'Uncategorized')
                    if category == "SC": category = "Speed Clear"

                    b = Build(
                        code=code,
                        primary_prof=str(entry.get('primary_profession', 'Unknown')),
                        secondary_prof=str(entry.get('secondary_profession', '')),
                        skill_ids=entry.get('skill_ids', []),
                        category=category,
                        team=entry.get('team', 'General'),
                        attributes=attrs
                    )
                    self.builds.append(b)
                    self.professions.add(b.primary_prof)
                    self.categories.add(b.category)
                    self.teams.add(b.team)
        except FileNotFoundError:
            print("JSON file not found.")

    def get_suggestions(self, active_skill_ids: List[int], limit=100, category=None, team=None, min_overlap=None) -> List[tuple[int, float]]:
        candidate_builds = self.builds
        if category and category != "All":
            candidate_builds = [b for b in candidate_builds if b.category == category]
        if team and team != "All":
            candidate_builds = [b for b in candidate_builds if b.team == team]

        active_set = set(active_skill_ids)
        if not active_set:
            matching_builds = candidate_builds
        else:
            threshold = 1
            if min_overlap is not None:
                threshold = min_overlap
            elif len(active_set) >= 2:
                threshold = 2
            
            if threshold == 1:
                 matching_builds = [b for b in candidate_builds if not active_set.isdisjoint(set(b.skill_ids))]
            else:
                 matching_builds = []
                 for b in candidate_builds:
                     shared = active_set.intersection(set(b.skill_ids))
                     if len(shared) >= threshold:
                         matching_builds.append(b)
        
        if not matching_builds:
            return []

        counter = Counter()
        total_matches = len(matching_builds)
        for b in matching_builds:
            for sid in b.skill_ids:
                if sid not in active_set and sid != 0: counter[sid] += 1
        
        results = []
        for sid, count in counter.most_common(limit):
            results.append((sid, count / total_matches))
        return results

    def filter_skills(self, prof=None, category=None, team=None) -> Set[int]:
        valid_ids = set()
        for b in self.builds:
            if prof and prof != "All" and b.primary_prof != prof:
                continue
            if category and category != "All" and b.category != category:
                continue
            if team and team != "All" and b.team != team:
                continue
            
            valid_ids.update(b.skill_ids)
        return valid_ids

# =============================================================================
# GUI COMPONENTS
# =============================================================================

class SkillSlot(QFrame):
    skill_equipped = pyqtSignal(int, int) 
    skill_removed = pyqtSignal(int)       
    clicked = pyqtSignal(int)             

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.current_skill_id = None
        self.is_ghost = False
        
        self.setFixedSize(ICON_SIZE + 4, ICON_SIZE + 4)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #555;
                background-color: #1a1a1a;
                border-radius: 4px;
            }
        """)
        
        self.icon_label = QLabel(self)
        self.icon_label.setGeometry(2, 2, ICON_SIZE, ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) 

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
            self.setStyleSheet("border: 2px solid #00AAFF; background-color: #222;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.update_style()

    def dropEvent(self, event):
        skill_id = int(event.mimeData().text())
        self.skill_equipped.emit(self.index, skill_id)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_skill_id is not None:
                self.clicked.emit(self.current_skill_id)
        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_skill_id is not None:
                self.clear_slot()

    def mouseDoubleClickEvent(self, event):
        if self.current_skill_id is not None:
            if self.is_ghost:
                self.skill_equipped.emit(self.index, self.current_skill_id)
            else:
                self.clear_slot()

    def set_skill(self, skill_id, skill_obj: Skill = None, ghost=False, confidence=0.0, rank=0):
        self.current_skill_id = skill_id
        self.is_ghost = ghost
        
        icon_file = skill_obj.icon_filename if skill_obj else f"{skill_id}.jpg"
        if not icon_file.lower().endswith('.jpg'):
            icon_file += '.jpg'
            
        path = os.path.join(ICON_DIR, icon_file)
        
        pix = QPixmap()
        if os.path.exists(path):
            pix.load(path)
        else:
            pix = QPixmap(ICON_SIZE, ICON_SIZE)
            pix.fill(QColor("#333"))
            p = QPainter(pix)
            p.setPen(Qt.GlobalColor.white)
            p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, skill_obj.name if skill_obj else str(skill_id))
            p.end()

        if ghost:
            transparent_pix = QPixmap(pix.size())
            transparent_pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(transparent_pix)
            p.setOpacity(0.4)
            p.drawPixmap(0, 0, pix)
            p.end()
            self.icon_label.setPixmap(transparent_pix)
        else:
            self.icon_label.setPixmap(pix)

        # Build detailed tooltip
        if skill_obj:
            desc = skill_obj.get_description_for_rank(rank)
            attr_name = ATTR_MAP.get(skill_obj.attribute, "None")
            tooltip = f"<b>{skill_obj.name}</b><br/>"
            if skill_obj.attribute != -1:
                tooltip += f"<i>{attr_name} ({rank})</i><br/>"
            tooltip += f"<br/>{desc}"
            
            if ghost:
                if isinstance(confidence, str):
                    tooltip = f"<b>Smart Synergy:</b> {confidence}<br/><hr/>" + tooltip
                else:
                    tooltip = f"<b>Synergy: {confidence:.0%}</b><br/><hr/>" + tooltip
            
            self.setToolTip(tooltip)
        else:
            self.setToolTip(str(skill_id))

        self.update_style()

    def clear_slot(self, silent=False):
        self.current_skill_id = None
        self.is_ghost = False
        self.icon_label.clear()
        self.setToolTip("")
        if not silent:
            self.skill_removed.emit(self.index)
        self.update_style()

    def update_style(self):
        if self.current_skill_id and not self.is_ghost:
            self.setStyleSheet("border: 2px solid #666; background-color: #2a2a2a;")
        else:
            self.setStyleSheet("border: 2px dashed #555; background-color: #1a1a1a;")

class SkillInfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(100)
        self.setStyleSheet("background-color: #1a1a1a; border-left: 1px solid #444;")
        layout = QVBoxLayout(self)
        
        self.lbl_name = QLabel("Select a skill")
        self.lbl_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #00AAFF;")
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(64, 64)
        self.lbl_icon.setStyleSheet("border: 1px solid #444;")
        
        self.txt_desc = QLabel("")
        self.txt_desc.setWordWrap(True)
        self.txt_desc.setStyleSheet("color: #ccc; font-style: italic;")
        self.txt_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.details = QLabel("")
        self.details.setStyleSheet("color: #aaa;")
        self.details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.txt_desc)
        layout.addWidget(self.details)
        layout.addStretch()

    def update_info(self, skill: Skill, rank=0):
        self.lbl_name.setText(skill.name)
        
        path = os.path.join(ICON_DIR, skill.icon_filename)
        if os.path.exists(path):
            self.lbl_icon.setPixmap(QPixmap(path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.lbl_icon.clear()
            
        self.txt_desc.setText(skill.get_description_for_rank(rank))
        
        info = []
        info.append(f"Profession: {skill.get_profession_str()}")
        attr_name = skill.get_attribute_str()
        if skill.attribute != -1:
             info.append(f"Attribute: {attr_name} ({rank})")
        else:
             info.append(f"Attribute: {attr_name}")
        if skill.energy: info.append(f"Energy: {skill.energy}")
        if skill.health_cost: info.append(f"<b>Sacrifice: {skill.health_cost} HP</b>") # NEW
        if skill.adrenaline: info.append(f"Adrenaline: {skill.adrenaline}")
        
        # Combined Timing Display
        total_time = skill.activation + skill.aftercast
        info.append(f"Cast: {skill.activation}s + {skill.aftercast}s ({total_time}s)") # NEW
        
        if skill.recharge: info.append(f"Recharge: {skill.recharge}s")
        
        if skill.is_elite: info.append("<b>Elite Skill</b>")
        if skill.is_pve_only: info.append("<i>PvE Only</i>")
        if skill.combo_req > 0: info.append(f"Combo Stage: {skill.combo_req}") # NEW
        
        self.details.setText("<br>".join(info))

class BuildPreviewWidget(QFrame):
    clicked = pyqtSignal(str) 
    skill_clicked = pyqtSignal(Skill) 

    def __init__(self, build: Build, repo: SkillRepository, is_pvp=False, parent=None):
        super().__init__(parent)
        self.build = build
        self.repo = repo
        self.setFixedHeight(ICON_SIZE + 80) 
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QFrame {
                background-color: #222;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QFrame:hover {
                background-color: #333;
                border: 1px solid #666;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)
        
        p1_name = PROF_MAP.get(int(build.primary_prof) if build.primary_prof.isdigit() else 0, "No Profession")
        p2_name = PROF_MAP.get(int(build.secondary_prof) if build.secondary_prof.isdigit() else 0, "No Profession")
        p1 = PROF_SHORT_MAP.get(p1_name, "X")
        p2 = PROF_SHORT_MAP.get(p2_name, "X")
        
        lbl_prof = QLabel(f"{p1}/{p2}")
        lbl_prof.setStyleSheet("color: #AAA; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        lbl_prof.setFixedWidth(50)
        lbl_prof.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_prof)
        
        for sid in build.skill_ids:
            skill_widget = None
            if sid != 0:
                skill = repo.get_skill(sid, is_pvp=is_pvp)
                if skill:
                    skill_widget = DraggableSkillIcon(skill)
                    skill_widget.setStyleSheet("background: transparent; border: none;")
                    skill_widget.clicked.connect(self.skill_clicked.emit)
            
            if skill_widget:
                layout.addWidget(skill_widget)
            else:
                placeholder = QFrame()
                placeholder.setFixedSize(ICON_SIZE + 10, ICON_SIZE + 60)
                placeholder.setStyleSheet("background: transparent; border: 1px dashed #444;")
                layout.addWidget(placeholder)
            
        layout.addStretch()
        
        btn_load = QPushButton("Load")
        btn_load.setFixedSize(60, 40)
        btn_load.setStyleSheet("""
            QPushButton {
                background-color: #0066CC; 
                color: white; 
                border: none; 
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0088FF;
            }
        """)
        btn_load.clicked.connect(lambda: self.clicked.emit(self.build.code))
        layout.addWidget(btn_load)

class FilterWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, db_path, engine, filters):
        super().__init__()
        self.db_path = db_path
        self.engine = engine
        self.filters = filters

    def run(self):
        try:
            # SQLite connections cannot be shared across threads.
            local_repo = SkillRepository(self.db_path)
            
            prof = self.filters['prof']
            cat = self.filters['cat']
            team = self.filters['team']
            search_text = self.filters['search_text']
            # Ensure is_pvp is strictly a boolean
            is_pvp = bool(self.filters['is_pvp'])
            is_pve_only = bool(self.filters['is_pve_only'])
            is_elites_only = self.filters['is_elites_only']
            is_no_elites = self.filters['is_no_elites']
            is_pre_only = self.filters['is_pre_only']

            # 1. Get initial list of IDs based on team/category
            if cat == "All" and team == "All":
                valid_ids = local_repo.get_all_skill_ids(is_pvp=is_pvp)
            else:
                valid_ids = self.engine.filter_skills(prof, cat, team)
            
            filtered_skills = []
            target_prof_id = -1
            if prof != "All":
                try:
                    target_prof_id = int(prof)
                except:
                    pass

            for sid in valid_ids:
                if self.isInterruptionRequested():
                    return
                
                # Fetch skill using the correct mode
                skill = local_repo.get_skill(sid, is_pvp=is_pvp)
                
                if skill:
                    # --- STRICT MODE CHECKS ---
                    if is_pvp:
                        # In PvP Mode: Hide PvE-Only skills
                        if skill.is_pve_only:
                            continue
                    else:
                        # In PvE Mode: Hide explicit PvP skills
                        # (This catches skills named "Abc (PvP)" which often slip into the main table)
                        if "(PvP)" in skill.name:
                            continue

                    # --- PvE ONLY ---
                    if is_pve_only and not skill.is_pve_only:
                        continue

                    # --- SEARCH ---
                    if search_text and search_text not in skill.name.lower():
                        continue
                        
                    # --- ELITE FILTERS ---
                    if is_elites_only and not skill.is_elite:
                        continue
                    if is_no_elites and skill.is_elite:
                        continue
                        
                    # --- PRE-SEARING ---
                    if is_pre_only and not skill.in_pre:
                        continue
                        
                    # --- PROFESSION ---
                    if target_prof_id != -1:
                        if skill.profession != target_prof_id:
                            continue
                        
                    filtered_skills.append(skill)

            # Sort by attribute (ascending), then by name (ascending)
            filtered_skills.sort(key=lambda x: (x.attribute, x.name))

            self.finished.emit(filtered_skills)
        except Exception as e:
            print(f"FilterWorker Error: {e}")
        finally:
            if 'local_repo' in locals():
                local_repo.conn.close()

class SynergyWorker(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, engine, active_skill_ids, prof_id=0, mode="legacy", debug=False):
        super().__init__()
        self.engine = engine
        self.active_skill_ids = active_skill_ids
        self.prof_id = prof_id 
        self.mode = mode
        self.debug = debug
        self._is_interrupted = False

    def run(self):
        try:
            results = []
            if self.mode == "smart":
                # PASS A LAMBDA THAT CHECKS IF THIS THREAD IS INTERRUPTED
                results = self.engine.find_synergies(
                    self.active_skill_ids, 
                    self.prof_id, 
                    debug_mode=self.debug,
                    stop_check=lambda: self.isInterruptionRequested()
                )
            else:
                results = self.engine.get_suggestions(self.active_skill_ids, limit=5000)
            
            if not self.isInterruptionRequested():
                self.results_ready.emit(results)
        except Exception as e:
            print(f"Worker Error: {e}")

    def stop(self):
        self.requestInterruption() # New standard PyQt6 way
        self.quit()
        self.wait()

class SkillItemDelegate(QStyledItemDelegate):
    """
    Renders the skill items to look like the old DraggableSkillIcon 
    (Card style with border), but using fast painting instead of Widgets.
    """
    def sizeHint(self, option, index):
        # Matches your old DraggableSkillIcon size (ICON_SIZE + 10, ICON_SIZE + 60)
        return QSize(ICON_SIZE + 10, ICON_SIZE + 60)

    def paint(self, painter, option, index):
        if not index.isValid(): return

        painter.save()
        
        # Data Retrieval
        skill_id = index.data(Qt.ItemDataRole.UserRole)
        name = index.data(Qt.ItemDataRole.DisplayRole)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        
        # Style Setup
        rect = option.rect
        rect.adjust(2, 2, -2, -2) # Margin
        
        # Background & Border
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QColor("#333"))
            painter.setPen(QColor("#666"))
        elif option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor("#2a2a2a"))
            painter.setPen(QColor("#00AAFF"))
        else:
            painter.setBrush(QColor("#222"))
            painter.setPen(QColor("#444"))
            
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawRoundedRect(rect, 4, 4)
        
        # Icon
        icon_rect = QRect(rect.center().x() - 32, rect.top() + 10, 64, 64)
        if icon:
            painter.drawPixmap(icon_rect, icon.pixmap(64, 64))
        
        # Text
        text_rect = QRect(rect.left() + 2, rect.top() + 80, rect.width() - 4, 40)
        painter.setPen(QColor("#EEE"))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, name)
        
        painter.restore()

class SkillLibraryWidget(QListWidget):
    """
    High-performance replacement for the ScrollArea + FlowLayout.
    """
    skill_clicked = pyqtSignal(int)
    skill_double_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        self.setDragEnabled(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setSpacing(5)
        self.setStyleSheet("QListWidget { background-color: #111; border: none; }")
        
        # Attach the custom painter
        self.setItemDelegate(SkillItemDelegate(self))

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        
        skill_id = item.data(Qt.ItemDataRole.UserRole)
        icon = item.icon()
        
        # Create standard drag object compatible with your existing SkillSlot
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(skill_id))
        drag.setMimeData(mime_data)
        drag.setPixmap(icon.pixmap(64, 64))
        drag.setHotSpot(QPoint(32, 32))
        drag.exec(Qt.DropAction.CopyAction)

    def mousePressEvent(self, event):
        # Handle clicks normally, but emit signal for info panel
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        if item:
            sid = item.data(Qt.ItemDataRole.UserRole)
            self.skill_clicked.emit(sid)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            sid = item.data(Qt.ItemDataRole.UserRole)
            self.skill_double_clicked.emit(sid)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("B.O.O.K.A.H. (Build Optimization & Organization for Knowledge-Agnostic Hominids)")
        self.resize(1200, 800)
        
        # Load Data
        self.repo = SkillRepository(DB_FILE)
        self.engine = SynergyEngine(JSON_FILE) # Legacy
        self.smart_engine = HamiltonianEngine(DB_FILE) # NEW: Physics Engine
        
        # State
        self.bar_skills = [None] * 8 
        self.suggestion_offset = 0
        self.current_suggestions = [] 
        self.all_icon_widgets = []
        self.skill_widgets = {} # {skill_id: DraggableSkillIcon}
        self.is_swapped = False 
        self.template_path = "" 
        self.current_selected_skill_id = None
        self.team_synergy_skills = [] # Skills from loaded team for Smart Mode
        
        self.setAcceptDrops(True) # Enable Drag & Drop
        # Debounce timer for search/filter inputs
        self.filter_debounce_timer = QTimer()
        self.filter_debounce_timer.setSingleShot(True)
        self.filter_debounce_timer.timeout.connect(self._run_filter)
        self.init_ui()
        self.apply_filters() 

    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.builder_tab = QWidget()
        self.tabs.addTab(self.builder_tab, "Builder")
        self.init_builder_ui(self.builder_tab)

        self.map_tab = QWidget()
        self.tabs.addTab(self.map_tab, "Synergy Map")
        self.init_map_ui(self.map_tab)

    def init_map_ui(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        if HAS_WEBENGINE:
            try:
                view = QWebEngineView()
                file_path = resource_path("synergy_map.html")
                view.load(QUrl.fromLocalFile(file_path))
                layout.addWidget(view)
            except Exception as e:
                layout.addWidget(QLabel(f"Error loading map: {e}"))
        else:
            layout.addWidget(QLabel("PyQt6-WebEngine is not installed."))

    def update_team_dropdown(self):
        selected_cat = self.combo_cat.currentText()
        current_team = self.combo_team.currentText()
        
        valid_teams = set()
        if selected_cat == "All":
            valid_teams = self.engine.teams
        else:
            for b in self.engine.builds:
                if b.category == selected_cat:
                    valid_teams.add(b.team)
        
        self.combo_team.blockSignals(True) 
        self.combo_team.clear()
        self.combo_team.addItem("All")
        
        # Priority sort: Solo first, then others
        if "Solo" in valid_teams:
            self.combo_team.addItem("Solo")
            others = sorted([t for t in valid_teams if t != "Solo"])
        else:
            others = sorted(list(valid_teams))
        
        self.combo_team.addItems(others)
        
        index = self.combo_team.findText(current_team)
        if index != -1:
            self.combo_team.setCurrentIndex(index)
        else:
            self.combo_team.setCurrentIndex(0) # Default to "All"
            
        self.combo_team.blockSignals(False)
        self.apply_filters()

    def init_builder_ui(self, parent_widget):
        main_layout = QVBoxLayout(parent_widget)

        # --- 1. Top Filters ---
        filter_layout = QHBoxLayout()
        
        self.combo_prof = QComboBox()
        self.combo_prof.addItem("All")
        for pid in sorted(PROF_MAP.keys()):
            self.combo_prof.addItem(f"{pid} - {PROF_MAP[pid]}")
        self.combo_prof.currentTextChanged.connect(self.apply_filters)
        
        self.combo_cat = QComboBox()
        self.combo_cat.addItem("All")
        self.combo_cat.addItems(sorted(list(self.engine.categories)))
        self.combo_cat.currentTextChanged.connect(self.update_team_dropdown)
        
        self.combo_team = QComboBox()
        self.combo_team.addItem("All")
        self.combo_team.addItems(sorted(list(self.engine.teams)))
        self.combo_team.currentTextChanged.connect(self.apply_filters)
        
        filter_layout.addWidget(QLabel("Profession:"))
        filter_layout.addWidget(self.combo_prof)
        filter_layout.addWidget(QLabel("Category:"))
        filter_layout.addWidget(self.combo_cat)
        
        filter_layout.addSpacing(20)
        
        filter_layout.addWidget(QLabel("Team:"))
        self.combo_team = QComboBox()
        self.combo_team.addItem("All")
        
        # Priority sort: Solo first
        all_teams = self.engine.teams
        if "Solo" in all_teams:
            self.combo_team.addItem("Solo")
            others = sorted([t for t in all_teams if t != "Solo"])
        else:
            others = sorted(list(all_teams))
        self.combo_team.addItems(others)
        
        self.combo_team.currentTextChanged.connect(self.apply_filters)
        self.combo_team.setCurrentIndex(0) # Default to "All" (No filter)
        filter_layout.addWidget(self.combo_team)
        
        self.btn_manage_teams = QPushButton("Manage Teams")
        self.btn_manage_teams.clicked.connect(self.open_team_manager)
        filter_layout.addWidget(self.btn_manage_teams)
        
        filter_layout.addSpacing(20)
        pvp_col = QVBoxLayout()
        pvp_col.addSpacing(26)
        self.check_pvp = QCheckBox("PvP")
        self.check_pvp.toggled.connect(self.on_pvp_toggled) # Updated handler
        pvp_col.addWidget(self.check_pvp)

        self.check_pve_only = QCheckBox("PvE Only")
        self.check_pve_only.toggled.connect(self.apply_filters)
        pvp_col.addWidget(self.check_pve_only)
        filter_layout.addLayout(pvp_col)

        filter_layout.addSpacing(20)
        self.check_pre = QCheckBox("Pre")
        self.check_pre.toggled.connect(self.apply_filters)
        filter_layout.addWidget(self.check_pre)

        filter_layout.addSpacing(20)
        elites_col = QVBoxLayout()
        elites_col.addSpacing(26)
        self.check_elites_only = QCheckBox("Elites")
        self.check_no_elites = QCheckBox("No Elites")
        self.check_elites_only.toggled.connect(self.toggle_elites)
        self.check_no_elites.toggled.connect(self.toggle_no_elites)
        elites_col.addWidget(self.check_elites_only)
        elites_col.addWidget(self.check_no_elites)
        filter_layout.addLayout(elites_col)

        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel("Search:"))
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Search skills...")
        self.edit_search.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.edit_search)
        
        filter_layout.addStretch()
        
        main_layout.addLayout(filter_layout)

        # --- 1b. Export Controls ---
        export_layout = QHBoxLayout()
        
        self.btn_path = QPushButton("Select Template Folder")
        self.btn_path.clicked.connect(self.choose_template_path)
        export_layout.addWidget(self.btn_path)
        
        self.lbl_path = QLabel("Path: (No folder selected)")
        self.lbl_path.setStyleSheet("color: #888; font-style: italic;")
        export_layout.addWidget(self.lbl_path)
        
        export_layout.addStretch()
        
        main_layout.addLayout(export_layout)

        # --- 2. Center Splitter ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.library_widget = SkillLibraryWidget()
        self.library_widget.skill_clicked.connect(self.handle_skill_id_clicked)
        self.library_widget.skill_double_clicked.connect(lambda sid: self.handle_skill_equipped_auto(sid))
        self.splitter.addWidget(self.library_widget)
        
        self.info_panel = SkillInfoPanel()
        self.splitter.addWidget(self.info_panel)
        
        # Attribute Editor (Phase 2 & UI Polish)
        self.attr_editor = AttributeEditor()
        self.attr_editor.setMinimumWidth(100)
        self.attr_editor.attributes_changed.connect(self.on_attributes_changed)
        self.splitter.addWidget(self.attr_editor)
        
        # Set resize mode for splitter to make center/right panels stick but resizable
        # Index 0: Scroll Area (Stretch)
        # Index 1: Info Panel
        # Index 2: Attribute Editor
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 0)
        
        # Set initial sizes: [Flexible, Info: 255, Attr: 145]
        # (Increased by 10% from previous 231/132)
        self.splitter.setSizes([800, 255, 145])
        
        main_layout.addWidget(self.splitter, stretch=1)

        # --- 3. Build Bar (Updated Layout) ---
        bar_container = QFrame()
        bar_container.setFixedHeight(140) # Increased height slightly to fit checkbox
        bar_container.setStyleSheet("background-color: #111; border-top: 1px solid #444;")
        container_layout = QHBoxLayout(bar_container)

        # --- NEW: Cycle & Debug Column ---
        cycle_container = QWidget()
        cycle_layout = QVBoxLayout(cycle_container)
        cycle_layout.setContentsMargins(0, 5, 0, 5)
        cycle_layout.setSpacing(5)

        self.btn_select_zone = QPushButton("Select Zone")
        self.btn_select_zone.setFixedSize(90, 50)
        self.btn_select_zone.setStyleSheet("""
            QPushButton { background-color: #444; color: white; border-radius: 4px; font-weight: bold; font-size: 10px; }
            QPushButton:hover { background-color: #555; }
        """)
        self.btn_select_zone.clicked.connect(self.open_location_manager)
        self.btn_select_zone.setVisible(False)
        cycle_layout.addWidget(self.btn_select_zone)

        self.btn_load_team_synergy = QPushButton("Load Teambuild\nto Bar")
        self.btn_load_team_synergy.setFixedSize(90, 50)
        self.btn_load_team_synergy.setStyleSheet("""
            QPushButton { background-color: #224466; color: white; border-radius: 4px; font-weight: bold; font-size: 10px; }
            QPushButton:hover { background-color: #335577; }
        """)
        self.btn_load_team_synergy.setVisible(False)
        self.btn_load_team_synergy.clicked.connect(self.open_team_manager_for_synergy)
        cycle_layout.addWidget(self.btn_load_team_synergy)
        
        container_layout.addWidget(cycle_container)

        # --- Skill Bar Area (Vertical wrapper for Bar + Cycle Button) ---
        bar_area_widget = QWidget()
        bar_area_layout = QVBoxLayout(bar_area_widget)
        bar_area_layout.setContentsMargins(0, 0, 0, 0)
        bar_area_layout.setSpacing(5)

        bar_layout = QHBoxLayout()
        bar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.slots = []
        for i in range(8):
            slot = SkillSlot(i)
            slot.skill_equipped.connect(self.handle_skill_equipped)
            slot.skill_removed.connect(self.handle_skill_removed)
            slot.clicked.connect(self.handle_skill_id_clicked)
            bar_layout.addWidget(slot)
            self.slots.append(slot)
            
        bar_area_layout.addLayout(bar_layout)

        # Cycle button moved here (beneath the bar)
        self.btn_cycle = QPushButton("Cycle Suggestions")
        self.btn_cycle.setFixedSize(150, 24)
        self.btn_cycle.setStyleSheet("""
            QPushButton { background-color: #444; color: white; border-radius: 4px; font-size: 10px; }
            QPushButton:hover { background-color: #555; }
        """)
        self.btn_cycle.clicked.connect(self.cycle_suggestions)
        bar_area_layout.addWidget(self.btn_cycle, alignment=Qt.AlignmentFlag.AlignCenter)

        container_layout.addStretch(1)
        container_layout.addWidget(bar_area_widget)
        container_layout.addSpacing(20) 
        
        # --- Control Layout (Right Side) ---
        control_layout = QVBoxLayout()
        
        self.check_show_others = QCheckBox("Show Other\nProfessions")
        self.check_show_others.toggled.connect(self.update_suggestions)
        control_layout.addWidget(self.check_show_others)

        self.check_lock_suggestions = QCheckBox("Lock")
        self.check_lock_suggestions.toggled.connect(self.update_suggestions)
        control_layout.addWidget(self.check_lock_suggestions)
        
        self.check_smart_mode = QCheckBox("Smart Mode\n(experimental)")
        self.check_smart_mode.setStyleSheet("color: #FFD700; font-weight: bold;")
        self.check_smart_mode.toggled.connect(self.on_smart_mode_toggled)
        control_layout.addWidget(self.check_smart_mode)

        container_layout.addLayout(control_layout)
        container_layout.addStretch(1)

        # --- Build Code Box (Rightmost) ---
        code_box = QFrame()
        code_box.setFixedWidth(250)
        code_layout = QVBoxLayout(code_box)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Build Code:"))
        
        self.lbl_prof_display = QLabel("X/X")
        self.lbl_prof_display.setStyleSheet("color: #888; font-weight: bold;")
        header_layout.addWidget(self.lbl_prof_display)
        
        self.btn_swap_prof = QPushButton("Swap")
        self.btn_swap_prof.setFixedSize(40, 20)
        self.btn_swap_prof.setStyleSheet("font-size: 10px; padding: 0px;")
        self.btn_swap_prof.clicked.connect(self.swap_professions)
        header_layout.addWidget(self.btn_swap_prof)
        
        header_layout.addStretch()
        code_layout.addLayout(header_layout)
        
        self.edit_code = QLineEdit()
        self.edit_code.setPlaceholderText("Paste build code here...")
        self.edit_code.setStyleSheet("background-color: #222; color: #00AAFF; font-weight: bold;")
        code_layout.addWidget(self.edit_code)

        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load")
        self.btn_load.clicked.connect(self.load_code)
        btn_layout.addWidget(self.btn_load)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.clicked.connect(self.copy_code)
        btn_layout.addWidget(self.btn_copy)
        
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setStyleSheet("background-color: #552222;")
        self.btn_reset.clicked.connect(self.reset_build)
        btn_layout.addWidget(self.btn_reset)
        
        code_layout.addLayout(btn_layout)
        container_layout.addWidget(code_box)
        main_layout.addWidget(bar_container)

    def on_smart_mode_toggled(self, checked):
        if hasattr(self, 'btn_load_team_synergy'):
            self.btn_load_team_synergy.setVisible(checked)
        if hasattr(self, 'btn_select_zone'):
            self.btn_select_zone.setVisible(checked)
        # Clear team synergy context if turning off smart mode? 
        # User might want it to persist, but for now we keep it.
        self.update_suggestions()

    def open_team_manager_for_synergy(self):
        # We'll use a modified TeamManagerDialog logic or just a specialized call
        dlg = TeamManagerDialog(self, self.engine)
        # Change button text to indicate synergy mode
        dlg.btn_load.setText("Load Team")
        dlg.btn_load.setToolTip("Load all skills from this team to use as synergy context")
        
        # Hide export and import buttons for smart mode context
        dlg.btn_export.setVisible(False)
        dlg.btn_add_folder.setVisible(False)
        
        # Override the load_team method for this instance
        original_load = dlg.load_team
        def synergy_load():
            item = dlg.list_widget.currentItem()
            if not item: return
            team_name = item.text()
            self.load_team_for_synergy(team_name)
            dlg.accept()
            
        dlg.load_team = synergy_load
        dlg.exec()

    def open_location_manager(self):
        dlg = LocationManagerDialog(self, DB_FILE)
        if dlg.exec():
            selected_zone = dlg.get_selected_location()
            if selected_zone:
                print(f"Selected Zone: {selected_zone}")
                # Logic for zone-based builds/enemies can be added here later

    def load_team_for_synergy(self, team_name):
        self.team_synergy_skills = []
        builds = [b for b in self.engine.builds if b.team == team_name]
        
        all_ids = set()
        for b in builds:
            for sid in b.skill_ids:
                if sid != 0:
                    all_ids.add(sid)
        
        self.team_synergy_skills = list(all_ids)
        print(f"Loaded {len(self.team_synergy_skills)} skills from team '{team_name}' for synergy context.")
        self.update_suggestions()

    def open_team_manager(self):
        dlg = TeamManagerDialog(self, self.engine)
        dlg.exec()
        # Refresh team dropdown after dialog closes
        current_team = self.combo_team.currentText()
        self.combo_team.blockSignals(True)
        self.combo_team.clear()
        self.combo_team.addItem("All")
        
        all_teams = self.engine.teams
        if "Solo" in all_teams:
            self.combo_team.addItem("Solo")
            others = sorted([t for t in all_teams if t != "Solo"])
        else:
            others = sorted(list(all_teams))
        self.combo_team.addItems(others)
        
        idx = self.combo_team.findText(current_team)
        if idx != -1: self.combo_team.setCurrentIndex(idx)
        else: self.combo_team.setCurrentIndex(0)
        self.combo_team.blockSignals(False)

    def on_pvp_toggled(self, checked):
        # Update both engines and refresh
        mode = "pvp" if checked else "pve"
        self.smart_engine.set_mode(mode)
        
        # Refresh current info panel if visible
        if self.current_selected_skill_id:
            self.handle_skill_id_clicked(self.current_selected_skill_id)
            
        self.apply_filters()
        self.update_suggestions()
        self.refresh_equipped_skills()

    def import_build_to_db(self):
        code = self.edit_code.text().strip()
        if not code:
            QMessageBox.warning(self, "Import Error", "Please enter or load a build code first.")
            return
            
        decoder = GuildWarsTemplateDecoder(code)
        decoded = decoder.decode()
        
        if not decoded:
            QMessageBox.warning(self, "Import Error", "Invalid Build Code.")
            return
            
        entry = {
            "build_code": code,
            "primary_profession": str(decoded['profession']['primary']),
            "secondary_profession": str(decoded['profession']['secondary']),
            "skill_ids": decoded['skills'],
            "category": "User Imported",
            "team": "User Imported"
        }
        
        try:
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []
                
            if any(d.get('build_code') == code for d in data):
                QMessageBox.information(self, "Import", "This build is already in the database.")
                return
                
            data.append(entry)
            
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
                
            self.engine = SynergyEngine(JSON_FILE)
            self.apply_filters()
            self.update_team_dropdown() 
            
            QMessageBox.information(self, "Success", "Build successfully imported into the synergy database!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save build: {e}")

    def reset_build(self):
        self.bar_skills = [None] * 8
        self.suggestion_offset = 0
        self.is_swapped = False
        
        self.combo_prof.setCurrentIndex(0) 
        self.combo_cat.setCurrentIndex(0) 
        self.combo_team.setCurrentIndex(0) 
        self.check_pvp.setChecked(False)
        self.check_pve_only.setChecked(False)
        if hasattr(self, 'check_pre'):
             self.check_pre.setChecked(False)
        self.check_show_others.setChecked(False)
        self.check_lock_suggestions.setChecked(False)
        if hasattr(self, 'check_smart_mode'):
             self.check_smart_mode.setChecked(False)
        self.edit_search.clear()
        self.edit_code.clear()
        
        for slot in self.slots:
            slot.clear_slot(silent=True)
            
        self.apply_filters()
        self.update_suggestions()

    def choose_template_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Template Folder", self.template_path)
        if path:
            self.template_path = path
            self.lbl_path.setText(f"Path: {path}")

    def export_team_builds(self):
        if not self.template_path:
            self.choose_template_path()
            if not self.template_path:
                return 
                
        team_name = self.combo_team.currentText()
        if team_name == "All":
            QMessageBox.warning(self, "Export Error", "Please select a specific Team to export.")
            return
            
        cat = self.combo_cat.currentText()
        matching_builds = [b for b in self.engine.builds if b.team == team_name]
        if cat != "All":
            matching_builds = [b for b in matching_builds if b.category == cat]
            
        if not matching_builds:
            QMessageBox.information(self, "Export", "No builds found to export.")
            return

        unique_builds = []
        seen_codes = set()
        for b in matching_builds:
            if b.code not in seen_codes:
                unique_builds.append(b)
                seen_codes.add(b.code)
        
        saved_count = 0
        for b in unique_builds:
            p1_id = int(b.primary_prof) if b.primary_prof.isdigit() else 0
            p2_id = int(b.secondary_prof) if b.secondary_prof.isdigit() else 0
            
            p1_name = PROF_MAP.get(p1_id, "No Profession")
            p2_name = PROF_MAP.get(p2_id, "No Profession")
            p1 = PROF_SHORT_MAP.get(p1_name, "X")
            p2 = PROF_SHORT_MAP.get(p2_name, "X")
            
            safe_team = "".join(c for c in team_name if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"{safe_team} {p1}-{p2}.txt"
            
            full_path = os.path.join(self.template_path, filename)
            
            counter = 1
            base_filename = filename
            while os.path.exists(full_path):
                name_part, ext = os.path.splitext(base_filename)
                full_path = os.path.join(self.template_path, f"{name_part} ({counter}){ext}")
                counter += 1
            
            try:
                with open(full_path, 'w') as f:
                    f.write(b.code)
                saved_count += 1
            except Exception as e:
                print(f"Error saving {filename}: {e}")
        
        QMessageBox.information(self, "Export Complete", f"Successfully exported {saved_count} builds to\n{self.template_path}")

    def copy_code(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.edit_code.text())

    def load_code(self, code_str=None):
        if not code_str:
            code = self.edit_code.text().strip()
        else:
            code = code_str.strip()
            self.edit_code.setText(code) 
            
        if not code:
            return

        decoder = GuildWarsTemplateDecoder(code)
        build_data = decoder.decode()
        
        if not build_data or "error" in build_data:
            print("Failed to decode build code.")
            return

        primary_prof_id = build_data.get("profession", {}).get("primary", 0)
        if primary_prof_id != 0:
            for i in range(self.combo_prof.count()):
                text = self.combo_prof.itemText(i)
                if text.startswith(f"{primary_prof_id} -"):
                    self.combo_prof.setCurrentIndex(i)
                    break
        
        skills = build_data.get("skills", [])
        if len(skills) < 8:
            skills.extend([0] * (8 - len(skills)))
        skills = skills[:8]
        
        is_pvp = self.check_pvp.isChecked()
        
        for i, skill_id in enumerate(skills):
            if skill_id == 0:
                self.bar_skills[i] = None
                self.slots[i].clear_slot(silent=True)
            else:
                self.bar_skills[i] = skill_id
                skill_obj = self.repo.get_skill(skill_id, is_pvp=is_pvp)
                self.slots[i].set_skill(skill_id, skill_obj, ghost=False)

        self.update_suggestions()

    def toggle_elites(self, checked):
        if checked:
            self.check_no_elites.blockSignals(True)
            self.check_no_elites.setChecked(False)
            self.check_no_elites.blockSignals(False)
        self.apply_filters()

    def toggle_no_elites(self, checked):
        if checked:
            self.check_elites_only.blockSignals(True)
            self.check_elites_only.setChecked(False)
            self.check_elites_only.blockSignals(False)
        self.apply_filters()

    def handle_skill_clicked(self, skill: Skill):
        self.current_selected_skill_id = skill.id
        dist = self.attr_editor.get_distribution()
        rank = dist.get(skill.attribute, 0)
        self.info_panel.update_info(skill, rank=rank)

    def apply_filters(self):
        # Debounce filter changes
        self.filter_debounce_timer.start(250)

    def _run_filter(self):
        # Stop any active filtering to prevent crashes
        if hasattr(self, 'filter_worker') and self.filter_worker.isRunning():
            self.filter_worker.requestInterruption()
            self.filter_worker.wait()

        # [REMOVED] self.lbl_loading.show() <- This was causing the potential next crash

        prof_str = self.combo_prof.currentText()
        if prof_str == "All": prof = "All"
        else: prof = prof_str.split(' ')[0]

        cat = self.combo_cat.currentText()
        team = self.combo_team.currentText()

        # Gather filters
        filters = {
            'prof': prof,
            'cat': cat,
            'team': team,
            'search_text': self.edit_search.text().lower(),
            'is_pvp': self.check_pvp.isChecked(),
            'is_pve_only': self.check_pve_only.isChecked(),
            'is_elites_only': self.check_elites_only.isChecked(),
            'is_no_elites': self.check_no_elites.isChecked(),
            'is_pre_only': self.check_pre.isChecked() if hasattr(self, 'check_pre') else False
        }

        self.filter_worker = FilterWorker(DB_FILE, self.engine, filters)
        self.filter_worker.finished.connect(self._on_filter_finished)
        self.filter_worker.start()

    def _on_filter_finished(self, filtered_skills):
        self.library_widget.clear()
        
        # [REMOVED] self.lbl_loading.hide() <- This was causing your specific crash
        
        # Turn off updates briefly for insertion speed
        self.library_widget.setUpdatesEnabled(False)
        
        for skill in filtered_skills:
            item = QListWidgetItem(skill.name)
            item.setData(Qt.ItemDataRole.UserRole, skill.id)
            item.setData(Qt.ItemDataRole.DisplayRole, skill.name) # Explicitly set display role for delegate
            
            # Icon Loading
            cache_key = skill.icon_filename
            pix = None
            
            if cache_key in PIXMAP_CACHE:
                pix = PIXMAP_CACHE[cache_key]
            else:
                path = os.path.join(ICON_DIR, skill.icon_filename)
                if os.path.exists(path):
                    pix = QPixmap(path)
                    # Cache standard size
                    pix = pix.scaled(ICON_SIZE, ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
                    PIXMAP_CACHE[cache_key] = pix
            
            if pix:
                item.setIcon(QIcon(pix))
                item.setData(Qt.ItemDataRole.DecorationRole, QIcon(pix)) # Ensure delegate gets the icon
            
            self.library_widget.addItem(item)
            
        self.library_widget.setUpdatesEnabled(True)

    def handle_skill_equipped_auto(self, skill_id):
        # Find first empty slot
        empty_index = -1
        for i, s_id in enumerate(self.bar_skills):
            if s_id is None:
                empty_index = i
                break
        
        if empty_index != -1:
            self.handle_skill_equipped(empty_index, skill_id)           

    def handle_skill_id_clicked(self, skill_id):
        self.current_selected_skill_id = skill_id
        is_pvp = self.check_pvp.isChecked()
        skill = self.repo.get_skill(skill_id, is_pvp=is_pvp)
        if skill:
            dist = self.attr_editor.get_distribution()
            rank = dist.get(skill.attribute, 0)
            self.info_panel.update_info(skill, rank=rank)

    def handle_skill_equipped(self, index, skill_id):
        self.bar_skills[index] = skill_id
        self.suggestion_offset = 0 
        
        is_pvp = self.check_pvp.isChecked()
        skill_obj = self.repo.get_skill(skill_id, is_pvp=is_pvp)
        
        dist = self.attr_editor.get_distribution()
        rank = dist.get(skill_obj.attribute, 0) if skill_obj else 0
        
        self.slots[index].set_skill(skill_id, skill_obj, ghost=False, rank=rank)
        
        self.update_suggestions()

    def handle_skill_removed(self, index):
        self.bar_skills[index] = None
        self.suggestion_offset = 0 
        self.update_suggestions()
        
    def refresh_equipped_skills(self):
        is_pvp = self.check_pvp.isChecked()
        dist = self.attr_editor.get_distribution()
        for i, sid in enumerate(self.bar_skills):
            if sid is not None:
                skill_obj = self.repo.get_skill(sid, is_pvp=is_pvp)
                rank = dist.get(skill_obj.attribute, 0) if skill_obj else 0
                self.slots[i].set_skill(sid, skill_obj, ghost=False, rank=rank)
        self.update_suggestions()

    def cycle_suggestions(self):
        empty_slots = sum(1 for s in self.bar_skills if s is None)
        if empty_slots == 0: 
            print("Cycle: No empty slots.")
            return

        if self.current_suggestions:
            old_offset = self.suggestion_offset
            # Shift offset by number of visible slots
            self.suggestion_offset = (self.suggestion_offset + empty_slots) % len(self.current_suggestions)
            print(f"Cycling: Offset {old_offset} -> {self.suggestion_offset} (Total: {len(self.current_suggestions)})")
            self.display_suggestions()
        else:
            print("Cycle: No suggestions to cycle.")

    def on_synergies_loaded(self, suggestions):
        self.current_suggestions = []
        is_pvp = self.check_pvp.isChecked()
        show_others = self.check_show_others.isChecked()
        
        active_ids = [sid for sid in self.bar_skills if sid is not None]
        profs_in_bar = set()
        for sid in active_ids:
            if sid != 0:
                s = self.repo.get_skill(sid, is_pvp=is_pvp)
                if s and s.profession != 0:
                    profs_in_bar.add(s.profession)
        
        allowed_profs = set()
        enforce_prof_limit = False
        
        if not show_others:
            if len(profs_in_bar) >= 2:
                enforce_prof_limit = True
                allowed_profs.update(profs_in_bar)
                allowed_profs.add(0)

        # Prepare team spirit set for fast lookup
        team_spirit_ids = set()
        if hasattr(self, 'check_smart_mode') and self.check_smart_mode.isChecked():
            # Find which IDs in team synergy context are spirits
            # We can do this once per batch or just check in the loop
            pass

        for sid, conf in suggestions:
            skill = self.repo.get_skill(sid, is_pvp=is_pvp)
            if not skill: continue
            
            if is_pvp and skill.is_pve_only: continue
            
            if enforce_prof_limit:
                if skill.profession not in allowed_profs:
                    continue
            
            # --- SPIRIT REDUNDANCY EXCEPTION ---
            # If in Smart Mode with a team context, don't suggest spirits already in that context
            if hasattr(self, 'check_smart_mode') and self.check_smart_mode.isChecked():
                if sid in self.team_synergy_skills:
                    # Check if it's a spirit
                    # We can use the tag map logic or just check the description
                    # Since we standardized tags, let's query the DB for this skill's tags if not already cached
                    # Or simpler: check if "Type_Spirit" is in its stats (if we had tags in Skill class)
                    # We'll do a quick check against the skill_tags table
                    cursor = self.repo.conn.cursor()
                    cursor.execute("SELECT 1 FROM skill_tags WHERE skill_id=? AND tag='Type_Spirit'", (sid,))
                    if cursor.fetchone():
                        continue # Skip duplicate spirit

            self.current_suggestions.append((sid, conf))

        self.suggestion_offset = 0
        self.display_suggestions()

    def update_suggestions(self):
        # Prevent updates if "Lock" is checked
        if hasattr(self, 'check_lock_suggestions') and self.check_lock_suggestions.isChecked():
            return
            
        # Clean up existing thread if running
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            
        active_ids = [sid for sid in self.bar_skills if sid is not None]
        
        if hasattr(self, 'check_smart_mode') and self.check_smart_mode.isChecked():
            # In Smart Mode, include the loaded team context if available
            # Filter duplicates between bar and team
            bar_set = set(active_ids)
            for sid in self.team_synergy_skills:
                if sid not in bar_set:
                    active_ids.append(sid)

        # Get Profession ID
        prof_text = self.combo_prof.currentText()
        try:
            pid = int(prof_text.split(' ')[0])
        except:
            pid = 0

        is_debug = False

        if hasattr(self, 'check_smart_mode') and self.check_smart_mode.isChecked():
            mode = "smart"
            engine = self.smart_engine
        else:
            mode = "legacy"
            engine = self.engine

        self.worker = SynergyWorker(engine, active_ids, pid, mode, debug=is_debug)
        self.worker.results_ready.connect(self.on_synergies_loaded)
        self.worker.start()

    def display_suggestions(self):
        empty_indices = [i for i, s in enumerate(self.bar_skills) if s is None]
        
        display_list = []
        is_pvp = self.check_pvp.isChecked()

        if self.current_suggestions:
            total_suggestions = len(self.current_suggestions)
            needed = len(empty_indices)
            
            # LOGIC FIX: Do not wrap around. Stop if we run out of unique items.
            # We take a slice of the list starting at the offset.
            # If the offset + needed exceeds the list, we just take what's left.
            
            for i in range(needed):
                idx = self.suggestion_offset + i
                if idx < total_suggestions:
                    display_list.append(self.current_suggestions[idx])
                else:
                    # We ran out of suggestions to show. Stop filling.
                    break
        
        s_idx = 0
        dist = self.attr_editor.get_distribution()
        for slot_idx in empty_indices:
            slot = self.slots[slot_idx]
            
            if s_idx < len(display_list):
                # Fill slot with suggestion
                s_id, conf = display_list[s_idx]
                skill_obj = self.repo.get_skill(s_id, is_pvp=is_pvp)
                rank = dist.get(skill_obj.attribute, 0) if skill_obj else 0
                slot.set_skill(s_id, skill_obj, ghost=True, confidence=conf, rank=rank)
                s_idx += 1
            else:
                # Ran out of suggestions? Clear the slot.
                slot.clear_slot(silent=True)
                
        self.update_build_code()

    def on_attributes_changed(self, distribution):
        self.update_build_code()
        # Phase 3: Refresh skill tooltips/displays
        self.refresh_skill_displays()

    def refresh_skill_displays(self):
        is_pvp = self.check_pvp.isChecked()
        dist = self.attr_editor.get_distribution()
        
        # Refresh equipped skills
        for i, sid in enumerate(self.bar_skills):
            if sid is not None:
                skill_obj = self.repo.get_skill(sid, is_pvp=is_pvp)
                rank = dist.get(skill_obj.attribute, 0) if skill_obj else 0
                self.slots[i].set_skill(sid, skill_obj, ghost=False, rank=rank)
                
        # Refresh info panel
        if self.current_selected_skill_id is not None:
            skill_obj = self.repo.get_skill(self.current_selected_skill_id, is_pvp=is_pvp)
            if skill_obj:
                rank = dist.get(skill_obj.attribute, 0)
                self.info_panel.update_info(skill_obj, rank=rank)

        # Refresh suggestions (this will call display_suggestions)
        self.display_suggestions()

    def swap_professions(self):
        self.is_swapped = not self.is_swapped
        self.update_build_code()

    def update_build_code(self):
        active_bar = [s if s is not None else 0 for s in self.bar_skills]
        
        profs_in_bar = set()
        for sid in active_bar:
            if sid != 0:
                s = self.repo.get_skill(sid)
                if s and s.profession != 0:
                    profs_in_bar.add(s.profession)
        
        primary_id = 0
        secondary_id = 0
        
        try: 
            combo_val = int(self.combo_prof.currentText().split(' ')[0])
            if combo_val != 0:
                primary_id = combo_val
        except: pass
        
        profs_sorted = sorted(list(profs_in_bar))
        
        if primary_id == 0:
            if len(profs_sorted) >= 1: primary_id = profs_sorted[0]
        
        for pid in profs_sorted:
            if pid != primary_id:
                secondary_id = pid
                break
        
        if self.is_swapped:
            primary_id, secondary_id = secondary_id, primary_id
            
        p1_name = PROF_MAP.get(primary_id, "No Profession")
        p2_name = PROF_MAP.get(secondary_id, "No Profession")
        p1_str = PROF_SHORT_MAP.get(p1_name, "X")
        p2_str = PROF_SHORT_MAP.get(p2_name, "X")
        
        self.lbl_prof_display.setText(f"{p1_str}/{p2_str}")
        
        # Collect active skill objects for PvE attribute detection
        active_skill_objs = []
        for sid in active_bar:
            if sid != 0:
                s = self.repo.get_skill(sid)
                if s: active_skill_objs.append(s)

        # Update Attribute Editor professions
        # We also pass active_skill_objs now so it can detect PvE attributes
        # We force update if the skill bar content implies different attributes
        # (The simple check _last_profs != ... is insufficient for dynamic PvE attributes)
        
        # Simplified change detection: just call it. Optimization can happen if needed.
        self.attr_editor.set_professions(primary_id, secondary_id, active_skill_objs)
        self._last_profs = (primary_id, secondary_id)

        # Get actual ranks from editor for the build code
        dist = self.attr_editor.get_distribution()
        attributes = []
        for aid, rank in dist.items():
            if rank > 0:
                attributes.append([aid, rank])

        data = {
            "header": {"type": 14, "version": 0},
            "profession": {"primary": primary_id, "secondary": secondary_id},
            "attributes": attributes,
            "skills": active_bar
        }
        
        try:
            live_code = GuildWarsTemplateEncoder(data).encode()
            self.edit_code.setText(live_code)
        except:
            pass

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                path = urls[0].toLocalFile()
                if os.path.isdir(path):
                    event.accept()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            folder_path = urls[0].toLocalFile()
            self.process_folder_drop(folder_path)

    def select_folder_for_team(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Team Build Folder")
        if folder_path:
            self.process_folder_drop(folder_path)

    def process_folder_drop(self, folder_path):
        team_name = os.path.basename(folder_path)
        if not team_name: return
        
        added_count = 0
        
        # Iterate files
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".txt"):
                file_path = os.path.join(folder_path, filename)
                try:
                    with open(file_path, 'r') as f:
                        code = f.read().strip()
                        
                    # Validate Code
                    decoder = GuildWarsTemplateDecoder(code)
                    decoded = decoder.decode()
                    if decoded:
                        entry = {
                            "build_code": code,
                            "primary_profession": str(decoded['profession']['primary']),
                            "secondary_profession": str(decoded['profession']['secondary']),
                            "skill_ids": decoded['skills'],
                            "category": "User Imported",
                            "team": team_name
                        }
                        
                        # Add to Engine
                        # Check duplicates?
                        exists = False
                        for b in self.engine.builds:
                            if b.code == code and b.team == team_name:
                                exists = True
                                break
                        
                        if not exists:
                            self.engine.builds.append(Build(
                                code=entry['build_code'],
                                primary_prof=entry['primary_profession'],
                                secondary_prof=entry['secondary_profession'],
                                skill_ids=entry['skill_ids'],
                                category=entry['category'],
                                team=entry['team']
                            ))
                            
                            # Persist
                            # Access the dialog helper? No, just replicate save logic or make helper static.
                            # I'll just append to JSON here manually or use a helper if available.
                            # Ideally I should have a shared DataManager.
                            # For now, I'll inline the save.
                            if os.path.exists(JSON_FILE):
                                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                            else:
                                data = []
                            
                            data.append(entry)
                            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=4)
                                
                            added_count += 1
                            
                except Exception as e:
                    print(f"Error processing {filename}: {e}")

        if added_count > 0:
            self.engine.teams.add(team_name)
            self.update_team_dropdown()
            # Select the new team
            idx = self.combo_team.findText(team_name)
            if idx != -1: self.combo_team.setCurrentIndex(idx)
            QMessageBox.information(self, "Team Added", f"Added {added_count} builds to team '{team_name}'.")
        else:
            QMessageBox.warning(self, "No Builds Found", "Could not find valid build codes in the selected folder.")

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
        event.accept()

# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())