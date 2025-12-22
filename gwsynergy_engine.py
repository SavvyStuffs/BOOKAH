import sqlite3
import pandas as pd

class SynergyEngine:
    def __init__(self, db_path='master.db', mode='pve'):
        self.conn = sqlite3.connect(db_path)
        self.mode = mode
        self.table = "skills_pvp" if mode.lower() == 'pvp' else "skills"
        
        # --- THE RULEBOOK ---
        # This defines "Why" skills work together.
        # Format: 'Tag': {'role': 'Generator/Consumer', 'seek': 'Target_Tag'}
        self.RULES = {
            # Condition: Burning
            'Condition_Burning':   {'role': 'Generator', 'seek': 'Condition_Burning', 'match_type': 'Consumer'}, 
            # Note: We need to distinguish between "Causes Burning" (Generator) vs "Bonus vs Burning" (Consumer)
            # Currently our regex just tagged both as "Condition_Burning". 
            # For V1, we will look for specific "Trigger" mechanics in the description dynamically.
        }

    def _get_skill_data(self, skill_name):
        """Fetches raw data + physics stats for a skill."""
        query = f"""
            SELECT skill_id, name, description, energy_cost, activation, aftercast, recharge, profession 
            FROM {self.table} WHERE name = ? COLLATE NOCASE
        """
        cursor = self.conn.execute(query, (skill_name,))
        return cursor.fetchone()

    def _get_tags(self, skill_id):
        """Fetches the tags we generated."""
        return [r[0] for r in self.conn.execute("SELECT tag FROM skill_tags WHERE skill_id = ?", (skill_id,))]

    def check_hamiltonian_stability(self, skill_a, skill_b):
        """
        The Physics Check.
        Input: Tuple (Energy, Act, After, Rech) for both skills.
        Returns: (Boolean Is_Viable, String Reason)
        """
        # Unpack Data (Energy, Activation, Aftercast, Recharge)
        # Note: skill_data format from query is indices 3, 4, 5, 6
        e_a, act_a, aft_a, rech_a = skill_a[3], skill_a[4], skill_a[5], skill_a[6]
        e_b, act_b, aft_b, rech_b = skill_b[3], skill_b[4], skill_b[5], skill_b[6]

        # 1. Energy Horizon (Simple Model)
        # Can we cast both without hitting 0 from a neutral state? 
        # (Assuming Base 25 Energy for caster)
        total_cost = e_a + e_b
        if total_cost > 25: 
            return False, f"Energy Spike too high ({total_cost}e > 25e base)"

        # 2. Time Horizon (The Loop)
        # Does the combo fit efficiently?
        # If Skill A has a short recharge, can we cast B before A is ready again?
        combo_time = act_a + aft_a + act_b + aft_b
        
        # If Skill A recharges faster than we can cast B, it's inefficient (clipping)
        # But not "Impossible". 
        
        return True, "Stable"

    def find_synergies(self, input_name):
        print(f"\n--- Analyzing [{input_name}] ({self.mode.upper()}) ---")
        
        # 1. Get Input Skill
        root = self._get_skill_data(input_name)
        if not root:
            print(f"Skill '{input_name}' not found in {self.table}.")
            return
            
        root_id, root_name, root_desc, root_nrg, root_act, root_aft, root_rech, root_prof = root
        tags = self._get_tags(root_id)
        
        print(f"Mechanics Identified: {tags}")
        
        # 2. Determine Logic Path
        # We parse the description to see what it NEEDS vs what it GIVES
        candidates = []
        
        # LOGIC: CONDITION SYNERGY
        # If I cause a condition, look for things that exploit it.
        conditions = ['Burning', 'Bleeding', 'Dazed', 'Deep Wound', 'Weakness', 'Poison']
        
        for cond in conditions:
            # Am I a Generator?
            if cond in root_desc and "target" in root_desc.lower(): 
                # Loose logic: If description mentions the condition and a target, I likely apply it.
                print(f" -> Role: GENERATOR of {cond}. Looking for CONSUMERS...")
                
                # Query: Find skills that say "if target is {cond}" or "bonus damage... {cond}"
                q = f"""
                    SELECT name, description, energy_cost, activation, aftercast, recharge
                    FROM {self.table}
                    WHERE description LIKE '%{cond}%' 
                    AND (description LIKE '%bonus%' OR description LIKE '%additional%')
                    AND name != ?
                """
                matches = self.conn.execute(q, (root_name,)).fetchall()
                for m in matches:
                    # Run Physics Check
                    viable, reason = self.check_hamiltonian_stability(root, (0,0,0,) + m[2:]) # Hacky tuple merge
                    if viable:
                        candidates.append({
                            'Skill': m[0],
                            'Synergy': f"Consumes {cond}",
                            'Physics': reason
                        })

            # Am I a Consumer?
            if cond in root_desc and ("bonus" in root_desc.lower() or "additional" in root_desc.lower()):
                 print(f" -> Role: CONSUMER of {cond}. Looking for GENERATORS...")
                 # Query: Find skills that apply it
                 q = f"""
                    SELECT name, description, energy_cost, activation, aftercast, recharge
                    FROM {self.table}
                    WHERE description LIKE '%{cond}%'
                    AND description NOT LIKE '%bonus%'
                    AND name != ?
                """
                 matches = self.conn.execute(q, (root_name,)).fetchall()
                 for m in matches:
                     viable, reason = self.check_hamiltonian_stability(root, (0,0,0,) + m[2:])
                     if viable:
                        candidates.append({
                            'Skill': m[0],
                            'Synergy': f"Generates {cond}",
                            'Physics': reason
                        })

        # 3. Output Results
        if candidates:
            df = pd.DataFrame(candidates)
            print("\n" + df.to_string(index=False))
        else:
            print("No high-confidence synergies found.")

# --- RUNNER ---
if __name__ == "__main__":
    engine = SynergyEngine(mode='pve')
    
    # Test 1: The Classic "Fire Magic" Check
    # Fireball causes Burning (Generator) -> Should suggest things that like Burning
    engine.find_synergies("Fireball")
    
    # Test 2: The "Hammer" Check
    # Irresistible Blow (Consumer of Knockdown) -> Should suggest Knockdowns
    engine.find_synergies("Irresistible Blow")