import sqlite3
from typing import List, Optional
from src.models import Skill

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
