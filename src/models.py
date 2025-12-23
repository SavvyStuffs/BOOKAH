from dataclasses import dataclass, field
from typing import List
from src.constants import PROF_MAP, ATTR_MAP

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
            val_10 = safe_int(stat[12]) # PvE Max Rank
            val_15 = safe_int(stat[17]) # PvP/Standard Max
            val_21 = safe_int(stat[23]) # Overcap Max
            
            val_target = safe_int(stat[2 + rank]) # rank 0 is at index 2
            
            # Prepare replacement string with blue color
            replacement = f'<span style="color: #55AAFF;">{val_target}</span>'
            
            # Candidate patterns to look for
            patterns = []
            
            # 1. Range patterns (e.g. 5..100)
            if val_0 != val_15 and val_15 != 0: patterns.append(f"{val_0}..{val_15}")
            if val_0 != val_10 and val_10 != 0: patterns.append(f"{val_0}..{val_10}")
            if val_0 != val_21 and val_21 != 0: patterns.append(f"{val_0}..{val_21}")
            
            # 2. Single value pattern (e.g. 5)
            # Only if it's a fixed value across ranks? 
            # Or if the text just says "5" but it actually scales?
            # Standard descriptions usually show the range if it scales. 
            # But sometimes it says "5" and that 5 scales.
            patterns.append(str(val_0))
            
            # Apply first match
            for pat in patterns:
                if pat in current_desc:
                    current_desc = current_desc.replace(pat, replacement, 1)
                    break
                    
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
