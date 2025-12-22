import sys
import os
import json
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Dict, Set
from collections import Counter
import math

# GUI Imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QComboBox, QLabel, QScrollArea, 
    QFrame, QGridLayout, QLineEdit, QSplitter, 
    QTabWidget, QCheckBox, QPushButton, QSizePolicy,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QMimeData, QSize, pyqtSignal, QPoint, QUrl
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont, QAction

# Attempt to import WebEngine for the Map Tab
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

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

DB_FILE = resource_path('skills2.db')
JSON_FILE = resource_path('all_skills.json')
ICON_DIR = resource_path('icons/skill_icons')  # Folder containing {id}.png images
ICON_SIZE = 64

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

# Mapping of Profession ID to its primary attribute ID for the 11 points logic
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

    def get_profession_str(self):
        return PROF_MAP.get(self.profession, f"Unknown ({self.profession})")

    def get_attribute_str(self):
        if self.attribute == -1: return "None"
        return ATTR_MAP.get(self.attribute, f"Unknown ({self.attribute})")

@dataclass
class Build:
    code: str
    primary_prof: str
    secondary_prof: str
    skill_ids: List[int]
    category: str
    team: str
    attributes: List[List[int]] = None # List of [id, points]

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
        
        table = "skills_pvp" if is_pvp else "skills"
        
        try:
            self.cursor.execute(f"""
                SELECT name, id, profession,
                       description, attribute, energy, activation,
                       recharge, adrenaline, is_elite, is_pve_only
                FROM {table}
                WHERE id=?
            """, (skill_id,))
            row = self.cursor.fetchone()
            if row:
                # Ensure the icon filename has .jpg extension
                # In DB, icon was stored in skills_index, but we can assume {id}.jpg
                icon_val = f"{skill_id}.jpg"
                
                # Safely handle potential None values for integers
                prof_val = row[2] if row[2] is not None else 0
                attr_val = row[4] if row[4] is not None else -1
                elite_val = int(row[9]) if row[9] is not None else 0
                pve_val = int(row[10]) if row[10] is not None else 0
                
                skill = Skill(
                    id=skill_id, 
                    name=row[0], 
                    icon_filename=icon_val, 
                    profession=prof_val,
                    description=row[3] or "",
                    attribute=attr_val,
                    energy=row[5] or 0,
                    activation=row[6] or 0.0,
                    recharge=row[7] or 0.0,
                    adrenaline=row[8] or 0,
                    is_elite=(elite_val == 1), # Strict check for 1
                    is_pve_only=bool(pve_val)
                )
                self._cache[cache_key] = skill
                return skill
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        return None

    def get_all_skills_by_ids(self, ids: List[int], is_pvp: bool = False) -> List[Skill]:
        skills = []
        for sid in ids:
            s = self.get_skill(sid, is_pvp=is_pvp)
            if s:
                skills.append(s)
        return skills

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
                    # Decode to get accurate attributes and professions if possible
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
        # Pre-filter builds based on category and team
        candidate_builds = self.builds
        if category and category != "All":
            candidate_builds = [b for b in candidate_builds if b.category == category]
        if team and team != "All":
            candidate_builds = [b for b in candidate_builds if b.team == team]

        # Modified Logic: "Relaxed Matching"
        # If we have < 2 active skills, just match builds containing ANY of them.
        # If we have >= 2 active skills, match builds containing AT LEAST 2 of them.
        # min_overlap override: allows forcing a lower threshold (e.g. 1) to broaden search.
        
        active_set = set(active_skill_ids)
        if not active_set:
            matching_builds = candidate_builds
        else:
            # Determine threshold
            threshold = 1
            if min_overlap is not None:
                threshold = min_overlap
            elif len(active_set) >= 2:
                threshold = 2
            
            if threshold == 1:
                 # Fast path for intersection >= 1
                 matching_builds = [b for b in candidate_builds if not active_set.isdisjoint(set(b.skill_ids))]
            else:
                 # Match if at least 'threshold' shared skills
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
        """Returns a set of Skill IDs appearing in builds matching the filters"""
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

