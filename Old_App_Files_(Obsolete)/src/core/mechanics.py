import os
from typing import Dict, Callable, Any

# Standard Level 20 Base Health for all professions
BASE_HEALTH = 480

# Profession Base Stats (at level 20)
# format: { prof_id: (base_energy, energy_regen_pips) }
PROF_BASE_STATS = {
    0:  (20, 2), # Default
    1:  (20, 2), # Warrior
    2:  (20, 4), # Ranger
    3:  (30, 4), # Monk
    4:  (30, 4), # Necromancer
    5:  (30, 4), # Mesmer
    6:  (30, 4), # Elementalist
    7:  (20, 4), # Assassin
    8:  (30, 4), # Ritualist
    9:  (20, 4), # Paragon
    10: (25, 4)  # Dervish
}

def get_crit_strikes_energy(rank: int) -> int:
    if rank <= 2: return 0
    if rank <= 7: return 1
    if rank <= 12: return 2
    if rank <= 17: return 3
    return 4

def get_leadership_energy(rank: int) -> int:
    if rank >= 20: return 10
    return rank // 2

class AttributeBonus:
    def __init__(self, name: str, value_func: Callable[[int], Any], desc_formatter: Callable[[Any, int], str]):
        self.name = name
        self.value_func = value_func
        self.desc_formatter = desc_formatter

    def get_value(self, rank: int) -> Any:
        return self.value_func(rank)

    def get_description(self, rank: int) -> str:
        val = self.get_value(rank)
        return self.desc_formatter(val, rank)

# Mapping of Attribute ID to its Primary Bonus logic
PRIMARY_ATTRIBUTE_DATA: Dict[int, AttributeBonus] = {
    17: AttributeBonus("Strength", lambda r: r, lambda v, r: f"{v}% armor penetration on attack skills"),
    23: AttributeBonus("Expertise", lambda r: r * 4, lambda v, r: f"-{v}% energy cost for Ranger skills"),
    16: AttributeBonus("Divine Favor", lambda r: r * 3.2, lambda v, r: f"+{v:.1f} healing when casting spells on allies"),
    6:  AttributeBonus("Soul Reaping", lambda r: r, lambda v, r: f"Gain {v} energy whenever a nearby creature dies"),
    0:  AttributeBonus("Fast Casting", lambda r: r, lambda v, r: f"Mesmer spells cast {v * 4.73:.1f}% faster and recharge {v * 3}% faster"),
    12: AttributeBonus("Energy Storage", lambda r: r * 3, lambda v, r: f"+{v} maximum energy"),
    35: AttributeBonus("Critical Strikes", get_crit_strikes_energy, lambda v, r: f"+{r}% critical hit chance. Gain {v} energy per critical hit"),
    36: AttributeBonus("Spawning Power", lambda r: r * 0.04, lambda v, r: f"Spirits have {int(v*100)}% extra health, weapon spells last {int(v*100)}% longer"),
    40: AttributeBonus("Leadership", get_leadership_energy, lambda v, r: f"Up to {v} energy gained from shouts/chants"),
    44: AttributeBonus("Mysticism", lambda r: r, lambda v, r: f"-{v * 4}% energy cost for Dervish enchantments, +{v} armor while enchanted")
}

def get_primary_bonus_description(attr_id: int, rank: int) -> str:
    if attr_id in PRIMARY_ATTRIBUTE_DATA:
        return PRIMARY_ATTRIBUTE_DATA[attr_id].get_description(rank)
    return ""

def get_primary_bonus_value(attr_id: int, rank: int) -> Any:
    if attr_id in PRIMARY_ATTRIBUTE_DATA:
        return PRIMARY_ATTRIBUTE_DATA[attr_id].get_value(rank)
    return 0