import sqlite3
from typing import List, Optional
from src.models import Skill
from src.constants import AQ_DB_FILE
try:
    from src.pvp_mapping import PVE_TO_PVP_MAP
    PVP_TO_PVE_MAP = {v: k for k, v in PVE_TO_PVP_MAP.items()}
except ImportError:
    PVE_TO_PVP_MAP = {}
    PVP_TO_PVE_MAP = {}

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
        
        target_id = skill_id
        if is_pvp:
            # Map PvE ID to PvP ID if a variant exists
            if skill_id in PVE_TO_PVP_MAP:
                target_id = PVE_TO_PVP_MAP[skill_id]
        
        # Query main skills table for everything
        query_full = """
            SELECT skill_id, name, profession, attribute, 
                   energy_cost, activation, recharge, adrenaline, is_pve_only,
                   description, is_elite,
                   health_cost, aftercast, combo_req, is_touch, campaign, in_pre, skill_type
            FROM skills
            WHERE skill_id=?
        """
        
        try:
            self.cursor.execute(query_full, (target_id,))
            row = self.cursor.fetchone()
            
            if row:
                return self._create_skill_object(row, is_pvp, cache_key)
                
        except sqlite3.OperationalError as e:
            print(f"Critical DB Error: {e}")
                
        return None

    def _create_skill_object(self, row, is_pvp, cache_key):
        skill_id = row[0]
        icon_id = PVP_TO_PVE_MAP.get(skill_id, skill_id)
        
        skill = Skill(
            id=skill_id, 
            name=row[1], 
            icon_filename=f"{icon_id}.jpg", 
            profession=int(row[2] or 0),
            attribute=int(row[3] if row[3] is not None else -1),
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
            in_pre=bool(row[16]),
            skill_type=str(row[17] or "")
        )
        
        # Load stats if available
        try:
            q_stats = "SELECT * FROM skill_stats2 WHERE skill_id=? ORDER BY variable_index"
            self.cursor.execute(q_stats, (skill.id,))
            stats = self.cursor.fetchall()
            skill.stats = stats

            # Load tags
            q_tags = "SELECT tag FROM skill_tags WHERE skill_id=?"
            self.cursor.execute(q_tags, (skill.id,))
            tags = [r[0].lower() for r in self.cursor.fetchall()]
            skill.tags = tags
        except Exception as e:
            print(f"Error loading stats/tags for skill {skill.id}: {e}")
            
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
                # Exclude PvE-only skills
                query = "SELECT skill_id FROM skills WHERE is_pve_only = 0"
            else:
                # Include everything? Or exclude PvP-only IDs?
                # PvE mode should ideally NOT show the unique PvP IDs (e.g. 2895)
                # because they are variants of the main ID (2005).
                # But we don't have an is_pvp_only flag.
                # We can filter out IDs that are VALUES in PVE_TO_PVP_MAP.
                query = "SELECT skill_id FROM skills"
            
            self.cursor.execute(query)
            all_ids = [row[0] for row in self.cursor.fetchall()]
            
            # Filter out PvP-only IDs so we don't duplicate them in the list.
            # We always keep the PvE ID as the key, and get_skill handles the swap.
            pvp_variant_ids = set(PVE_TO_PVP_MAP.values())
            all_ids = [sid for sid in all_ids if sid not in pvp_variant_ids]
                
            return all_ids
        except Exception as e:
            print(f"Error in get_all_skill_ids: {e}")
            return []