class DraggableSkillIcon(QFrame):
    clicked = pyqtSignal(Skill)
    double_clicked = pyqtSignal(Skill)

    def __init__(self, skill: Skill, parent=None):
        super().__init__(parent)
        self.skill = skill
        self.setFixedSize(ICON_SIZE + 10, ICON_SIZE + 60) # Increased height for text
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #444; 
                background-color: #222; 
                border-radius: 4px;
            }
            QFrame:hover {
                border: 1px solid #666;
                background-color: #333;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Icon Label
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self.icon_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Name Label
        self.name_lbl = QLabel(skill.name)
        self.name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_lbl.setWordWrap(True)
        self.name_lbl.setStyleSheet("border: none; background: transparent; color: #EEE; font-size: 10px;")
        layout.addWidget(self.name_lbl)
        
        self.load_icon()

    def load_icon(self):
        path = os.path.join(ICON_DIR, self.skill.icon_filename)
        if os.path.exists(path):
            pix = QPixmap(path)
            self.icon_lbl.setPixmap(pix.scaled(ICON_SIZE, ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            # Fallback: Generate an icon with text
            pix = QPixmap(ICON_SIZE, ICON_SIZE)
            pix.fill(QColor("#333"))
            painter = QPainter(pix)
            painter.setPen(Qt.GlobalColor.white)
            font = QFont("Arial", 8)
            painter.setFont(font)
            painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.skill.name)
            painter.end()
            self.icon_lbl.setPixmap(pix)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.skill)
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(str(self.skill.id))
            drag.setMimeData(mime_data)
            drag.setPixmap(self.icon_lbl.pixmap()) # Drag the icon image
            drag.setHotSpot(event.position().toPoint())
            drag.exec(Qt.DropAction.CopyAction)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.skill)

