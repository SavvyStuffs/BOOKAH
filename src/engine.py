import sqlite3
import json
import os
import collections
from typing import List, Set, Tuple
from collections import Counter
from src.skill2vec import SkillBrain
from src.utils import GuildWarsTemplateDecoder
from src.models import Build
from src.constants import BEHAVIOR_MODEL_PATH, SEMANTIC_MODEL_PATH, USER_BUILDS_FILE

# =============================================================================
# MECHANICS ENGINE

CONDITION_DEFINITIONS = {
    "bleeding": {
        "providers": ["causes bleeding", "inflicts bleeding", "target foe bleeds", "strike a bleeding foe"],
        "consumers": ["if target is bleeding", "against a bleeding foe"],
        "negatives": ["remove", "cure", "end", "lose", "immune", "reduced"]
    },
    "burning": {
        "providers": ["causes burning", "inflicts burning", "target foe burns", "strike a burning foe"],
        "consumers": ["if target is burning", "against a burning foe", "duration of burning"],
        "negatives": ["extinguish", "remove", "cure", "less fire damage"]
    },
    "poison": {
        "providers": ["causes poison", "inflicts poison", "poisonous"],
        "consumers": ["if target is poisoned", "against a poisoned foe"],
        "negatives": ["cure", "remove",]
    },
    "deep wound": {
        "providers": ["causes a deep wound", "inflicts deep wound"],
        "consumers": ["if target has a deep wound", "against a deep wounded foe"],
        "negatives": ["cure", "remove",]
    },
    "dazed": {
        "providers": ["dazes target", "causes dazed", "interrupts... and dazes"],
        "consumers": ["against a dazed foe", "casting time increased"],
        "negatives": ["cure", "remove"]
    },
    "weakness": {
        "providers": ["causes weakness", "inflicts weakness", "enfeebles"],
        "consumers": ["against a weakened foe", "if target is weakened"],
        "negatives": ["cure", "remove", "restore attributes"]
    },
    "blind": {
        "providers": ["causes blindness", "inflicts blindness", "target foe is blinded", "blinds target"],
        "consumers": ["against a blinded foe", "if target is blinded"],
        "negatives": ["cure", "remove", "sight"]
    },
    "cripple": {
        "providers": ["cripples target", "causes crippled", "target foe is crippled"],
        "consumers": ["against a crippled foe", "if target is crippled"],
        "negatives": ["cure", "remove", "move speed"]
    },
    "disease": {
        "providers": ["causes disease", "inflicts disease"],
        "consumers": ["if target is diseased"],
        "negatives": ["cure", "remove", "cauterize"]
    }
}

class BuildState:
    """
    Represents the instantaneous state of the build.
    Tracks resources, mechanic states, and active effects.
    """
    def __init__(self, primary_prof_id=0):
        # --- Profession Physics Config ---
        # Casters: Monk(3), Necro(4), Mesmer(5), Ele(6), Rit(8)
        self.is_caster = primary_prof_id in [3, 4, 5, 6, 8]
        
        self.elite_count = 0
        
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
        self.self_heal_count = 0
        self.energy_management_count = 0
        self.has_high_cost = False
        self.has_energy_denial = False
        self.knockdowns = False
        self.hexes_applied = False
        
        self.combo_stages = set()
        self.conditions_applied = set()
        self.active_attributes = set() # Track used attributes
        
        # --- Weapon Tracking ---
        self.primary_weapon = None
        self.WEAPON_MAP = {
            18: "Axe", 19: "Hammer", 20: "Sword",      # Warrior
            25: "Bow",                                 # Ranger
            29: "Dagger",                              # Assassin
            37: "Spear",                               # Paragon
            41: "Scythe"                               # Dervish
        }

    def ingest_skill(self, skill, tags=None):
        """
        Reads a skill row from the DB and updates the System Context.
        DB Index: 0:id, 1:name, 2:desc, 3:nrg, 4:act, 5:rech, 6:adr, 7:hp, 8:aft, 9:combo, 10:elite, 11:attr
        """
        if tags is None: tags = set()
        name = skill[1].lower()
        desc = skill[2].lower() if skill[2] else ""
        nrg = skill[3] or 0
        rech = skill[5] or 0.0
        attr = skill[11] or -1
        
        if attr != -1:
            self.active_attributes.add(attr)
        
        # 1. Physics: Energy Entropy
        if rech > 0:
            self.energy_drain_per_sec += (nrg / rech)
            
        # 2. Law of Occupancy & Mechanics
        if skill[10]: self.elite_count += 1
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

        # 6. Basic Needs Tracking
        if "heal" in desc and ("self" in desc or "you" in desc): self.self_heal_count += 1
        
        # Energy Management tracking
        if ("gain" in desc and "energy" in desc) or 'Type_Energy_Management' in tags:
            self.energy_management_count += 1
            
        if nrg >= 15:
            self.has_high_cost = True
            
        if 'Type_Energy_Denial' in tags:
            self.has_energy_denial = True

    def calculate_efficiency(self, candidate_skill):
        """ Calculates variable efficiency modifiers (Smart Logic). """
        name = candidate_skill[1].lower()
        attr = candidate_skill[11] or -1
        
        score = 1.0
        
        # Attribute Efficiency: Bonus for sticking to active attributes
        if attr != -1 and attr in self.active_attributes:
            score += 0.3
        elif attr != -1 and len(self.active_attributes) >= 3:
            # Penalize spreading too thin (if we already have 3+ attributes)
            score -= 0.2
        
        # Logic: Mystic Regeneration
        if "mystic regeneration" in name:
            if self.active_enchantments == 0: return 0.1, "Useless (No Enchants)"
            if self.active_enchantments < 3: return 0.5, "Weak Heal"
            return 1.5, "Strong Synergy"
            
        return score, "OK"

