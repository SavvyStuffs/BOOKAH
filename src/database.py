import sqlite3
from typing import List, Optional
from src.models import Skill
from src.constants import AQ_DB_FILE

class SkillRepository:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._cache = {}

    def get_skill_acquisition(self, skill_id: int) -> dict:
        try:
            with sqlite3.connect(AQ_DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT quests, trainers, hero_trainers, capture, campaign FROM skill_acquisition WHERE skill_id=?", (skill_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "quests": row[0],
                        "trainers": row[1],
                        "hero_trainers": row[2],
                        "capture": row[3],
                        "campaign": row[4]
                    }
        except Exception as e:
            print(f"Error fetching acquisition for {skill_id}: {e}")
        return {}

    def get_skill(self, skill_id: int, is_pvp: bool = False) -> Optional[Skill]:
        cache_key = (skill_id, is_pvp)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # We always want is_pve_only from the main 'skills' table because 'skills_pvp' 
        # often has incorrect or missing data for that specific field.
        if is_pvp:
            query_full = """
                SELECT p.skill_id, p.name, p.profession, p.attribute, 
                       p.energy_cost, p.activation, p.recharge, p.adrenaline, s.is_pve_only,
                       p.description, p.is_elite,
                       s.health_cost, s.aftercast, s.combo_req, s.is_touch, s.campaign, s.in_pre
                FROM skills_pvp p
                JOIN skills s ON p.skill_id = s.skill_id
                WHERE p.skill_id=?
            """
        else:
            query_full = """
                SELECT skill_id, name, profession, attribute, 
                       energy_cost, activation, recharge, adrenaline, is_pve_only,
                       description, is_elite,
                       health_cost, aftercast, combo_req, is_touch, campaign, in_pre
                FROM skills
                WHERE skill_id=?
            """
        
        try:
            self.cursor.execute(query_full, (skill_id,))
            row = self.cursor.fetchone()
            
            if row:
                return self._create_skill_object(row, is_pvp, cache_key)
                
        except sqlite3.OperationalError:
            # FALLBACK: The tables might be missing some columns (older DB versions)
            if is_pvp:
                return self._fetch_hybrid_skill(skill_id, cache_key)
            else:
                print(f"Critical DB Error: Main 'skills' table corrupted or missing columns.")
                
        return None

    def _fetch_hybrid_skill(self, skill_id, cache_key):
        """
        Fetches Text/Basic Stats from PvP table (for UI),
        but fills missing Physics Data from PvE table (for Engine).
        """
        # A. Get Display Data from PvP Table (Safe Columns Only)
        # Note: We skip is_pve_only here and get it from the main table instead.
        query_safe = """
            SELECT skill_id, name, profession, attribute, 
                   energy_cost, activation, recharge, adrenaline,
                   description, is_elite
            FROM skills_pvp
            WHERE skill_id=?
        """
        self.cursor.execute(query_safe, (skill_id,))
        pvp_row = self.cursor.fetchone()
        
        if not pvp_row:
            return None
            
        # B. Get Missing Physics Data and correct is_pve_only from Main Skills Table
        query_phys = """
            SELECT health_cost, aftercast, combo_req, is_touch, campaign, in_pre, is_pve_only
            FROM skills
            WHERE skill_id=?
        """
        self.cursor.execute(query_phys, (skill_id,))
        phys_row = self.cursor.fetchone()
        
        # Fallback if somehow main table is missing it too
        # Index map for phys_row: 0:hp, 1:after, 2:combo, 3:touch, 4:camp, 5:pre, 6:pve_only
        phys_data = phys_row if phys_row else (0, 0.75, 0, 0, 0, 0, 0)
        
        # Re-stitch row for _create_skill_object
        # Expected order: 
        # 0:id, 1:name, 2:prof, 3:attr, 4:nrg, 5:act, 6:rech, 7:adr, 8:pve_only, 9:desc, 10:elite,
        # 11:hp, 12:after, 13:combo, 14:touch, 15:camp, 16:pre
        merged_row = [
            pvp_row[0], pvp_row[1], pvp_row[2], pvp_row[3], pvp_row[4], 
            pvp_row[5], pvp_row[6], pvp_row[7], phys_data[6], pvp_row[8], pvp_row[9],
            phys_data[0], phys_data[1], phys_data[2], phys_data[3], phys_data[4], phys_data[5]
        ]
        
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
        try:
            if is_pvp:
                # We join with 'skills' to filter out PvE-only skills at the database level.
                # Only return skills that are in 'skills_pvp' AND are NOT marked as PvE-only in the main table.
                query = "SELECT p.skill_id FROM skills_pvp p JOIN skills s ON p.skill_id = s.skill_id WHERE s.is_pve_only = 0"
            else:
                query = "SELECT skill_id FROM skills"
            
            self.cursor.execute(query)
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error in get_all_skill_ids: {e}")
            return []
