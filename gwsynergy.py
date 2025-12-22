import sys
import os
import json
import sqlite3
from dataclasses import dataclass
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

DB_FILE = resource_path('master.db') 
JSON_FILE = resource_path('all_skills.json')
ICON_DIR = resource_path('icons/skill_icons')
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
        if rech_a > 0 and (rech_a + 0.25) < cycle_b: return False, f"Timing Clog (Wait {cycle_b - rech_a:.1f}s)"

        return True, "Stable"

    # --- MAIN LOOP ---
    def find_synergies(self, active_skill_ids: List[int], primary_prof_id: int = 0, debug_mode: bool = False, stop_check=None) -> List[tuple[int, str]]:
        if not active_skill_ids: return []

        try:
            conn = sqlite3.connect(self.db_path)
            table = self._get_table()
            
            cols = "skill_id, name, description, energy_cost, activation, recharge, adrenaline, health_cost, aftercast, combo_req, is_elite, attribute"
            placeholders = ','.join(['?'] * len(active_skill_ids))
            
            q_active = f"SELECT {cols} FROM {table} WHERE skill_id IN ({placeholders})"
            cursor = conn.execute(q_active, active_skill_ids)
            active_skills_data = cursor.fetchall()
            
            context = SystemContext(primary_prof_id)
            for s in active_skills_data:
                context.ingest_skill(s)

            synergies = []
            conditions = ['Burning', 'Bleeding', 'Dazed', 'Deep Wound', 'Weakness', 'Poison', 'Knockdown', 'Hexed', 'Enchanted']
            existing_ids = set(active_skill_ids)

            for root in active_skills_data:
                if stop_check and stop_check(): return []
                
                root_desc = root[2].lower() if root[2] else ""
                root_hp_cost = root[7] or 0
                
                # --- A. HEALTH & MECHANICS SEARCH ---
                
                # 1. LAW OF PRESERVATION (Upstream)
                # If we sacrifice health, we NEED healing.
                if root_hp_cost > 0 or "sacrifice" in root_desc:
                     q_heal = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%heal%' OR description LIKE '%regeneration%')
                        AND description NOT LIKE '%sacrifice%'
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                     """
                     self._process_matches(conn, q_heal, list(existing_ids), root, context, synergies, debug_mode, "Mitigates Sacrifice", stop_check)

                # 2. LAW OF AUGMENTATION (Downstream)
                # If we Heal, look for skills that boost Healing.
                if "heal" in root_desc and ("target ally" in root_desc or "party" in root_desc):
                    q_boost = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%whenever you heal%' OR description LIKE '%healing prayers%' OR description LIKE '%50% extra health%')
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_boost, list(existing_ids), root, context, synergies, debug_mode, "Boosts Healing", stop_check)

                # 3. LAW OF ENCHANTMENT (Downstream)
                # If we cast an Enchantment, look for things that use/count Enchantments.
                if "enchantment" in root_desc and "spell" in root_desc:
                    q_ench = f"""
                        SELECT {cols} FROM {table}
                        WHERE (description LIKE '%for each enchantment%' OR description LIKE '%while you are enchanted%' OR description LIKE '%extend%enchantment%')
                        AND description NOT LIKE '%remove%'
                        AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})
                    """
                    self._process_matches(conn, q_ench, list(existing_ids), root, context, synergies, debug_mode, "Uses Enchantment", stop_check)

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
                   health_cost, aftercast, combo_req, is_touch, campaign
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
            return self.get_skill(skill_id, is_pvp=False) # Total fallback if missing in PvP

        # B. Get Physics Data from PvE Table
        query_physics = """
            SELECT health_cost, aftercast, combo_req, is_touch, campaign
            FROM skills
            WHERE skill_id=?
        """
        self.cursor.execute(query_physics, (skill_id,))
        pve_row = self.cursor.fetchone()
        
        # Defaults if PvE is also missing (unlikely)
        phys_data = pve_row if pve_row else (0, 0.75, 0, 0, 0)
        
        # C. Stitch it together
        # pvp_row has indices 0-10. phys_data has 0-4.
        # We construct a "fake" full row to pass to the object creator.
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
            campaign=int(row[15] or 0)
        )
        self._cache[cache_key] = skill
        return skill

    def get_all_skills_by_ids(self, ids: List[int], is_pvp: bool = False) -> List[Skill]:
        skills = []
        for sid in ids:
            s = self.get_skill(sid, is_pvp=is_pvp)
            if s:
                skills.append(s)
        return skills

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

class DraggableSkillIcon(QFrame):
    clicked = pyqtSignal(Skill)
    double_clicked = pyqtSignal(Skill)

    def __init__(self, skill: Skill, parent=None):
        super().__init__(parent)
        self.skill = skill
        self.setFixedSize(ICON_SIZE + 10, ICON_SIZE + 60)
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
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self.icon_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        
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
            drag.setPixmap(self.icon_lbl.pixmap()) 
            drag.setHotSpot(event.position().toPoint())
            drag.exec(Qt.DropAction.CopyAction)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.skill)

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

    def set_skill(self, skill_id, skill_obj: Skill = None, ghost=False, confidence=0.0):
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
            
            # Formatted tooltip based on confidence type
            if isinstance(confidence, str):
                self.setToolTip(f"Smart Synergy: {skill_obj.name}\n{confidence}")
            else:
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guild Wars Synergy Builder")
        self.resize(1200, 800)
        
        # Load Data
        self.repo = SkillRepository(DB_FILE)
        self.engine = SynergyEngine(JSON_FILE) # Legacy
        self.smart_engine = HamiltonianEngine(DB_FILE) # NEW: Physics Engine
        
        # State
        self.bar_skills = [None] * 8 
        self.suggestion_offset = 0
        self.current_suggestions = [] 
        self.is_swapped = False 
        self.template_path = "" 
        
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
        self.combo_team.addItems(sorted(list(valid_teams)))
        
        index = self.combo_team.findText(current_team)
        if index != -1:
            self.combo_team.setCurrentIndex(index)
        else:
            self.combo_team.setCurrentIndex(0)
            
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
        filter_layout.addWidget(QLabel("Team:"))
        filter_layout.addWidget(self.combo_team)
        
        filter_layout.addSpacing(20)
        self.check_pvp = QCheckBox("PvP?")
        self.check_pvp.toggled.connect(self.on_pvp_toggled) # Updated handler
        filter_layout.addWidget(self.check_pvp)

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

        # --- 2. Center Splitter ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.skill_grid_widget = QWidget()
        self.skill_grid_layout = QGridLayout(self.skill_grid_widget)
        self.skill_grid_layout.setHorizontalSpacing(20) 
        self.skill_grid_layout.setVerticalSpacing(10)
        self.skill_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.skill_grid_widget)
        
        self.splitter.addWidget(self.scroll_area)
        self.info_panel = SkillInfoPanel()
        self.splitter.addWidget(self.info_panel)
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

        self.btn_cycle = QPushButton("Cycle\nSuggestions")
        self.btn_cycle.setFixedSize(90, 50)
        self.btn_cycle.setStyleSheet("""
            QPushButton { background-color: #444; color: white; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #555; }
            QPushButton:pressed { background-color: #666; }
        """)
        self.btn_cycle.clicked.connect(self.cycle_suggestions)
        cycle_layout.addWidget(self.btn_cycle)

        self.check_debug = QCheckBox("Debug Mode")
        self.check_debug.setStyleSheet("color: #FF5555; font-size: 10px; font-weight: bold;")
        self.check_debug.setToolTip("Show rejected suggestions in tooltips.\nHover over ghost icons to see why they failed.")
        self.check_debug.toggled.connect(self.update_suggestions)
        cycle_layout.addWidget(self.check_debug, alignment=Qt.AlignmentFlag.AlignCenter)
        
        container_layout.addWidget(cycle_container)

        # --- Skill Slots ---
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
        container_layout.addSpacing(20) 
        
        # --- Control Layout (Right Side) ---
        control_layout = QVBoxLayout()
        
        self.check_show_others = QCheckBox("Show Other\nProfessions")
        self.check_show_others.toggled.connect(self.update_suggestions)
        control_layout.addWidget(self.check_show_others)

        self.check_lock_suggestions = QCheckBox("Lock")
        self.check_lock_suggestions.toggled.connect(self.update_suggestions)
        control_layout.addWidget(self.check_lock_suggestions)
        
        self.check_smart_mode = QCheckBox("Smart Mode\n(Physics)")
        self.check_smart_mode.setStyleSheet("color: #FFD700; font-weight: bold;")
        self.check_smart_mode.toggled.connect(self.update_suggestions)
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

    def on_pvp_toggled(self, checked):
        # Update both engines and refresh
        mode = "pvp" if checked else "pve"
        self.smart_engine.set_mode(mode)
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

    def handle_skill_double_clicked(self, skill: Skill):
        empty_index = -1
        for i, s_id in enumerate(self.bar_skills):
            if s_id is None:
                empty_index = i
                break
        
        if empty_index != -1:
            self.handle_skill_equipped(empty_index, skill.id)

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
        
        for i in reversed(range(self.skill_grid_layout.count())): 
            self.skill_grid_layout.itemAt(i).widget().setParent(None)

        if team != "All":
            matching_builds = [b for b in self.engine.builds if b.team == team]
            if cat != "All":
                matching_builds = [b for b in matching_builds if b.category == cat]
            
            unique_builds = []
            seen_codes = set()
            for b in matching_builds:
                if b.code not in seen_codes:
                    unique_builds.append(b)
                    seen_codes.add(b.code)
            
            row = 0
            cols_wide = 8
            for b in unique_builds:
                widget = BuildPreviewWidget(b, self.repo, is_pvp=self.check_pvp.isChecked())
                widget.clicked.connect(lambda code=b.code: self.load_code(code_str=code))
                widget.skill_clicked.connect(self.info_panel.update_info)
                self.skill_grid_layout.addWidget(widget, row, 0, 1, cols_wide) 
                row += 1
            return

        search_text = self.edit_search.text().lower()
        is_pvp = self.check_pvp.isChecked()
        is_elites_only = self.check_elites_only.isChecked()
        is_no_elites = self.check_no_elites.isChecked()
        
        valid_ids = self.engine.filter_skills(prof, cat, team)
        
        filtered_skills = []
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
                if is_pvp and skill.is_pve_only:
                    continue
                if is_elites_only and not skill.is_elite:
                    continue
                if is_no_elites and skill.is_elite:
                    continue
                if target_prof_id != -1:
                    if skill.profession != target_prof_id:
                        continue
                    
                filtered_skills.append(skill)

        if len(filtered_skills) > 500:
             filtered_skills = filtered_skills[:500]

        row, col = 0, 0
        cols_wide = 8 
        
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
        self.suggestion_offset = 0 
        
        is_pvp = self.check_pvp.isChecked()
        skill_obj = self.repo.get_skill(skill_id, is_pvp=is_pvp)
        self.slots[index].set_skill(skill_id, skill_obj, ghost=False)
        
        self.update_suggestions()

    def handle_skill_removed(self, index):
        self.bar_skills[index] = None
        self.suggestion_offset = 0 
        self.update_suggestions()
        
    def refresh_equipped_skills(self):
        is_pvp = self.check_pvp.isChecked()
        for i, sid in enumerate(self.bar_skills):
            if sid is not None:
                skill_obj = self.repo.get_skill(sid, is_pvp=is_pvp)
                self.slots[i].set_skill(sid, skill_obj, ghost=False)
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

        for sid, conf in suggestions:
            skill = self.repo.get_skill(sid, is_pvp=is_pvp)
            if not skill: continue
            
            if is_pvp and skill.is_pve_only: continue
            
            if enforce_prof_limit:
                if skill.profession not in allowed_profs:
                    continue
            
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
        
        # Get Profession ID
        prof_text = self.combo_prof.currentText()
        try:
            pid = int(prof_text.split(' ')[0])
        except:
            pid = 0

        # Check Debug
        is_debug = False
        if hasattr(self, 'check_debug'):
            is_debug = self.check_debug.isChecked()

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
        for slot_idx in empty_indices:
            slot = self.slots[slot_idx]
            
            if s_idx < len(display_list):
                # Fill slot with suggestion
                s_id, conf = display_list[s_idx]
                skill_obj = self.repo.get_skill(s_id, is_pvp=is_pvp)
                slot.set_skill(s_id, skill_obj, ghost=True, confidence=conf)
                s_idx += 1
            else:
                # Ran out of suggestions? Clear the slot.
                slot.clear_slot(silent=True)
                
        self.update_build_code()

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