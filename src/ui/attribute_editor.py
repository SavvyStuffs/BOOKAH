from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QScrollArea, QWidget, QGridLayout, QComboBox, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt
from src.constants import ATTR_MAP, PROF_PRIMARY_ATTR, PROF_ATTRS
from src.models import Skill
from src.ui.theme import get_color
from src.core.mechanics import get_primary_bonus_description
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
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(2)
        
        # Title Layout with HR Bonus
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)
        
        self.title = QLabel("Atts (0/200)")
        title_layout.addWidget(self.title)
        
        title_layout.addStretch()
        
        lbl_hr = QLabel("HR Bonus:")
        lbl_hr.setStyleSheet(f"font-size: 10px; color: {get_color('text_primary')};")
        title_layout.addWidget(lbl_hr)
        
        self.hr_combo = QComboBox()
        self.hr_combo.addItems([str(i) for i in range(5)])
        self.hr_combo.setFixedWidth(35)
        self.hr_combo.setStyleSheet(f"""
            QComboBox {{ 
                background-color: {get_color('btn_bg')}; 
                color: {get_color('btn_text')}; 
                border: 1px solid {get_color('slot_border')}; 
                padding-left: 2px;
                font-size: 10px;
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
        """)
        self.hr_combo.currentIndexChanged.connect(self._on_hr_changed)
        title_layout.addWidget(self.hr_combo)
        
        self.layout.addLayout(title_layout)
        
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
        self.primary_id = 0
        self.hr_bonus = 0
        
        self.refresh_theme()

    def _on_hr_changed(self, index):
        self.hr_bonus = index
        self._update_total() # Recalculate if needed, mainly for UI updates
        # Emit signal so Main Window recalculates effective stats
        self.attributes_changed.emit(self.current_distribution)

    def get_hr_bonus(self):
        return self.hr_bonus

    def refresh_theme(self):
        self.setStyleSheet(f"background-color: {get_color('bg_tertiary')}; border: 1px solid {get_color('border')}; border-radius: 4px;")
        self.scroll_content.setStyleSheet("background-color: transparent;")
        self._update_total() # Refresh title color
        
        # Style for cleaner boxes without arrows
        combo_style = f"""
            QComboBox {{ 
                background-color: {get_color('btn_bg')}; 
                color: {get_color('btn_text')}; 
                border: 1px solid {get_color('slot_border')}; 
                padding-left: 5px;
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
        """
        
        # Refresh widgets in grid
        for aid, (lbl, spin) in self.attr_widgets.items():
            spin.setStyleSheet(combo_style)
            if aid < 0:
                lbl.setStyleSheet(f"color: {get_color('text_warning')}; font-size: 13px; border: none; font-weight: bold;")
            else:
                lbl.setStyleSheet(f"color: {get_color('text_secondary')}; font-size: 13px; border: none; font-weight: bold;")

    def set_professions(self, primary_id, secondary_id, active_skills: List[Skill] = None, extra_attrs: List[int] = None):
        self.primary_id = primary_id # Store for dynamic updates
        # Snapshot current values before clearing to ensure preservation
        for aid, (lbl, spin) in self.attr_widgets.items():
            try:
                val = int(spin.currentText())
                self.current_distribution[aid] = val
            except:
                pass

        # Clear existing widgets
        for i in reversed(range(self.grid.count())): 
            self.grid.itemAt(i).widget().setParent(None)
        self.attr_widgets.clear()
        
        # 1. Base Profession attributes are editable
        editable_attrs = set()
        if primary_id in PROF_ATTRS:
            editable_attrs.update(PROF_ATTRS[primary_id])
        if secondary_id in PROF_ATTRS:
            secondary_primary_attr = PROF_PRIMARY_ATTR.get(secondary_id)
            for aid in PROF_ATTRS[secondary_id]:
                if aid != secondary_primary_attr:
                    editable_attrs.add(aid)
        
        relevant_attrs = list(editable_attrs)
        
        # 2. Check for attributes in active skills (Title tracks etc)
        if active_skills:
            for s in active_skills:
                if s.attribute != -1:
                    if s.attribute not in relevant_attrs:
                        relevant_attrs.append(s.attribute)
                    # PvE attributes are "editable" (points representing title rank)
                    if s.attribute < 0:
                        editable_attrs.add(s.attribute)

        # 3. Check for extra attributes (e.g. from special weapons)
        # These are added to relevant_attrs so they appear, but NOT to editable_attrs
        if extra_attrs:
            for aid in extra_attrs:
                if aid != -1 and aid not in relevant_attrs:
                    relevant_attrs.append(aid)

        # SPECIAL: If no primary profession selected, allow editing of ALL displayed attributes
        if primary_id == 0:
            for aid in relevant_attrs:
                if aid >= 0:
                    editable_attrs.add(aid)

        # Sort: Standard attributes first (by name), then PvE attributes
        std_attrs = [a for a in relevant_attrs if a >= 0]
        pve_attrs = [a for a in relevant_attrs if a < 0]
        
        std_attrs.sort(key=lambda x: ATTR_MAP.get(x, ""))
        pve_attrs.sort(key=lambda x: ATTR_MAP.get(x, ""))
        
        final_attrs = std_attrs + pve_attrs
        
        # Style for cleaner boxes without arrows
        combo_style = f"""
            QComboBox {{ 
                background-color: {get_color('btn_bg')}; 
                color: {get_color('btn_text')}; 
                border: 1px solid {get_color('slot_border')}; 
                padding-left: 5px;
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox:disabled {{
                background-color: {get_color('bg_secondary')};
                color: {get_color('text_tertiary')};
                border: 1px dashed {get_color('border')};
            }}
        """

        for i, aid in enumerate(final_attrs):
            name = ATTR_MAP.get(aid, f"Attr {aid}")
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            
            spin = QComboBox()
            # Default limits: 12 for standard, 10 for PvE
            limit = 12 if aid >= 0 else 10
            
            # Specific PvE caps
            if aid in [-4, -5]: limit = 12 # Luxon & Kurzick
            elif aid in [-3, -2]: limit = 8 # Lightbringer & Sunspear
            
            spin.addItems([str(i) for i in range(limit + 1)])
            spin.setFixedWidth(40)
            spin.setStyleSheet(combo_style)
            
            # --- EDITABILITY LOGIC ---
            is_editable = aid in editable_attrs
            spin._originally_disabled = not is_editable # STORE ORIGINAL STATE
            if not is_editable:
                spin.setCurrentIndex(0)
                spin.setEnabled(False)
                lbl.setToolTip("This attribute is class specific and doesnt match your primary profession.")
            else:
                # Set previous value if it existed and was valid
                prev_val = self.current_distribution.get(aid, 0)
                spin.setCurrentIndex(min(prev_val, limit))
                spin.setEnabled(True) # Ensure enabled if it is editable
            
            spin.currentIndexChanged.connect(lambda _, a=aid: self._on_attr_changed(a))
            
            # Apply tooltip if it's a primary bonus
            if primary_id in PROF_PRIMARY_ATTR and aid == PROF_PRIMARY_ATTR[primary_id]:
                bonus_text = get_primary_bonus_description(aid, spin.currentIndex())
                if bonus_text:
                    lbl.setToolTip(f"<b>Primary Bonus:</b><br>{bonus_text}")

            # Label on top row, Spinbox on row below it
            self.grid.addWidget(lbl, i * 2, 0, Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(spin, i * 2 + 1, 0, Qt.AlignmentFlag.AlignCenter)
            self.attr_widgets[aid] = (lbl, spin)
            
            # Initial styling
            self._update_label_style(aid)
            
        self._update_total()

    def _update_label_style(self, aid, bonus=0):
        if aid not in self.attr_widgets: return
        lbl, spin = self.attr_widgets[aid]
        
        style_parts = ["font-size: 13px;", "border: none;", "font-weight: bold;"]
        
        # 1. Color
        if aid < 0:
            style_parts.append(f"color: {get_color('text_warning')};")
        elif bonus > 0:
            style_parts.append("color: #00FF00;")
        else:
            style_parts.append(f"color: {get_color('text_secondary')};")
            
        # 2. Underline (Inherent Attribute)
        if self.primary_id in PROF_PRIMARY_ATTR and aid == PROF_PRIMARY_ATTR[self.primary_id]:
            style_parts.append("text-decoration: underline;")
            
        lbl.setStyleSheet(" ".join(style_parts))

    def set_external_bonuses(self, bonuses: dict, global_bonus: int = 0):
        """
        Updates the labels to show total effective attributes.
        bonuses: {attr_id: bonus_val}
        global_bonus: int (e.g. +1 from Grail)
        """
        for aid, (lbl, spin) in self.attr_widgets.items():
            base_val = int(spin.currentText())
            
            # Calculate total
            bonus = bonuses.get(aid, 0) + global_bonus + self.hr_bonus
            
            # PvE attributes usually don't get standard bonuses, but let's assume they might get global
            if aid < 0:
                bonus = 0 # Usually PvE ranks are standalone or capped differently. Let's keep them clean for now unless specified.
            
            total = base_val + bonus
            if total > 20: total = 20 # Hard Cap
            
            attr_name = ATTR_MAP.get(aid, f"Attr {aid}")
            
            if bonus > 0:
                lbl.setText(f"{attr_name} ({total})")
            else:
                lbl.setText(attr_name)
            
            self._update_label_style(aid, bonus)

    def _on_attr_changed(self, attr_id):
        # Calculate what the total would be with the new value
        new_val = int(self.attr_widgets[attr_id][1].currentText())
        old_val = self.current_distribution.get(attr_id, 0)
        
        costs = [0, 1, 3, 6, 10, 15, 21, 28, 37, 48, 61, 77, 97]
        
        # Calculate potential new total
        potential_total = 0
        for aid, (lbl, spin) in self.attr_widgets.items():
            if aid < 0: continue
            
            rank = int(spin.currentText())
            # For the attribute currently being changed, use the new potential value
            if aid == attr_id:
                rank = new_val
                
            cost_rank = min(rank, 12)
            potential_total += costs[cost_rank]

        # Enforce Limit
        if potential_total > self.max_points:
            # Revert to old value
            spin = self.attr_widgets[attr_id][1]
            spin.blockSignals(True)
            spin.setCurrentIndex(min(old_val, 12))
            spin.blockSignals(False)
            return

        # Commit Change
        self.current_distribution[attr_id] = new_val
        
        # Update Tooltip if it's the primary attribute
        if self.primary_id in PROF_PRIMARY_ATTR:
            if attr_id == PROF_PRIMARY_ATTR[self.primary_id]:
                bonus_text = get_primary_bonus_description(attr_id, new_val)
                if bonus_text:
                    self.attr_widgets[attr_id][0].setToolTip(f"<b>Primary Bonus:</b><br>{bonus_text}")

        self._update_total()
        self.attributes_changed.emit(self.current_distribution)

    def _update_total(self):
        # Calculate point cost (GW formula)
        costs = [0, 1, 3, 6, 10, 15, 21, 28, 37, 48, 61, 77, 97]
        
        total = 0
        for aid, (lbl, spin) in self.attr_widgets.items():
            if aid < 0: continue # PvE attributes cost 0 points
            
            rank = int(spin.currentText())
            # Clamp rank to 12 for cost calculation, as ranks 13-20 are from external sources
            cost_rank = min(rank, 12)
            total += costs[cost_rank]
        
        self.current_points = total
        self.title.setText(f"Atts ({total}/{self.max_points})")
        
        if total > self.max_points:
            self.title.setStyleSheet(f"font-weight: bold; color: {get_color('text_warning')}; border: none;")
        else:
            self.title.setStyleSheet(f"font-weight: bold; color: {get_color('text_secondary')}; border: none;")

    def get_distribution(self):
        return {aid: int(spin.currentText()) for aid, (lbl, spin) in self.attr_widgets.items()}
    
    def set_distribution(self, dist):
        self.current_distribution = dist
        
        # Iterate over ALL active widgets to ensure full sync
        for aid, (lbl, spin) in list(self.attr_widgets.items()):
            target_val = dist.get(aid, 0)
            
            # Re-calculate limit for this attribute
            limit = 12 if aid >= 0 else 10
            if aid in [-4, -5]: limit = 12
            elif aid in [-3, -2]: limit = 8
            
            spin.setCurrentIndex(min(target_val, limit))
            
        self._update_total()

    def get_attribute_widget(self, attr_id):
        """ Returns the label and spinbox for a specific attribute if it exists. """
        return self.attr_widgets.get(attr_id)

    def set_read_only(self, read_only: bool):
        """
        Enables or disables user interaction with the attribute controls.
        Used to prevent editing of meta builds.
        """
        self.hr_combo.setEnabled(not read_only)
        for aid, (lbl, spin) in self.attr_widgets.items():
            # If the attribute wasn't editable to begin with (e.g. weapon-only), 
            # we keep it disabled.
            if hasattr(spin, '_originally_disabled') and spin._originally_disabled:
                spin.setEnabled(False)
            else:
                spin.setEnabled(not read_only)
            
            # Update visual style to reflect state
            if read_only:
                lbl.setToolTip(f"<b>Read Only</b><br>Meta builds cannot be edited directly.")
            else:
                lbl.setToolTip("") # Restore default or clear
