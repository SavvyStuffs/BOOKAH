import sqlite3
import json
import collections
from typing import List, Set
from collections import Counter
from src.utils import GuildWarsTemplateDecoder
from src.models import Build

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

                # 13. LAW OF ENERGY (Duplicate numbering in original)
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
        
        # --- NEW LOGIC: Dynamic Threshold ---
        # 1. Try strict threshold (>= 10 matches)
        strict_candidates = [sid for sid, count in counter.items() if count >= 10]
        
        final_candidates = []
        if len(strict_candidates) >= 10:
            final_candidates = strict_candidates
        else:
            # 2. Fallback to lenient threshold (>= 2 matches)
            # This ensures we see suggestions even if data is sparse, but avoids 1-off noise
            final_candidates = [sid for sid, count in counter.items() if count >= 2]
            
        # Sort by frequency (descending)
        # We manually sort because we filtered the keys, so most_common usage is slightly different
        sorted_candidates = sorted(final_candidates, key=lambda sid: counter[sid], reverse=True)
        
        results = []
        for sid in sorted_candidates[:limit]:
            results.append((sid, counter[sid] / total_matches))
            
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
