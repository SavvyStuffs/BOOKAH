from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QScrollArea, QWidget, QGridLayout, QComboBox
from PyQt6.QtCore import pyqtSignal
from src.constants import ATTR_MAP, PROF_PRIMARY_ATTR
from src.models import Skill
from typing import List

class AttributeEditor(QFrame):
    """
    GUI Panel for managing attribute point distribution.
    Shows attributes for the current primary/secondary professions.
    """
    attributes_changed = pyqtSignal(dict) # Emits {attr_id: rank}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333; border-radius: 4px;")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(2)
        
        self.title = QLabel("Attributes (0/200)")
        self.title.setStyleSheet("font-weight: bold; color: #aaa; border: none;")
        self.layout.addWidget(self.title)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none;")
        self.scroll_content = QWidget()
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.scroll.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll)
        
        self.attr_widgets = {} # {attr_id: (label, spinbox)}
        self.current_points = 0
        self.max_points = 200
        self.current_distribution = {} # {attr_id: rank}
        
        # Mapping of profession to its attributes
        self.PROF_ATTRS = {
            1: [17, 18, 19, 20, 21],          # Warrior: Strength, Axe, Hammer, Sword, Tactics
            2: [22, 23, 24, 25],              # Ranger: Beast, Expertise, Wild, Marks
            3: [13, 14, 15, 16],              # Monk: Heal, Smiting, Prot, Divine
            4: [4, 5, 6, 7],                  # Necro: Blood, Death, Soul, Curses
            5: [0, 1, 2, 3],                  # Mesmer: Fast, Illusion, Dom, Insp
            6: [8, 9, 10, 11, 12],            # Ele: Air, Earth, Fire, Water, Energy
            7: [29, 30, 31, 35],              # Assassin: Dagger, Deadly, Shadow, Critical
            8: [32, 33, 34, 36],              # Ritualist: Communing, Resto, Chan, Spawning
            9: [37, 38, 39, 40],              # Paragon: Spear, Command, Motiv, Leadership
            10: [41, 42, 43, 44]              # Dervish: Scythe, Wind, Earth, Mysticism
        }

    def set_professions(self, primary_id, secondary_id, active_skills: List[Skill] = None):
        # Clear existing widgets
        for i in reversed(range(self.grid.count())): 
            self.grid.itemAt(i).widget().setParent(None)
        self.attr_widgets.clear()
        
        relevant_attrs = []
        if primary_id in self.PROF_ATTRS:
            relevant_attrs.extend(self.PROF_ATTRS[primary_id])
        if secondary_id in self.PROF_ATTRS:
            # Add secondary attrs, skipping duplicates
            for aid in self.PROF_ATTRS[secondary_id]:
                if aid not in relevant_attrs:
                    is_primary_of_another = False
                    for pid, primary_aid in PROF_PRIMARY_ATTR.items():
                        if aid == primary_aid and pid != secondary_id:
                            is_primary_of_another = True
                            break
                    
                    if not is_primary_of_another:
                        relevant_attrs.append(aid)
        
        # Check for PvE attributes (negative IDs) in active skills
        if active_skills:
            for s in active_skills:
                if s.attribute < 0 and s.attribute != -1: # -1 is None
                    if s.attribute not in relevant_attrs:
                        relevant_attrs.append(s.attribute)

        # Sort: Standard attributes first (by name), then PvE attributes
        # ATTR_MAP has names for negatives now
        
        # Split into standard and pve
        std_attrs = [a for a in relevant_attrs if a >= 0]
        pve_attrs = [a for a in relevant_attrs if a < 0]
        
        std_attrs.sort(key=lambda x: ATTR_MAP.get(x, ""))
        pve_attrs.sort(key=lambda x: ATTR_MAP.get(x, ""))
        
        final_attrs = std_attrs + pve_attrs
        
        for row, aid in enumerate(final_attrs):
            name = ATTR_MAP.get(aid, f"Attr {aid}")
            lbl = QLabel(name)
            lbl.setStyleSheet("color: #ccc; font-size: 11px; border: none;")
            
            spin = QComboBox()
            
            # Range: 0-12 for standard, 0-10 for PvE
            limit = 12 if aid >= 0 else 10
            spin.addItems([str(i) for i in range(limit + 1)])
            
            spin.setFixedWidth(45)
            spin.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
            
            # Set previous value if it existed
            prev_val = self.current_distribution.get(aid, 0)
            spin.setCurrentIndex(min(prev_val, limit))
            
            spin.currentIndexChanged.connect(lambda _, a=aid: self._on_attr_changed(a))
            
            # Highlight PvE attributes
            if aid < 0:
                lbl.setStyleSheet("color: #FFAA00; font-size: 11px; border: none; font-weight: bold;")
            
            self.grid.addWidget(lbl, row, 0)
            self.grid.addWidget(spin, row, 1)
            self.attr_widgets[aid] = (lbl, spin)
            
        self._update_total()

    def _on_attr_changed(self, attr_id):
        val = int(self.attr_widgets[attr_id][1].currentText())
        self.current_distribution[attr_id] = val
        self._update_total()
        self.attributes_changed.emit(self.current_distribution)

    def _update_total(self):
        # Calculate point cost (GW formula)
        costs = [0, 1, 3, 6, 10, 15, 21, 28, 37, 48, 61, 77, 97]
        
        total = 0
        for aid, (lbl, spin) in self.attr_widgets.items():
            if aid < 0: continue # PvE attributes cost 0 points
            
            rank = int(spin.currentText())
            if rank < len(costs):
                total += costs[rank]
        
        self.current_points = total
        self.title.setText(f"Attributes ({total}/{self.max_points})")
        
        if total > self.max_points:
            self.title.setStyleSheet("font-weight: bold; color: #ff5555; border: none;")
        else:
            self.title.setStyleSheet("font-weight: bold; color: #aaa; border: none;")

    def get_distribution(self):
        return {aid: int(spin.currentText()) for aid, (lbl, spin) in self.attr_widgets.items()}
    
    def set_distribution(self, dist):
        self.current_distribution = dist
        for aid, rank in dist.items():
            if aid in self.attr_widgets:
                self.attr_widgets[aid][1].setCurrentIndex(min(rank, 12))
        self._update_total()
