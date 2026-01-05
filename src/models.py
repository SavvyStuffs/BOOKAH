from dataclasses import dataclass, field
from typing import List
from src.constants import PROF_MAP, ATTR_MAP
from src.core.mechanics import get_primary_bonus_value

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
    tags: List[str] = field(default_factory=list)
    skill_type: str = ""
    original_description: str = ""

    def __post_init__(self):
        if not self.original_description:
            self.original_description = self.description

    def get_profession_str(self):
        return PROF_MAP.get(self.profession, f"Unknown ({self.profession})")

    def get_attribute_str(self):
        if self.attribute == -1: return "None"
        return ATTR_MAP.get(self.attribute, f"Unknown ({self.attribute})")

    def get_effective_energy(self, rank: int, bonuses: dict = None) -> int:
        cost = self.energy
        reduction = 0.0
        
        if bonuses:
            # Expertise Logic
            if "Expertise" in bonuses:
                stype = self.skill_type.lower()
                is_exp_applicable = False
                
                if self.profession == 2: # Ranger
                    is_exp_applicable = True
                elif "touch" in stype:
                    is_exp_applicable = True
                elif "attack" in stype:
                    is_exp_applicable = True
                elif "nature ritual" in stype or "binding ritual" in stype:
                    is_exp_applicable = True
                
                if is_exp_applicable:
                    reduction = max(reduction, bonuses.get("Expertise", 0.0) / 100.0)

            # Mysticism: Dervish enchantments
            if self.profession == 10 and "Mysticism" in bonuses:
                if "type_enchantment" in self.tags or "type_form" in self.tags:
                    reduction = max(reduction, bonuses.get("Mysticism", 0.0) * 0.04)
                
        if reduction > 0:
            cost = round(cost * (1.0 - reduction))
            
        return max(0, cost)

    def get_effective_activation(self, rank: int, bonuses: dict = None, global_mod: float = 0.0) -> float:
        act = self.activation
        
        fc_factor = 0.0
        # Fast Casting Logic
        if bonuses and "Fast Casting" in bonuses:
            fc_val = bonuses["Fast Casting"]
            should_apply = False
            # 1. Mesmer Skills
            if self.profession == 5:
                should_apply = True
            # 2. Non-Mesmer Skills (Only Spells/Signets >= 2s)
            else:
                stype = self.skill_type.lower()
                if ("spell" in stype or "signet" in stype) and self.activation >= 2.0:
                    should_apply = True
            
            if should_apply:
                fc_factor = fc_val * 0.0473

        if fc_factor > 0.25:
            # High Fast Casting benefit overrides global consumables
            act = act / (1.0 + fc_factor)
        else:
            # Apply Global modifiers first, then Fast Casting
            if global_mod != 0:
                act = act * (1.0 - abs(global_mod))
            
            if fc_factor > 0:
                act = act / (1.0 + fc_factor)

        return round(act, 3)

    def get_effective_recharge(self, rank: int, bonuses: dict = None, global_mod: float = 0.0) -> float:
        rech = self.recharge
        reduction = 0.0
        
        fc_reduction = 0.0
        # Fast Casting Logic: Recharge reduced by 3% per rank
        if bonuses and "Fast Casting" in bonuses and self.profession == 5:
             fc_reduction = bonuses["Fast Casting"] * 0.03
        
        if fc_reduction > 0.25:
            reduction = fc_reduction
        else:
            reduction = fc_reduction
            if global_mod != 0:
                reduction += abs(global_mod)
        
        if reduction > 0:
            rech = rech * (1.0 - reduction)
            
        return round(rech, 1)

    def get_description_for_rank(self, rank: int, bonuses: dict = None) -> str:
        """
        Dynamically substitutes variables in the description based on the provided attribute rank.
        Uses self.stats to find patterns and values. Also applies primary attribute bonuses.
        """
        if not self.stats:
            return self.description
            
        # Ensure rank is within bounds (0-21)
        rank = max(0, min(rank, 21))
        
        # Start with the ORIGINAL description, not the potentially already modified one
        current_desc = self.original_description
        
        for stat in self.stats:
            stat_name = stat[1]
            
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
            
            # --- APPLY PRIMARY BONUS ---
            effective_val = val_target
            bonus_suffix = ""
            desc_lower = self.description.lower()
            
            # Divine Favor (Monk): Only applies to "Heal" stats (ignore generic Health sacrifice)
            df_bonus = bonuses.get("Divine Favor", 0.0) if bonuses else 0.0
            if df_bonus > 0 and self.profession == 3 and "heal" in stat_name.lower():
                effective_val = int(effective_val + df_bonus)
                bonus_suffix = f" <span style='color:#00FF00; font-size:10px;'>(+{df_bonus:.0f})</span>"
            
            # Spawning Power (Ritualist):
            sp_bonus = bonuses.get("Spawning Power", 0.0) if bonuses else 0.0
            if sp_bonus > 0 and self.profession == 8:
                apply_sp = False
                # 1. Weapon Spell Duration
                if "duration" in stat_name.lower() and "weapon spell" in desc_lower:
                    apply_sp = True
                # 2. Spirit Health
                elif "health" in stat_name.lower() and "spirit" in desc_lower:
                    apply_sp = True
                    
                if apply_sp:
                    effective_val = int(effective_val * (1 + sp_bonus))
                    bonus_suffix = f" <span style='color:#00FF00; font-size:10px;'>(+{int(sp_bonus*100)}%)</span>"
            
            # Prepare replacement string with blue color
            replacement = f'<span style="color: #55AAFF;">{effective_val}</span>{bonus_suffix}'
            
            # Candidate patterns to look for
            patterns = []
            
            # 1. Range patterns (e.g. 5..100)
            if val_0 != val_15 and val_15 != 0: patterns.append(f"{val_0}..{val_15}")
            if val_0 != val_10 and val_10 != 0: patterns.append(f"{val_0}..{val_10}")
            if val_0 != val_21 and val_21 != 0: patterns.append(f"{val_0}..{val_21}")
            
            # 2. Single value pattern (e.g. 5)
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
    name: str = ""
    url: str = ""