class SkillSlot(QFrame):
    skill_equipped = pyqtSignal(int, int) # slot_index, skill_id
    skill_removed = pyqtSignal(int)       # slot_index
    clicked = pyqtSignal(int)             # skill_id

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
        
        # Label to hold the image
        self.icon_label = QLabel(self)
        self.icon_label.setGeometry(2, 2, ICON_SIZE, ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Let drops pass through label

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
        # The main window will handle the actual logic via the signal
        # but we need to emit it here.
        self.skill_equipped.emit(self.index, skill_id)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_skill_id is not None:
                self.clicked.emit(self.current_skill_id)
        # Right click to remove
        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_skill_id is not None:
                self.clear_slot()

    def mouseDoubleClickEvent(self, event):
        # Double click behavior:
        # If ghost (suggestion): Confirm it (equip it)
        # If solid (equipped): Remove it
        if self.current_skill_id is not None:
            if self.is_ghost:
                self.skill_equipped.emit(self.index, self.current_skill_id)
            else:
                self.clear_slot()

    def set_skill(self, skill_id, skill_obj: Skill = None, ghost=False, confidence=0.0):
        self.current_skill_id = skill_id
        self.is_ghost = ghost
        
        # Visuals
        icon_file = skill_obj.icon_filename if skill_obj else f"{skill_id}.jpg"
        if not icon_file.lower().endswith('.jpg'):
            icon_file += '.jpg'
            
        path = os.path.join(ICON_DIR, icon_file)
        
        pix = QPixmap()
        if os.path.exists(path):
            pix.load(path)
        else:
            # Fallback text gen
            pix = QPixmap(ICON_SIZE, ICON_SIZE)
            pix.fill(QColor("#333"))
            p = QPainter(pix)
            p.setPen(Qt.GlobalColor.white)
            p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, skill_obj.name if skill_obj else str(skill_id))
            p.end()

        if ghost:
            # Make semi-transparent
            transparent_pix = QPixmap(pix.size())
            transparent_pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(transparent_pix)
            p.setOpacity(0.4)
            p.drawPixmap(0, 0, pix)
            p.end()
            self.icon_label.setPixmap(transparent_pix)
            self.setToolTip(f"Suggestion: {skill_obj.name}\nSynergy: {confidence:.0%}")
        else:
            self.icon_label.setPixmap(pix)
            self.setToolTip(skill_obj.name if skill_obj else "")

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
        self.setFixedWidth(250)
        self.setStyleSheet("background-color: #1a1a1a; border-left: 1px solid #444;")
        layout = QVBoxLayout(self)
        
        self.lbl_name = QLabel("Select a skill")
        self.lbl_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #00AAFF;")
        self.lbl_name.setWordWrap(True)
        
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(64, 64)
        self.lbl_icon.setStyleSheet("border: 1px solid #444;")
        
        self.txt_desc = QLabel("")
        self.txt_desc.setWordWrap(True)
        self.txt_desc.setStyleSheet("color: #ccc; font-style: italic;")
        
        self.details = QLabel("")
        self.details.setStyleSheet("color: #aaa;")
        
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.txt_desc)
        layout.addWidget(self.details)
        layout.addStretch()

    def update_info(self, skill: Skill):
        self.lbl_name.setText(skill.name)
        
        path = os.path.join(ICON_DIR, skill.icon_filename)
        if os.path.exists(path):
            self.lbl_icon.setPixmap(QPixmap(path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.lbl_icon.clear()
            
        self.txt_desc.setText(skill.description)
        
        info = []
        info.append(f"Profession: {skill.get_profession_str()}")
        info.append(f"Attribute: {skill.get_attribute_str()}")
        if skill.energy: info.append(f"Energy: {skill.energy}")
        if skill.activation: info.append(f"Activation: {skill.activation}s")
        if skill.recharge: info.append(f"Recharge: {skill.recharge}s")
        if skill.adrenaline: info.append(f"Adrenaline: {skill.adrenaline}")
        if skill.is_elite: info.append("<b>Elite Skill</b>")
        if skill.is_pve_only: info.append("<i>PvE Only</i>")
        
        self.details.setText("<br>".join(info))

class BuildPreviewWidget(QFrame):
    clicked = pyqtSignal(str) # Emits build code (Load)
    skill_clicked = pyqtSignal(Skill) # Emits skill for info panel

    def __init__(self, build: Build, repo: SkillRepository, is_pvp=False, parent=None):
        super().__init__(parent)
        self.build = build
        self.repo = repo
        self.setFixedHeight(ICON_SIZE + 80) # Adjusted height
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
        
        # Display Professions
        p1_name = PROF_MAP.get(int(build.primary_prof) if build.primary_prof.isdigit() else 0, "No Profession")
        p2_name = PROF_MAP.get(int(build.secondary_prof) if build.secondary_prof.isdigit() else 0, "No Profession")
        p1 = PROF_SHORT_MAP.get(p1_name, "X")
        p2 = PROF_SHORT_MAP.get(p2_name, "X")
        
        lbl_prof = QLabel(f"{p1}/{p2}")
        lbl_prof.setStyleSheet("color: #AAA; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        lbl_prof.setFixedWidth(50)
        lbl_prof.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_prof)
        
        # Display 8 Skills
        for sid in build.skill_ids:
            skill_widget = None
            if sid != 0:
                skill = repo.get_skill(sid, is_pvp=is_pvp)
                if skill:
                    # Reuse DraggableSkillIcon
                    skill_widget = DraggableSkillIcon(skill)
                    # Reset style to avoid double borders
                    skill_widget.setStyleSheet("background: transparent; border: none;")
                    # Connect click for preview
                    skill_widget.clicked.connect(self.skill_clicked.emit)
            
            if skill_widget:
                layout.addWidget(skill_widget)
            else:
                # Placeholder
                placeholder = QFrame()
                placeholder.setFixedSize(ICON_SIZE + 10, ICON_SIZE + 60)
                placeholder.setStyleSheet("background: transparent; border: 1px dashed #444;")
                layout.addWidget(placeholder)
            
        layout.addStretch()
        
        # Load Button
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guild Wars Synergy Builder")
        self.resize(1200, 800)
        
        # Load Data
        self.repo = SkillRepository(DB_FILE)
        self.engine = SynergyEngine(JSON_FILE)
        
        # State
        self.bar_skills = [None] * 8 # Array of skill_ids or None
        self.suggestion_offset = 0
        self.current_suggestions = [] # Store filtered list for cycling
        self.is_swapped = False # Track if primary/secondary are swapped
        self.template_path = "" # Start empty to force selection
        
        self.init_ui()
        self.apply_filters() # Initial population

    def init_ui(self):
        # Create Tab Widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- Tab 1: Builder ---
        self.builder_tab = QWidget()
        self.tabs.addTab(self.builder_tab, "Builder")
        
        # Initialize builder UI on the builder_tab
        self.init_builder_ui(self.builder_tab)

        # --- Tab 2: Synergy Map ---
        self.map_tab = QWidget()
        self.tabs.addTab(self.map_tab, "Synergy Map")
        self.init_map_ui(self.map_tab)

    def init_map_ui(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        if HAS_WEBENGINE:
            try:
                view = QWebEngineView()
                # Load local file
                file_path = resource_path("synergy_map.html")
                view.load(QUrl.fromLocalFile(file_path))
                layout.addWidget(view)
            except Exception as e:
                layout.addWidget(QLabel(f"Error loading map: {e}"))
        else:
            layout.addWidget(QLabel("PyQt6-WebEngine is not installed. Please install it to view the map.\n\npip install PyQt6-WebEngine"))

    def update_team_dropdown(self):
        selected_cat = self.combo_cat.currentText()
        current_team = self.combo_team.currentText()
        
        # Collect valid teams
        valid_teams = set()
        if selected_cat == "All":
            valid_teams = self.engine.teams
        else:
            for b in self.engine.builds:
                if b.category == selected_cat:
                    valid_teams.add(b.team)
        
        # Update Dropdown
        self.combo_team.blockSignals(True) # Prevent triggering apply_filters multiple times
        self.combo_team.clear()
        self.combo_team.addItem("All")
        self.combo_team.addItems(sorted(list(valid_teams)))
        
        # Restore selection if possible, otherwise default to All
        index = self.combo_team.findText(current_team)
        if index != -1:
            self.combo_team.setCurrentIndex(index)
        else:
            self.combo_team.setCurrentIndex(0)
            
        self.combo_team.blockSignals(False)
        
        # Refresh grid
        self.apply_filters()

    def init_builder_ui(self, parent_widget):
        main_layout = QVBoxLayout(parent_widget)

        # --- 1. Top Filters ---
        filter_layout = QHBoxLayout()
        
        self.combo_prof = QComboBox()
        self.combo_prof.addItem("All")
        # Use PROF_MAP for display
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
        filter_layout.addWidget(QLabel("Team:"))
        filter_layout.addWidget(self.combo_team)
        
        # Add PvP Checkbox
        filter_layout.addSpacing(20)
        self.check_pvp = QCheckBox("PvP?")
        # When checked: Filter OUT PvE-only skills
        # When unchecked: Show everything (PvE Mode)
        self.check_pvp.toggled.connect(self.apply_filters)
        self.check_pvp.toggled.connect(self.update_suggestions)
        self.check_pvp.toggled.connect(self.refresh_equipped_skills)
        filter_layout.addWidget(self.check_pvp)

        # Add Elites Filters
        filter_layout.addSpacing(20)
        self.check_elites_only = QCheckBox("Elites")
        self.check_no_elites = QCheckBox("No Elites")
        
        self.check_elites_only.toggled.connect(self.toggle_elites)
        self.check_no_elites.toggled.connect(self.toggle_no_elites)
        
        filter_layout.addWidget(self.check_elites_only)
        filter_layout.addWidget(self.check_no_elites)

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
        
        self.btn_export_team = QPushButton("Export Team Builds")
        self.btn_export_team.clicked.connect(self.export_team_builds)
        self.btn_export_team.setToolTip("Export the currently displayed team builds to individual .txt files.")
        export_layout.addWidget(self.btn_export_team)
        
        main_layout.addLayout(export_layout)

        # --- 2. Center Splitter (Grid + Info) ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Skill Browser (Left)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.skill_grid_widget = QWidget()
        self.skill_grid_layout = QGridLayout(self.skill_grid_widget)
        self.skill_grid_layout.setHorizontalSpacing(20) # Increased spacing
        self.skill_grid_layout.setVerticalSpacing(10)
        # AlignTop is fine, remove AlignLeft to allow full width expansion
        self.skill_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.skill_grid_widget)
        
        self.splitter.addWidget(self.scroll_area)
        
        # Info Panel (Right)
        self.info_panel = SkillInfoPanel()
        self.splitter.addWidget(self.info_panel)
        
        main_layout.addWidget(self.splitter, stretch=1)

        # --- 3. Build Bar (Bottom) ---
        bar_container = QFrame()
        bar_container.setFixedHeight(120)
        bar_container.setStyleSheet("background-color: #111; border-top: 1px solid #444;")
        container_layout = QHBoxLayout(bar_container)

        # Cycle Button (Left of skills)
        self.btn_cycle = QPushButton("Cycle\nSuggestions")
        self.btn_cycle.setFixedSize(80, 60)
        self.btn_cycle.clicked.connect(self.cycle_suggestions)
        container_layout.addWidget(self.btn_cycle)

        # Left/Center: The Skills
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
            
        container_layout.addStretch(1)
        container_layout.addLayout(bar_layout)
        container_layout.addSpacing(20) # Spacing
        
        # Show Other Professions (Moved here)
        self.check_show_others = QCheckBox("Show Other\nProfessions")
        self.check_show_others.setToolTip("If checked, suggest skills from ALL professions.\nIf unchecked, strictly limits suggestions to the current Primary/Secondary professions.")
        self.check_show_others.toggled.connect(self.update_suggestions)
        container_layout.addWidget(self.check_show_others)
        
        container_layout.addStretch(1)

        # Right: Build Code Section
        code_box = QFrame()
        code_box.setFixedWidth(250)
        code_layout = QVBoxLayout(code_box)
        
        # Header Row: "Build Code: [W/Mo] [Swap]"
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
        
        self.btn_import = QPushButton("Import to DB")
        self.btn_import.setStyleSheet("background-color: #225522;")
        self.btn_import.clicked.connect(self.import_build_to_db)
        btn_layout.addWidget(self.btn_import)
        
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setStyleSheet("background-color: #552222;")
        self.btn_reset.clicked.connect(self.reset_build)
        btn_layout.addWidget(self.btn_reset)
        
        code_layout.addLayout(btn_layout)
        
        container_layout.addWidget(code_box)
        main_layout.addWidget(bar_container)

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
            
        # Construct Entry
        entry = {
            "build_code": code,
            "primary_profession": str(decoded['profession']['primary']),
            "secondary_profession": str(decoded['profession']['secondary']),
            "skill_ids": decoded['skills'],
            "category": "User Imported",
            "team": "User Imported"
        }
        
        # Save to JSON
        try:
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []
                
            # Check for duplicate
            if any(d.get('build_code') == code for d in data):
                QMessageBox.information(self, "Import", "This build is already in the database.")
                return
                
            data.append(entry)
            
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
                
            # Reload Engine
            self.engine = SynergyEngine(JSON_FILE)
            self.apply_filters()
            self.update_team_dropdown() # Refresh team list in case "User Imported" is new
            
            QMessageBox.information(self, "Success", "Build successfully imported into the synergy database!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save build: {e}")

    def reset_build(self):
        # 1. Reset State
        self.bar_skills = [None] * 8
        self.suggestion_offset = 0
        self.is_swapped = False
        
        # 2. Reset UI Controls
        self.combo_prof.setCurrentIndex(0) # All
        self.combo_cat.setCurrentIndex(0) # All
        self.combo_team.setCurrentIndex(0) # All
        self.check_pvp.setChecked(False)
        self.check_show_others.setChecked(False)
        self.edit_search.clear()
        self.edit_code.clear()
        
        # 3. Clear Slots
        for slot in self.slots:
            slot.clear_slot(silent=True)
            
        # 4. Refresh
        self.apply_filters()
        self.update_suggestions()

    def choose_template_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Template Folder", self.template_path)
        if path:
            self.template_path = path
            self.lbl_path.setText(f"Path: {path}")

    def export_team_builds(self):
        # Force path selection if empty
        if not self.template_path:
            self.choose_template_path()
            if not self.template_path:
                return # Abort if user still didn't select
                
        team_name = self.combo_team.currentText()
        if team_name == "All":
            QMessageBox.warning(self, "Export Error", "Please select a specific Team to export.")
            return
            
        # Identify builds to export (same logic as apply_filters)
        cat = self.combo_cat.currentText()
        matching_builds = [b for b in self.engine.builds if b.team == team_name]
        if cat != "All":
            matching_builds = [b for b in matching_builds if b.category == cat]
            
        if not matching_builds:
            QMessageBox.information(self, "Export", "No builds found to export.")
            return

        # Deduplicate
        unique_builds = []
        seen_codes = set()
        for b in matching_builds:
            if b.code not in seen_codes:
                unique_builds.append(b)
                seen_codes.add(b.code)
        
        saved_count = 0
        for b in unique_builds:
            # Generate Name: "TeamName P1-P2.txt"
            p1_id = int(b.primary_prof) if b.primary_prof.isdigit() else 0
            p2_id = int(b.secondary_prof) if b.secondary_prof.isdigit() else 0
            
            p1_name = PROF_MAP.get(p1_id, "No Profession")
            p2_name = PROF_MAP.get(p2_id, "No Profession")
            p1 = PROF_SHORT_MAP.get(p1_name, "X")
            p2 = PROF_SHORT_MAP.get(p2_name, "X")
            
            # Sanitize filename
            safe_team = "".join(c for c in team_name if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"{safe_team} {p1}-{p2}.txt"
            
            full_path = os.path.join(self.template_path, filename)
            
            # Handle collisions (e.g. two Warriors in same team)
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
            self.edit_code.setText(code) # Update UI to match
            
        if not code:
            return

        decoder = GuildWarsTemplateDecoder(code)
        build_data = decoder.decode()
        
        if not build_data or "error" in build_data:
            # Could add a status bar message here if desired
            print("Failed to decode build code.")
            return

        # 1. Update Profession
        # Try to match the primary profession ID to the ComboBox
        primary_prof_id = build_data.get("profession", {}).get("primary", 0)
        if primary_prof_id != 0:
            for i in range(self.combo_prof.count()):
                text = self.combo_prof.itemText(i)
                if text.startswith(f"{primary_prof_id} -"):
                    self.combo_prof.setCurrentIndex(i)
                    break
        
        # 2. Update Skills
        skills = build_data.get("skills", [])
        # Ensure we have exactly 8 skills (pad or trim)
        if len(skills) < 8:
            skills.extend([0] * (8 - len(skills)))
        skills = skills[:8]
        
        # Get PvP Status
        is_pvp = self.check_pvp.isChecked()
        
        for i, skill_id in enumerate(skills):
            if skill_id == 0:
                self.bar_skills[i] = None
                self.slots[i].clear_slot(silent=True)
            else:
                self.bar_skills[i] = skill_id
                skill_obj = self.repo.get_skill(skill_id, is_pvp=is_pvp)
                self.slots[i].set_skill(skill_id, skill_obj, ghost=False)

        # 3. Trigger updates (Suggestions + Code regeneration to normalize)
        self.update_suggestions()

    def handle_skill_double_clicked(self, skill: Skill):
        # Find first empty slot
        empty_index = -1
        for i, s_id in enumerate(self.bar_skills):
            if s_id is None:
                empty_index = i
                break
        
        if empty_index != -1:
            self.handle_skill_equipped(empty_index, skill.id)
        else:
            # Optional: Replace the currently selected slot or notify user?
            # For now, just ignore if full
            pass

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

    def apply_filters(self):
        prof_str = self.combo_prof.currentText()
        if prof_str == "All": prof = "All"
        else: prof = prof_str.split(' ')[0]

        cat = self.combo_cat.currentText()
        team = self.combo_team.currentText()
        
        # Clear current grid
        for i in reversed(range(self.skill_grid_layout.count())): 
            self.skill_grid_layout.itemAt(i).widget().setParent(None)

        # TEAM VIEW MODE: Show Build Bars instead of Skills
        if team != "All":
            matching_builds = [b for b in self.engine.builds if b.team == team]
            if cat != "All":
                matching_builds = [b for b in matching_builds if b.category == cat]
            
            # Deduplicate builds based on code
            unique_builds = []
            seen_codes = set()
            for b in matching_builds:
                if b.code not in seen_codes:
                    unique_builds.append(b)
                    seen_codes.add(b.code)
            
            # Use a vertical list layout style within the grid
            row = 0
            cols_wide = 8 # Match standard grid width
            for b in unique_builds:
                widget = BuildPreviewWidget(b, self.repo, is_pvp=self.check_pvp.isChecked())
                widget.clicked.connect(lambda code=b.code: self.load_code(code_str=code))
                widget.skill_clicked.connect(self.info_panel.update_info) # Connect info panel
                self.skill_grid_layout.addWidget(widget, row, 0, 1, cols_wide) # Span full width
                row += 1
            return

        # SKILL VIEW MODE (Standard)
        search_text = self.edit_search.text().lower()
        is_pvp = self.check_pvp.isChecked()
        is_elites_only = self.check_elites_only.isChecked()
        is_no_elites = self.check_no_elites.isChecked()
        
        # Get valid skill IDs from engine filters
        valid_ids = self.engine.filter_skills(prof, cat, team)
        
        # Filter by search text and Profession strictly
        filtered_skills = []
        
        # Parse prof ID once
        target_prof_id = -1
        if prof != "All":
            try:
                target_prof_id = int(prof)
            except:
                pass

        for sid in valid_ids:
            skill = self.repo.get_skill(sid, is_pvp=is_pvp)
            if skill:
                if search_text and search_text not in skill.name.lower():
                    continue
                # PvP Filter logic: If Checked, hide PvE-only skills.
                if is_pvp and skill.is_pve_only:
                    continue
                
                # Elite Filters
                if is_elites_only and not skill.is_elite:
                    continue
                if is_no_elites and skill.is_elite:
                    continue
                
                # Strict Profession Filter (Fix for "Warrior seeing Monk skills")
                if target_prof_id != -1:
                    # Allow Common (0) or strict match? Usually strict for "Warrior".
                    # Common skills are usually fine to show, but if I ask for Warrior I probably want Warrior.
                    # Let's strict match.
                    if skill.profession != target_prof_id:
                        continue
                    
                filtered_skills.append(skill)

        # Limit display count for performance
        if len(filtered_skills) > 500:
             filtered_skills = filtered_skills[:500]

        row, col = 0, 0
        cols_wide = 8 # Changed from 10 to 8
        
        # Sort by Name
        for skill in sorted(filtered_skills, key=lambda x: x.name):
            icon = DraggableSkillIcon(skill)
            icon.clicked.connect(self.info_panel.update_info)
            icon.double_clicked.connect(self.handle_skill_double_clicked)
            self.skill_grid_layout.addWidget(icon, row, col)
            col += 1
            if col >= cols_wide:
                col = 0
                row += 1

    def handle_skill_id_clicked(self, skill_id):
        is_pvp = self.check_pvp.isChecked()
        skill = self.repo.get_skill(skill_id, is_pvp=is_pvp)
        if skill:
            self.info_panel.update_info(skill)

    def handle_skill_equipped(self, index, skill_id):
        self.bar_skills[index] = skill_id
        self.suggestion_offset = 0 # Reset cycling
        
        # Fetch skill object to render solidly
        is_pvp = self.check_pvp.isChecked()
        skill_obj = self.repo.get_skill(skill_id, is_pvp=is_pvp)
        self.slots[index].set_skill(skill_id, skill_obj, ghost=False)
        
        self.update_suggestions()

    def handle_skill_removed(self, index):
        self.bar_skills[index] = None
        self.suggestion_offset = 0 # Reset cycling
        self.update_suggestions()
        
    def refresh_equipped_skills(self):
        """Reloads the equipped skills in the bar to match current PvE/PvP mode."""
        is_pvp = self.check_pvp.isChecked()
        for i, sid in enumerate(self.bar_skills):
            if sid is not None:
                skill_obj = self.repo.get_skill(sid, is_pvp=is_pvp)
                self.slots[i].set_skill(sid, skill_obj, ghost=False)
        # Also refresh suggestions as they might need to update tooltips/icons if versions differ
        self.update_suggestions()

    def cycle_suggestions(self):
        # Increment offset by the number of empty slots (or a fixed amount like 4 or 8)
        # We want to show the NEXT batch of suggestions.
        # Count empty slots
        empty_slots = sum(1 for s in self.bar_skills if s is None)
        if empty_slots == 0: return

        if self.current_suggestions:
            self.suggestion_offset = (self.suggestion_offset + empty_slots) % len(self.current_suggestions)
            self.refresh_ghosts_only()

    def refresh_ghosts_only(self):
        # Helper to just update the ghost slots without re-querying everything if we have the list
        # But for simplicity, we can just call update_suggestions logic part.
        # Actually, let's just make cycle call update_suggestions but WITHOUT resetting offset?
        # No, update_suggestions does the query.
        # Let's split logic or just re-run update_suggestions.
        # Since the query is fast (memory), re-running is fine, but we need to PERSIST the list for consistent cycling?
        # Actually, if the active skills haven't changed, the query result is deterministic.
        # So we can just re-run update_suggestions.
        # But wait, I added self.suggestion_offset reset in the handlers.
        # So cycle_suggestions just changes offset and calls update_suggestions? Yes.
        # BUT update_suggestions needs to USE the offset.
        self.display_suggestions()

    def update_suggestions(self):
        # 1. Get currently active skills (excluding None)
        active_ids = [sid for sid in self.bar_skills if sid is not None]
        
        # 2. Get suggestions from engine 
        # Deep pool search (5000 limit) without category/team filters.
        suggestions = self.engine.get_suggestions(active_ids, limit=5000)
        
        is_pvp = self.check_pvp.isChecked()
        show_others = self.check_show_others.isChecked()
        
        # Determine current professions (Bar ONLY - ignore dropdown)
        profs_in_bar = set()
        
        for sid in active_ids:
            if sid != 0:
                s = self.repo.get_skill(sid, is_pvp=is_pvp)
                if s and s.profession != 0:
                    profs_in_bar.add(s.profession)
        
        # Logic for filtering
        filtered_suggestions = []
        
        # Define allowed professions if we are in "Strict Mode" (not showing others)
        allowed_profs = set()
        enforce_prof_limit = False
        
        if not show_others:
            # If we aren't explicitly showing others, check if we have hit the 2-prof limit
            if len(profs_in_bar) >= 2:
                enforce_prof_limit = True
                allowed_profs.update(profs_in_bar)
                allowed_profs.add(0) # Always allow Common skills in strict mode

        for sid, conf in suggestions:
            skill = self.repo.get_skill(sid, is_pvp=is_pvp)
            if not skill: continue
            
            # PvP Filter
            if is_pvp and skill.is_pve_only:
                continue
            
            # Profession Filter
            if enforce_prof_limit:
                if skill.profession not in allowed_profs:
                    continue
            
            filtered_suggestions.append((sid, conf))
        
        self.current_suggestions = filtered_suggestions
        # Reset offset because the list has changed
        self.suggestion_offset = 0
             
        self.display_suggestions()

    def display_suggestions(self):
        # Slice the current suggestions based on offset
        # We need enough to fill empty slots
        empty_indices = [i for i, s in enumerate(self.bar_skills) if s is None]
        
        # Get slice
        # We need len(empty_indices) suggestions starting from offset
        # Handle wrapping? Or just stop? "Cycle" implies wrapping.
        
        display_list = []
        count_needed = len(empty_indices)
        is_pvp = self.check_pvp.isChecked()

        if self.current_suggestions:
            total = len(self.current_suggestions)
            for i in range(count_needed):
                idx = (self.suggestion_offset + i) % total
                display_list.append(self.current_suggestions[idx])
        
        # Fill empty slots
        s_idx = 0
        for slot_idx in empty_indices:
            slot = self.slots[slot_idx]
            if s_idx < len(display_list):
                s_id, conf = display_list[s_idx]
                skill_obj = self.repo.get_skill(s_id, is_pvp=is_pvp)
                slot.set_skill(s_id, skill_obj, ghost=True, confidence=conf)
                s_idx += 1
            else:
                slot.clear_slot(silent=True)
                
        # Also update the code section based on ACTUAL skills only
        self.update_build_code()

    def swap_professions(self):
        self.is_swapped = not self.is_swapped
        self.update_build_code()

    def update_build_code(self):
        # Determine full skill bar (Active only, ignore ghosts for code?)
        # Standard GW templates usually don't include empty slots unless explicitly 0.
        
        active_bar = [s if s is not None else 0 for s in self.bar_skills]
        
        # Profession Logic for code generation
        profs_in_bar = set()
        for sid in active_bar:
            if sid != 0:
                s = self.repo.get_skill(sid)
                if s and s.profession != 0:
                    profs_in_bar.add(s.profession)
        
        primary_id = 0
        secondary_id = 0
        
        # 1. Try to get Primary from Dropdown
        try: 
            combo_val = int(self.combo_prof.currentText().split(' ')[0])
            if combo_val != 0:
                primary_id = combo_val
        except: pass
        
        # 2. Get Secondary from Skills (excluding primary)
        # Or if Primary is 0, infer both from skills
        
        profs_sorted = sorted(list(profs_in_bar))
        
        # If no primary selected, take first available
        if primary_id == 0:
            if len(profs_sorted) >= 1: primary_id = profs_sorted[0]
        
        # Find secondary
        # It's the first prof in list that isn't primary
        for pid in profs_sorted:
            if pid != primary_id:
                secondary_id = pid
                break
        
        # Apply Swap if requested
        if self.is_swapped:
            primary_id, secondary_id = secondary_id, primary_id
            
        # Update Display Label
        p1_name = PROF_MAP.get(primary_id, "No Profession")
        p2_name = PROF_MAP.get(secondary_id, "No Profession")
        p1_str = PROF_SHORT_MAP.get(p1_name, "X")
        p2_str = PROF_SHORT_MAP.get(p2_name, "X")
        
        self.lbl_prof_display.setText(f"{p1_str}/{p2_str}")

        attributes = []
        if primary_id in PROF_PRIMARY_ATTR:
            attributes.append([PROF_PRIMARY_ATTR[primary_id], 11])
        if secondary_id in PROF_PRIMARY_ATTR:
            attr_id = PROF_PRIMARY_ATTR[secondary_id]
            if not any(a[0] == attr_id for a in attributes):
                attributes.append([attr_id, 11])

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

# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Dark Mode Theme
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