class MechanicsEngine:
    """
    Connects to master.db to perform mechanic checks and system validation.
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
        if "stance" in desc and context.stance_count >= 2: return False, "Stance Clog"
        if "weapon spell" in desc and context.weapon_spell_count >= 2: return False, "Weapon Spell Clog"
        return True, "OK"

    def check_causal_viability(self, candidate_row, context):
        desc = candidate_row[2].lower()
        if "remove a hex" in desc and not context.hexes_applied: return False, "No Hexes to Shatter"
        if "knocked down foe" in desc and not context.knockdowns: return False, "No Knockdowns present"
        return True, "OK"

    def check_energy_drain(self, candidate_row, context):
        nrg = candidate_row[3] or 0
        rech = candidate_row[5] or 0.0
        if rech > 0:
            candidate_eps = nrg / rech
            total_drain = context.energy_drain_per_sec + candidate_eps
            limit = 4.0 if context.is_caster else 2.5
            if total_drain > limit: return True, "⚠️ High Energy Usage"
        return True, "OK"

    def check_resource_stability(self, skill_a_data, skill_b_data, context):
        e_a, rech_a, hp_a = skill_a_data[3] or 0, skill_a_data[5] or 0.0, skill_a_data[7] or 0
        e_b, act_b, hp_b = skill_b_data[3] or 0, skill_b_data[4] or 0.0, skill_b_data[7] or 0
        rech_b = skill_b_data[5] or 0.0
        aft_b = skill_b_data[8] or 0.75

        burst_cost = e_a + e_b
        cap = context.max_energy_capacity
        
        if burst_cost > cap: return False, "⚠️ High Energy Usage"
        if burst_cost > (cap * 0.8): return True, "⚠️ High Energy Usage"

        total_hp = hp_a + hp_b
        if total_hp > 50 and (rech_a < 8 or rech_b < 8): return False, "⚠️ High Health Cost"

        return True, "Stable"

    def _check_condition_logic(self, desc, condition_key):
        def_data = CONDITION_DEFINITIONS[condition_key]
        
        # 1. Negative Check (Fast Fail)
        idx = desc.find(condition_key)
        if idx != -1:
            start = max(0, idx - 40)
            end = min(len(desc), idx + 20)
            context_window = desc[start:end]
            if any(neg in context_window for neg in def_data['negatives']):
                return "Neutral" # It's a cure/reduction, ignore it

        # 2. Provider Check
        if any(prov in desc for prov in def_data['providers']):
            return "Provider"

        # 3. Consumer Check
        if any(cons in desc for cons in def_data['consumers']):
            return "Consumer"
            
        return "None"
    
    def find_counters(self, threats: List[Tuple[int, bool]]) -> List[Tuple[int, float, str]]:
        if not threats: return []
        
        threat_ids = [t[0] for t in threats]
        boss_ids = {t[0] for t in threats if t[1]}
        
        conn = sqlite3.connect(self.db_path)
        placeholders = ','.join(['?'] * len(threat_ids))
        
        # 1. Analyze Threats
        mechanics = Counter()
        
        # Description Scan
        q = f"SELECT skill_id, description FROM skills WHERE skill_id IN ({placeholders})"
        rows = conn.execute(q, threat_ids).fetchall()
        for sid, desc in rows:
            weight = 3 if sid in boss_ids else 1
            d = desc.lower() if desc else ""
            if "hex" in d: mechanics['hex'] += weight
            if "enchantment" in d: mechanics['enchantment'] += weight
            if "condition" in d or "bleeding" in d or "burning" in d or "poison" in d: mechanics['condition'] += weight
            if "knock down" in d: mechanics['knockdown'] += weight
            
        # Tag Scan
        q_tags = f"SELECT tag FROM skill_tags WHERE skill_id IN ({placeholders})"
        # Need to map tags back to IDs to apply weight.
        # This query loses ID association.
        # Better: SELECT skill_id, tag FROM ...
        q_tags_full = f"SELECT skill_id, tag FROM skill_tags WHERE skill_id IN ({placeholders})"
        tag_rows = conn.execute(q_tags_full, threat_ids).fetchall()
        
        for sid, tag in tag_rows:
            weight = 3 if sid in boss_ids else 1
            if tag == 'Type_Hex': mechanics['hex'] += weight
            if tag == 'Type_Enchantment': mechanics['enchantment'] += weight
            if tag == 'Type_Condition': mechanics['condition'] += weight
            if tag == 'Control_Knockdown': mechanics['knockdown'] += weight
            if tag == 'Type_Attack_Physical': mechanics['physical'] += weight
            if tag == 'Type_Attack_Ranged': mechanics['ranged'] += weight
            if tag == 'Type_Healing_Ally': mechanics['healer'] += weight
            if tag == 'Type_Energy_Denial': mechanics['energy_denial'] += weight
            if tag == 'Type_Degeneration': mechanics['degen'] += weight

        # 2. Find Defensive Counters
        counter_data = {}
        
        def add_counters(search_term, score_weight, reason_label):
            q_c = f"SELECT skill_id FROM skills WHERE description LIKE '%{search_term}%'"
            for row in conn.execute(q_c):
                sid = row[0]
                if sid not in counter_data:
                    counter_data[sid] = {'score': 0, 'reasons': set()}
                counter_data[sid]['score'] += score_weight
                counter_data[sid]['reasons'].add(reason_label)

        # Thresholds to avoid noise (e.g. only suggest Hex Removal if Hex score > 2)
        
        if mechanics['hex'] > 0:
            add_counters("remove hex", mechanics['hex'], "Anti-Hex")
            
        if mechanics['condition'] > 0:
            add_counters("remove condition", mechanics['condition'], "Anti-Condi")
            add_counters("cure condition", mechanics['condition'], "Anti-Condi")
            
        if mechanics['enchantment'] > 0:
            # If enemies have enchants, we strip them to survive (reduce their buff)
            add_counters("remove enchantment", mechanics['enchantment'], "Strip Enchant")
            add_counters("strip enchantment", mechanics['enchantment'], "Strip Enchant")
            
        if mechanics['knockdown'] > 0:
            add_counters("stability", mechanics['knockdown'] * 2, "Stability") # High priority
            add_counters("cannot be knocked down", mechanics['knockdown'] * 2, "Stability")
            # "Stance" generic search is too broad
            
        if mechanics['physical'] > 0:
            add_counters("block", mechanics['physical'], "Block")
            add_counters("blind", mechanics['physical'], "Blind")
            add_counters("weakness", mechanics['physical'], "Weakness")
            
        if mechanics['ranged'] > 0:
            # Reflection is the best defense against ranged
            add_counters("reflect", mechanics['ranged'] * 2, "Reflection")
            add_counters("shield", mechanics['ranged'], "Shielding") # e.g. "Shield of Absorption"
            
        if mechanics['healer'] > 0:
            add_counters("interrupt", mechanics['healer'], "Interrupt")
            add_counters("daze", mechanics['healer'], "Daze")
            
        if mechanics['energy_denial'] > 0:
            add_counters("gain energy", mechanics['energy_denial'], "Energy Mgmt")
            
        if mechanics['degen'] > 0:
            add_counters("regeneration", mechanics['degen'], "Regen")

        conn.close()
        
        # Format results
        total_threat_score = sum(mechanics.values()) or 1
        results = []
        
        sorted_items = sorted(counter_data.items(), key=lambda x: x[1]['score'], reverse=True)
        
        for sid, data in sorted_items[:50]: # Limit to top 50 relevant
            norm = min(1.0, data['score'] / max(1, total_threat_score * 0.5))
            reason_str = ", ".join(sorted(list(data['reasons'])))
            results.append((sid, norm, reason_str))
            
        return results

    def get_basic_needs_suggestions(self, context: BuildState, is_pre: bool = False) -> List[Tuple[int, float, str]]:
        suggestions = []
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Base query part
            join_clause = "JOIN skills s ON t.skill_id = s.skill_id"
            pre_clause = "AND s.in_pre = 1" if is_pre else ""
            
            # 1. Self Heal
            if context.self_heal_count == 0:
                q = f"SELECT t.skill_id FROM skill_tags t {join_clause} WHERE t.tag = 'Type_Healing_Self' {pre_clause} ORDER BY random() LIMIT 3"
                rows = conn.execute(q).fetchall()
                for r in rows:
                    suggestions.append((r[0], 0.75, "Missing Self Heal"))

            # 2. Energy Management (Casters)
            if context.is_caster and context.energy_management_count == 0:
                q = f"SELECT t.skill_id FROM skill_tags t {join_clause} WHERE t.tag = 'Type_Energy_Management' {pre_clause} ORDER BY random() LIMIT 3"
                rows = conn.execute(q).fetchall()
                for r in rows:
                    suggestions.append((r[0], 0.75, "Missing Energy Mgmt"))
                    
            conn.close()
        except Exception as e:
            print(f"Error in basic needs: {e}")
            
        return suggestions

    def validate_neural_suggestion(self, skill_id: int, context: BuildState) -> Tuple[bool, str]:
        """
        Checks if a suggestion obeys mechanic constraints.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            table = self._get_table()
            
            query = f"SELECT skill_id, name, description, energy_cost, activation, recharge, adrenaline, health_cost, aftercast, combo_req, is_elite, attribute FROM {table} WHERE skill_id = ?"
            cursor = conn.execute(query, (skill_id,))
            skill_data = cursor.fetchone()
            conn.close()

            if not skill_data: return False, "Unknown Skill"

            # 1. Weapon Compatibility
            valid, reason = self.check_weapon_compatibility(skill_data[11], context)
            if not valid: return False, reason

            # 2. Occupancy
            valid, reason = self.check_occupancy_viability(skill_data, context)
            if not valid: return False, reason
            
            # 3. Energy Checks
            valid, reason = self.check_energy_drain(skill_data, context)
            if not valid: return False, reason

            return True, "Neural Synergy"
            
        except Exception as e:
            return False, f"Validation Error: {e}"

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
            
            context = BuildState(primary_prof_id)
            has_mantra = False
            for s in active_skills_data:
                context.ingest_skill(s, skill_tags_map.get(s[0], set()))
                if s[1].lower().startswith("mantra"):
                    has_mantra = True

            synergies = []
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
                is_hex_cons = ("hexed foe" in root_desc or "remove a hex" in root_desc or "shatter" in root_desc) and root_target_type != 3
                
                is_ench_prov = 'Type_Enchantment' in root_tags
                is_ench_cons = "while you are enchanted" in root_desc or "for each enchantment" in root_desc or "extend" in root_desc and "enchantment" in root_desc
                
                is_spirit_prov = 'Type_Spirit' in root_tags
                
                # Check for consumers of spirits (excluding "non-spirit" matches)
                is_spirit_cons = False
                if "non-spirit" not in root_desc:
                    if "near a spirit" in root_desc or "earshot of a spirit" in root_desc:
                        is_spirit_cons = True
                    elif "destroy" in root_desc and "spirit" in root_desc:
                        is_spirit_cons = True
                
                is_signet_prov = 'Type_Signet' in root_tags
                is_signet_cons = "equipped signet" in root_desc or "signet you control" in root_desc or "recharge" in root_desc and "signet" in root_desc
                
                is_corpse_cons = 'Type_Corpse_Exploit' in root_tags or "exploit" in root_desc and "corpse" in root_desc or "minion" in root_desc
                
                is_kd_prov = 'Control_Knockdown' in root_tags
                is_kd_cons = "knocked down foe" in root_desc or "against a knocked down" in root_desc
                
                is_int_prov = 'Control_Interrupt' in root_tags
                is_int_cons = "if you interrupt" in root_desc or "whenever you interrupt" in root_desc or "after you interrupt" in root_desc
                
                # HEALING SPLIT
                is_heal_self = 'Type_Healing_Self' in root_tags
                is_heal_ally = 'Type_Healing_Ally' in root_tags
                is_heal_life = 'Type_Healing_Lifesteal' in root_tags
                is_heal_prov = is_heal_self or is_heal_ally or is_heal_life
                
                is_heal_cons = "whenever you heal" in root_desc or "heal bonus" in root_desc
                
                is_degen_prov = 'Type_Degeneration' in root_tags
                is_degen_cons = "suffers from degeneration" in root_desc or "whenever target suffers degeneration" in root_desc
                
                is_nrg_prov = 'Type_Energy_Management' in root_tags
                is_nrg_cons = "energy lost" in root_desc
                
                is_phys_prov = 'Type_Attack_Physical' in root_tags
                is_phys_cons = "physical damage" in root_desc and ("deal" not in root_desc) or "attack skill" in root_desc
                
                is_ranged_prov = 'Type_Attack_Ranged' in root_tags
                is_ranged_cons = "projectile" in root_desc or "bow attack" in root_desc
                
                is_cond_prov = 'Type_Condition' in root_tags
                is_cond_cons = "if target is" in root_desc or "against" in root_desc and any(x in root_desc for x in ["bleeding", "burning", "poison", "disease", "blinded", "dazed", "weakness", "cripple", "deep wound"])
                
                is_buff_prov = 'Type_Buff' in root_tags
                is_stance_prov = 'Type_Stance' in root_tags
                is_pet_prov = 'Type_Pet' in root_tags or "pet" in root_desc or "beast" in root_desc or "charm animal" in root_desc
                
                # Check for existing pet or stance count
                has_pet = False
                stance_count = 0
                
                # We need to query tags for existing_ids to check for pets/stances properly
                if existing_ids:
                    q_check = f"SELECT tag FROM skill_tags WHERE skill_id IN ({','.join(['?']*len(existing_ids))})"
                    check_rows = conn.execute(q_check, list(existing_ids)).fetchall()
                    for (tag,) in check_rows:
                        if tag == 'Type_Pet': has_pet = True
                        if tag == 'Type_Stance': stance_count += 1
                    
                    # Also check names for specific pet skills if tags miss them
                    q_names = f"SELECT name FROM {table} WHERE skill_id IN ({','.join(['?']*len(existing_ids))})"
                    name_rows = conn.execute(q_names, list(existing_ids)).fetchall()
                    for (name,) in name_rows:
                        if name.lower() in ["charm animal", "comfort animal"]: has_pet = True

                # --- 2. LAW OF ENCHANTMENT ---
                if is_ench_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%for each enchantment%' OR description LIKE '%while you are enchanted%' OR description LIKE '%extend%enchantment%') AND description NOT LIKE '%remove%' AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Uses Enchantment", stop_check, has_mantra=has_mantra)
                if is_ench_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Enchantment') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Enchantment", stop_check, has_mantra=has_mantra)

                # --- 3. LAW OF MULTIPLICATION (AoE Synergy) ---
                if ("adjacent" in root_desc or "nearby" in root_desc) and ("attack" in root_desc or "strike" in root_desc or "shoot" in root_desc):
                     q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%adjacent%' OR description LIKE '%nearby%') AND (description LIKE '%deal%damage%' OR description LIKE '%strike%') AND (skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Weapon_Spell' OR tag='Type_Enchantment')) AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                     self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "AoE Payload", stop_check, has_mantra=has_mantra)

                # --- 4. LAW OF SPIRITUALISM ---
                if is_spirit_prov:
                    # Suggest skills that use spirits (exclude non-spirit)
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%near a spirit%' OR description LIKE '%earshot of a spirit%' OR description LIKE '%destroy%spirit%' OR description LIKE '%spirit%loses health%') AND description NOT LIKE '%non-spirit%' AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Uses Spirits", stop_check, has_mantra=has_mantra)
                    # Suggest more spirits (Spirit Army)
                    q_army = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Spirit') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q_army, list(existing_ids), root, context, synergies, debug_mode, "Spirit Army", stop_check, has_mantra=has_mantra)

                if is_spirit_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Spirit') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Creates Spirits", stop_check, has_mantra=has_mantra)

                # --- 5. LAW OF GRAVITY ---
                if is_kd_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%knocked down foe%' OR description LIKE '%against a knocked down%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Punishes Knockdown", stop_check, has_mantra=has_mantra)
                if is_kd_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Control_Knockdown') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Knockdown", stop_check, has_mantra=has_mantra)

                # --- 6. LAW OF DISRUPTION ---
                if is_int_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%if you interrupt%' OR description LIKE '%whenever you interrupt%' OR description LIKE '%after you interrupt%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Rewards Interrupt", stop_check, has_mantra=has_mantra)
                if is_int_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Control_Interrupt') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Interrupt", stop_check, has_mantra=has_mantra)

                # --- 7. LAW OF THE DEAD ---
                if is_corpse_cons:
                    # Suggest other skills that exploit corpses or provide them (Minions included)
                    q_exploit = f"SELECT {cols} FROM {table} WHERE (skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Corpse_Exploit') OR (description LIKE '%exploit%' AND description LIKE '%corpse%') OR (description LIKE '%minion%') OR (description LIKE '%create%' AND description LIKE '%corpse%')) AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q_exploit, list(existing_ids), root, context, synergies, debug_mode, "Corpse/Minion Synergy", stop_check, has_mantra=has_mantra)

                # --- 8. LAW OF HEXES (Refined) ---
                if is_hex_prov:
                    # Recommend Stacking Hexes (e.g. Necromancer/Mesmer pressure)
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Hex') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Hex Synergy", stop_check, has_mantra=has_mantra)
                    
                if is_hex_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Hex') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Hex", stop_check, has_mantra=has_mantra)

                # --- 9. LAW OF SIGNETS ---
                if is_signet_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%equipped signet%' OR description LIKE '%recharge%signets%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Uses Signets", stop_check, has_mantra=has_mantra)
                if is_signet_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Signet') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Signet", stop_check, has_mantra=has_mantra)

                # --- 11. LAW OF HEALING (Unified) ---
                if is_heal_ally or is_heal_cons:
                    # 1. Suggest heal providers (must have 'heal' in description to avoid tag noise like Dark Aura)
                    q_stack = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Healing_Ally') AND description LIKE '%heal%' AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q_stack, list(existing_ids), root, context, synergies, debug_mode, "Healing Synergy", stop_check, has_mantra=has_mantra)
                    
                    # 2. Suggest heal boosters/augments (e.g. Unyielding Aura effects)
                    q_boost = f"SELECT {cols} FROM {table} WHERE (description LIKE '%whenever you heal%' OR description LIKE '%% more health%' OR description LIKE '%healing prayers%' OR description LIKE '%extra health%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q_boost, list(existing_ids), root, context, synergies, debug_mode, "Boosts Healing", stop_check, has_mantra=has_mantra)

                # --- 12. LAW OF CHAINS (Combos) ---
                root_combo = root[9] or 0
                if "lead attack" in root_desc: # Root provides Lead
                    q = f"SELECT {cols} FROM {table} WHERE combo_req = 1 AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Combo: Off-Hand", stop_check, has_mantra=has_mantra)
                elif root_combo == 1: # Root is Off-Hand (provides Off-Hand state)
                    q = f"SELECT {cols} FROM {table} WHERE combo_req = 2 AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Combo: Dual", stop_check, has_mantra=has_mantra)

                # 14. LAW OF DEGENERATION (Entropy)
                if is_degen_prov:
                    pass 
                if is_degen_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Degeneration') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Causes Degeneration", stop_check, has_mantra=has_mantra)

                # --- 13. LAW OF ENERGY (Provides) ---
                if context.energy_management_count < 2 and (context.has_high_cost or context.has_energy_denial):
                    # Trigger if the root skill itself is high cost or energy denial
                    if (root[3] and root[3] >= 15) or 'Type_Energy_Denial' in root_tags:
                        q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Energy_Management') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                        self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Provides Energy", stop_check, has_mantra=has_mantra)

                # 14. LAW OF PHYSICAL ATTACKS
                if is_phys_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%attack skill%') AND description LIKE '%bonus%' AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Boosts Physical", stop_check, has_mantra=has_mantra)
                if is_phys_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Attack_Physical') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Physical Attack", stop_check, has_mantra=has_mantra)

                # 15. LAW OF RANGED ATTACKS
                if is_ranged_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%bow attack%') AND description LIKE '%bonus%' AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Boosts Ranged", stop_check, has_mantra=has_mantra)
                if is_ranged_cons:
                    q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Attack_Ranged') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Ranged Attack", stop_check, has_mantra=has_mantra)

                # --- 18. LAW OF STANCES ---
                if is_stance_prov:
                    # Suggest skills that benefit from stances
                    q_benefit = f"SELECT {cols} FROM {table} WHERE (description LIKE '%while you are in a stance%' OR description LIKE '%while in a stance%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q_benefit, list(existing_ids), root, context, synergies, debug_mode, "Benefits from Stance", stop_check, has_mantra=has_mantra)

                    # Only suggest other stances if we have fewer than 2
                    if stance_count < 2:
                        q = f"SELECT {cols} FROM {table} WHERE skill_id IN (SELECT skill_id FROM skill_tags WHERE tag='Type_Stance') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))}) AND name NOT LIKE 'Mantra%'"
                        self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Stance Choice", stop_check, has_mantra=has_mantra)

                # --- 19. LAW OF PETS ---
                if is_pet_prov:
                    q = f"SELECT {cols} FROM {table} WHERE (description LIKE '%pet%' OR description LIKE '%beast%' OR description LIKE '%companion%') AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                    self._process_matches(conn, q, list(existing_ids), root, context, synergies, debug_mode, "Pet Synergy", stop_check, has_mantra=has_mantra)

                # --- B. CONDITION SEARCH (Semantic) ---
                for cond_key, def_data in CONDITION_DEFINITIONS.items():
                    role = self._check_condition_logic(root_desc, cond_key)
                    
                    if role == "Provider":
                        # Suggest Consumers (Feed on it)
                        for phrase in def_data['consumers']:
                            q = f"SELECT {cols} FROM {table} WHERE description LIKE ? AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                            self._process_matches(conn, q, [f'%{phrase}%'] + list(existing_ids), 
                                               root, context, synergies, debug_mode, f"Feeds on {cond_key.title()}", stop_check, has_mantra=has_mantra)
                                               
                    elif role == "Consumer":
                        # Suggest Providers (Cause it)
                        for phrase in def_data['providers']:
                            q = f"SELECT {cols} FROM {table} WHERE description LIKE ? AND skill_id NOT IN ({','.join(['?']*len(existing_ids))})"
                            self._process_matches(conn, q, [f'%{phrase}%'] + list(existing_ids), 
                                               root, context, synergies, debug_mode, f"Provides {cond_key.title()}", stop_check,
                                               check_negative_context=True, target_cond=cond_key, has_mantra=has_mantra)

        except Exception as e:
            print(f"Physics Engine Error: {e}")
            return []
        finally:
            if 'conn' in locals(): conn.close()

        return synergies

    def _process_matches(self, conn, query, params, root, context, results_list, debug_mode, reason_prefix, stop_check, check_negative_context=False, target_cond="", has_mantra=False):
        matches = conn.execute(query, params).fetchall()
        
        for m in matches:
            if stop_check and stop_check(): return 
            
            # --- GLOBAL MANTRA FILTER ---
            # If we already have a Mantra, do not suggest another one.
            if has_mantra and m[1].lower().startswith("mantra"):
                 continue

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
            
            valid, drain_r = self.check_energy_drain(m, context)
            if not valid: fail_reasons.append(drain_r)
            
            # B. Resource Checks
            stable, phys_r = self.check_resource_stability(root, m, context)
            if not stable: fail_reasons.append(phys_r)

            # C. Output
            if not fail_reasons:
                eff, eff_r = context.calculate_efficiency(m)
                if eff < 0.5: 
                    if debug_mode: results_list.append((m[0], f"[DEBUG: Low Eff] {eff_r}"))
                    continue
                
                reason_str = reason_prefix
                if "⚠️" in phys_r: reason_str += f" | {phys_r}"
                if "⚠️" in drain_r: reason_str += f" | {drain_r}"
                results_list.append((m[0], reason_str))
            
            elif debug_mode:
                reason_str = f"[DEBUG] {', '.join(fail_reasons)}"
                results_list.append((m[0], reason_str))

class SynergyEngine:
    def __init__(self, json_path, db_path):
        self.builds: List[Build] = []
        self.professions = set()
        self.categories = set()
        self.teams = set()
        
        # Initialize the Brain and the Mechanics Validator
        self.brain = SkillBrain(model_path=BEHAVIOR_MODEL_PATH, semantic_path=SEMANTIC_MODEL_PATH)
        self.mechanics = MechanicsEngine(db_path)
        
        self.load_data(json_path)

    def load_data(self, json_path):
        # 1. Load the raw JSON for standard lookups
        seen_builds = set() # (code, team) to prevent duplicates
        
        # Helper to process a JSON file
        def process_file(path, is_user_data=False):
            if not os.path.exists(path): return
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for entry in data:
                        code = entry.get('build_code', '')
                        team = entry.get('team', 'General')
                        
                        if (code, team) in seen_builds:
                            continue
                        seen_builds.add((code, team))

                        attrs = []
                        if code:
                            decoded = GuildWarsTemplateDecoder(code).decode()
                            if decoded:
                                attrs = decoded.get('attributes', [])

                        category = entry.get('category', 'Uncategorized')
                        if category == "SC": category = "Speed Clear"
                        
                        name = entry.get('name', '')

                        # Auto-assign to Mosquito's Teambuild category
                        if "Mosquito" in team or "Mosquito" in name:
                            category = "Mosquito's Teambuild"

                        b = Build(
                            code=code,
                            primary_prof=str(entry.get('primary_profession', 'Unknown')),
                            secondary_prof=str(entry.get('secondary_profession', '')),
                            skill_ids=entry.get('skill_ids', []),
                            category=category,
                            team=team,
                            attributes=attrs,
                            name=name
                        )
                        # Tag user builds so we know where to save them later
                        b.is_user_build = is_user_data
                        
                        self.builds.append(b)
                        self.professions.add(b.primary_prof)
                        self.categories.add(b.category)
                        self.teams.add(b.team)
            except Exception as e:
                print(f"Error loading {path}: {e}")

        # Load User Builds (Writable) - Process these first so they take precedence
        process_file(USER_BUILDS_FILE, is_user_data=True)
        # Load System Builds (Read-Only)
        process_file(json_path, is_user_data=False)

        # 2. TRIGGER AUTO-TRAINING HERE
        # We train the brain using the user builds file so it learns from user additions
        self.brain.train(USER_BUILDS_FILE, self.mechanics.db_path)

    def save_user_builds(self):
        user_data = []
        for b in self.builds:
            if getattr(b, 'is_user_build', False):
                user_data.append({
                    "build_code": b.code,
                    "primary_profession": b.primary_prof,
                    "secondary_profession": b.secondary_prof,
                    "skill_ids": b.skill_ids,
                    "category": b.category,
                    "team": b.team,
                    "name": b.name
                })
        
        try:
            with open(USER_BUILDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, indent=4)
        except Exception as e:
            print(f"Error saving user builds: {e}")

    def get_zone_skills(self, zone_name: str) -> List[Tuple[int, bool]]:
        try:
            conn = sqlite3.connect(self.mechanics.db_path)
            cursor = conn.cursor()
            
            # 1. Get enemies IDs
            cursor.execute("SELECT enemies_ids FROM locations WHERE name = ?", (zone_name,))
            row = cursor.fetchone()
            if not row or not row[0]:
                conn.close()
                return []
            
            enemy_ids_str = row[0].split(',')
            enemy_ids = [int(eid) for eid in enemy_ids_str if eid.strip().isdigit()]
            
            if not enemy_ids:
                conn.close()
                return []
                
            # 2. Get skills from monster builds
            placeholders = ','.join(['?'] * len(enemy_ids))
            query = f"SELECT is_boss, skill_1, skill_2, skill_3, skill_4, skill_5, skill_6, skill_7, skill_8 FROM monster_builds WHERE id IN ({placeholders})"
            cursor.execute(query, enemy_ids)
            
            threat_skills = []
            for row in cursor.fetchall():
                is_boss = bool(row[0])
                skills = row[1:]
                for sid in skills:
                    if sid and sid != 0:
                        threat_skills.append((sid, is_boss))
            
            conn.close()
            return threat_skills
            
        except Exception as e:
            print(f"Error fetching zone skills: {e}")
            return []

    def get_counters(self, zone_name: str) -> List[Tuple[int, float, str]]:
        threat_ids = self.get_zone_skills(zone_name)
        if not threat_ids:
            return []
        return self.mechanics.find_counters(threat_ids)

    def get_zone_summary(self, zone_name: str) -> List[dict]:
        try:
            conn = sqlite3.connect(self.mechanics.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT enemies_ids FROM locations WHERE name = ?", (zone_name,))
            row = cursor.fetchone()
            if not row or not row[0]:
                conn.close()
                return []
            
            enemy_ids = [int(eid) for eid in row[0].split(',') if eid.strip().isdigit()]
            if not enemy_ids:
                conn.close()
                return []

            placeholders = ','.join(['?'] * len(enemy_ids))
            query = f"SELECT monster_name, is_boss, skill_1, skill_2, skill_3, skill_4, skill_5, skill_6, skill_7, skill_8 FROM monster_builds WHERE id IN ({placeholders})"
            cursor.execute(query, enemy_ids)
            
            monsters = []
            for row in cursor.fetchall():
                m_name = row[0]
                is_boss = bool(row[1])
                s_ids = [sid for sid in row[2:] if sid and sid != 0]
                
                # Fetch skill names
                s_names = []
                if s_ids:
                    p_s = ','.join(['?'] * len(s_ids))
                    cursor.execute(f"SELECT name FROM skills WHERE skill_id IN ({p_s})", s_ids)
                    s_names = [r[0] for r in cursor.fetchall()]
                
                monsters.append({
                    "name": m_name,
                    "is_boss": is_boss,
                    "skills": s_names,
                    "skill_ids": s_ids
                })
            
            conn.close()
            return monsters
        except Exception as e:
            print(f"[Engine] Summary Error: {e}")
            return []

    def get_suggestions(self, active_skill_ids: List[int], limit=100, category=None, team=None, min_overlap=None, mode="legacy", is_pre=False, allowed_campaigns=None, is_pvp=False, primary_prof_id=0) -> List[tuple]:
        # ...
        # 1. Cold Start Check
        if not active_skill_ids:
            return []

        # 2. Neural Step
        neural_suggestions = self.brain.suggest(active_skill_ids, top_n=limit, use_semantic=(mode == "smart"))
        print(f"[Engine] Input: {active_skill_ids} | Mode: {mode} | Neural Suggestions: {len(neural_suggestions)}")
        
        if not neural_suggestions:
            return []

        # Restore Context Initialization
        context = BuildState(primary_prof_id) 
        conn = sqlite3.connect(self.mechanics.db_path)
        placeholders = ','.join(['?'] * len(active_skill_ids))
        
        # Fetch tags for active skills
        q_tags = f"SELECT skill_id, tag FROM skill_tags WHERE skill_id IN ({placeholders})"
        cursor = conn.execute(q_tags, active_skill_ids)
        active_tags_map = {}
        for sid, tag in cursor.fetchall():
            if sid not in active_tags_map: active_tags_map[sid] = set()
            active_tags_map[sid].add(tag)

        q = f"SELECT skill_id, name, description, energy_cost, activation, recharge, adrenaline, health_cost, aftercast, combo_req, is_elite, attribute FROM skills WHERE skill_id IN ({placeholders})"
        cursor = conn.execute(q, active_skill_ids)
        active_skills_data = [] # Store full data for stability checks
        for row in cursor.fetchall():
            active_skills_data.append(row)
            context.ingest_skill(row, active_tags_map.get(row[0], set()))
        conn.close()

        # 3. Validation Step (Relaxed)
        conn = sqlite3.connect(self.mechanics.db_path)
        cursor = conn.cursor()
        
        final_results = []
        same_prof_results = []
        other_results = []
        seen_ids = set()
        
        # Cols needed for stability check: id, name, desc, nrg, act, rech, adr, hp, aft, combo, elite, attr
        cols_full = "skill_id, name, description, energy_cost, activation, recharge, adrenaline, health_cost, aftercast, combo_req, is_elite, attribute, profession, in_pre, campaign"

        for sid, score in neural_suggestions:
            if sid in active_skill_ids: continue

            cursor.execute(f"SELECT {cols_full} FROM skills WHERE skill_id = ?", (sid,))
            row = cursor.fetchone()
            
            if row:
                name = row[1]
                prof = row[12]
                # PvP Check: If in PvE mode, skip skills with "(PvP)" in name
                if not is_pvp and "(PvP)" in name:
                    continue
                
                # If PvP mode is ON, swap PvE skills to PvP versions if available
                if is_pvp and "(PvP)" not in name:
                    pvp_name = name + " (PvP)"
                    cursor.execute("SELECT skill_id FROM skills WHERE name = ?", (pvp_name,))
                    pvp_row = cursor.fetchone()
                    if pvp_row:
                        sid = pvp_row[0]
                        # Re-fetch row for the new ID
                        cursor.execute(f"SELECT {cols_full} FROM skills WHERE skill_id = ?", (sid,))
                        row = cursor.fetchone()
                        prof = row[12]

                # Deduplication check
                if sid in seen_ids: continue
                if sid in active_skill_ids: continue
                seen_ids.add(sid)

                # Campaign Filter
                if allowed_campaigns is not None:
                    # 0=Core, 1=Prophecies, 2=Factions, 3=Nightfall, 4=EotN
                    # We always allow Core (0)
                    camp = row[14]
                    if camp != 0 and camp not in allowed_campaigns:
                        continue

            if not row: 
                # Try PvP table fallback?
                # If PvP mode is disabled, do NOT suggest PvP-only skills
                if not is_pvp: continue

                # If Pre-Searing is active, PvP skills are generally invalid unless they exist in Pre (which they should be in 'skills' table then)
                if is_pre: continue 
                
                # PvP table doesn't have all columns, but we need basics
                cursor.execute("SELECT skill_id, name, is_elite, profession FROM skills_pvp WHERE skill_id = ?", (sid,))
                row_pvp = cursor.fetchone()
                if not row_pvp:
                    print(f"[Engine] Dropped ID {sid} (Not found in DB)")
                    continue
                
                if sid in seen_ids: continue
                seen_ids.add(sid)
                prof = row_pvp[3]
                # Construct a fake row with 0s for stats so checks don't crash, but we can't really validate stability
                row = (sid, row_pvp[1], "", 0, 0, 0, 0, 0, 0, 0, row_pvp[2], 0, row_pvp[3], 0, 0)
            else:
                # Check Pre-Searing constraint
                if is_pre and not row[13]:
                    continue

            # Elite Filter: Only show additional elites if bar has >= 3 skills
            is_elite = bool(row[10])
            if is_elite and context.elite_count > 0 and len(active_skill_ids) < 3:
                continue
            
            # --- SAFETY CHECKS (Warnings) ---
            warnings = []
            
            # Check Stability against all active skills
            for active_row in active_skills_data:
                # active_row indices match DB fetch order: 0:id, 1:name ... 3:nrg ... 5:rech ...
                # row indices match cols_full: 0:id, 1:name ... 3:nrg ...
                
                # We need to pass data in the format check_resource_stability expects (db row style)
                # check_resource_stability expects [3]=nrg, [5]=rech, [7]=hp, [4]=act, [8]=aft
                
                stable, phys_r = self.mechanics.check_resource_stability(active_row, row, context)
                if not stable or "⚠️" in phys_r:
                   if phys_r not in warnings: warnings.append(phys_r)

            # Check Energy Drain
            valid, drain_r = self.mechanics.check_energy_drain(row, context)
            if not valid or "⚠️" in drain_r:
                if drain_r not in warnings: warnings.append(drain_r)

            # Construct Result
            reason_str = ""
            if warnings:
                reason_str = " | ".join(warnings)
            
            # Prioritization Logic: Separate same-profession from others
            if primary_prof_id > 0 and prof == primary_prof_id:
                same_prof_results.append((sid, score, reason_str))
            else:
                other_results.append((sid, score, reason_str))

        # Re-combine: Same profession first
        final_results = same_prof_results + other_results
            
        # 4. Basic Needs Injection (Smart Mode Only)
        # We only inject basic needs if the AI didn't already provide enough of them
        if mode == "smart":
            current_ids = {item[0] for item in final_results}
            basic_needs = self.mechanics.get_basic_needs_suggestions(context, is_pre=is_pre)
            
            # Inject basic needs with a slightly higher priority but limited count
            # This ensures builds have a heal/energy if missing, without flooding.
            added_needs = 0
            for sid, score, reason in basic_needs:
                if sid not in current_ids and sid not in active_skill_ids:
                    # PvP/PvE Check
                    cursor.execute("SELECT name FROM skills WHERE skill_id = ?", (sid,))
                    row_check = cursor.fetchone()
                    if row_check:
                        if not is_pvp and "(PvP)" in row_check[0]: continue
                    elif not is_pvp:
                        continue

                    # Append to the end so AI suggestions remain prioritized at the top
                    final_results.append((sid, score, reason))
                    current_ids.add(sid)
                    added_needs += 1
                    if added_needs >= 3: break

        # 5. Final Filtering (Limits)
        filtered_final = []
        elite_count = 0
        self_heal_count = 0
        
        # Determine limits based on remaining slots
        open_slots = 8 - len(active_skill_ids)
        limit_elite = 1 if (open_slots <= 4 or context.elite_count > 0) else 2
        limit_heal = 1 if open_slots <= 4 else 2
        
        for item in final_results:
            sid = item[0]
            score = item[1]
            reason = item[2] if len(item) > 2 else ""

            # Check Elite Status
            cursor.execute("SELECT is_elite FROM skills WHERE skill_id = ?", (sid,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT is_elite FROM skills_pvp WHERE skill_id = ?", (sid,))
                row = cursor.fetchone()

            is_elite = bool(row[0]) if row else False

            if is_elite:
                if elite_count >= limit_elite: continue
                elite_count += 1

            if reason == "Missing Self Heal":
                if self_heal_count >= limit_heal: continue
                self_heal_count += 1

            filtered_final.append(item)

        final_results = filtered_final
        conn.close()
        print(f"[Engine] Final Results: {len(final_results)}")
        return final_results

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