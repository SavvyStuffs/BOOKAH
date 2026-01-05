import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QScrollArea, QFrame, QPushButton, QCheckBox, QGroupBox, QComboBox, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QIcon, QPixmap
from src.constants import resource_path, PROF_MAP
from src.ui.theme import get_color

# --- Data Definitions ---

CONSUMABLES = {
    "apple": {
        "name": "Candy Apple",
        "icon": "apple.png",
        "stats": {"hp": 100, "energy": 10}
    },
    "corn": {
        "name": "Candy Corn",
        "icon": "corn.png",
        "stats": {"all_atts": 1}
    },
    "egg": {
        "name": "Golden Egg",
        "icon": "egg.png",
        "stats": {"all_atts": 1}
    },
    "lunar": {
        "name": "Lunar Fortune",
        "icon": "lunar.png",
        "stats": {"all_atts": 1}
    },
    "green_rock": {
        "name": "Green Rock Candy",
        "icon": "green_rock.png",
        "stats": {"attack_speed": 0.15, "activation": -0.15}
    },
    "blue_rock": {
        "name": "Blue Rock Candy",
        "icon": "blue_rock.png",
        "stats": {"attack_speed": 0.25, "activation": -0.20}
    },
    "red_rock": {
        "name": "Red Rock Candy",
        "icon": "red_rock.png",
        "stats": {"attack_speed": 0.33, "activation": -0.25}
    },
    "pie": {
        "name": "Pumpkin Pie",
        "icon": "pie.png",
        "stats": {"attack_speed": 0.25, "activation": -0.15}
    },
    "armor": {
        "name": "Armor of Salvation",
        "icon": "armor.png",
        "stats": {"crit_immunity": 0.50, "armor": 10, "hp_regen": 1, "incoming_dmg": -5}
    },
    "bu": {
        "name": "Essence of Celerity",
        "icon": "bu.png",
        "stats": {"move_speed": 0.20, "attack_speed": 0.20, "activation": -0.20, "recharge": -0.20}
    },
    "grail": {
        "name": "Grail of Might",
        "icon": "grail.png",
        "stats": {"hp": 100, "energy": 10, "all_atts": 1}
    },
    "cupcake": {
        "name": "Birthday Cupcake",
        "icon": "cupcake.png",
        "stats": {"hp": 100, "energy": 10, "move_speed": 0.25}
    }
}

WEAPONS = {
    "decade_bow": {"name": "Scorpion's Clutch", "attr": 17, "icon": "decade_bow.png"},
    "decade_dagger": {"name": "Dragon's Restraint", "attr": 23, "icon": "decade_dagger.png"},
    "decade_hammer": {"name": "Bear's Roar", "attr": 40, "icon": "decade_hammer.png"},
    "decade_rod": {"name": "Unicorn's Valor", "attr": 0, "icon": "decade_rod.png"},
    "decade_scythe": {"name": "Soul's Repentance", "attr": 6, "icon": "decade_scythe.png"},
    "decade_spear": {"name": "Sun's Revolution", "attr": 35, "icon": "decade_spear.png"},
    "decade_staff_hour": {"name": "Hourglass's Patience", "attr": 12, "icon": "decade_staff_hour.png"},
    "decade_staff_snake": {"name": "Snake's Lineage", "attr": 36, "icon": "decade_staff_snake.png"},
    "decade_staff_dragon": {"name": "Dragon's Inheritance", "attr": 44, "icon": "decade_staff_dragon.png"},
    "decade_staff_spirit": {"name": "Spirit's Absolution", "attr": 16, "icon": "decade_staff_spirit.png"},
}

CAPS = {
    "activation": -0.25,      # Lower is better (negative), capped at -25%
    "attack_speed": 0.33,     # Higher is better
    "move_speed": 0.34,       # Higher is better
    "hp_regen": 10,           # Max +10
    "recharge": -0.50,        # Max -50%
    "armor": 25,              # Max +25
    "all_atts": 20            # Standard attribute rank cap
}

class ConsumableItem(QPushButton):
    toggled_state = pyqtSignal(str, bool) # key, is_checked

    def __init__(self, key, data):
        super().__init__()
        self.key = key
        self.data = data
        self.setCheckable(True)
        self.setFixedSize(64, 64)
        self.setIconSize(QSize(48, 48))
        
        # HTML Tooltip
        tooltip = f"<b>{data['name']}</b><br/><br/>{self._format_stats(data['stats'])}"
        self.setToolTip(tooltip)
        
        icon_path = resource_path(os.path.join("icons", "cons_icons", data['icon']))
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            self.setText(data['name'][:2])

        self.refresh_theme()
        self.toggled.connect(lambda checked: self.toggled_state.emit(self.key, checked))

    def refresh_theme(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('slot_bg')};
                border: 2px solid {get_color('slot_border')};
                border-radius: 8px;
            }}
            QPushButton:checked {{
                background-color: {get_color('slot_bg_equipped')};
                border: 2px solid #00FF00;
            }}
            QPushButton:hover {{
                border-color: {get_color('border_accent')};
            }}
            QToolTip {{
                background-color: {get_color('tooltip_bg')};
                color: {get_color('tooltip_text')};
                border: 1px solid {get_color('border')};
                padding: 4px;
            }}
        """)

    def set_icon_size(self, size):
        self.setFixedSize(size, size)
        self.setIconSize(QSize(int(size * 0.75), int(size * 0.75)))

    def _format_stats(self, stats):
        lines = []
        for k, v in stats.items():
            if "speed" in k or "activation" in k or "recharge" in k or "crit" in k:
                val = f"{int(v*100)}%"
                if v > 0: val = f"{val}"
            else:
                val = str(v)
                if v > 0: val = f"{val}"
            lines.append(f"{k.replace('_', ' ').title()}: {val}")
        return "<br/>".join(lines)

class WeaponItem(QPushButton):
    def __init__(self, name):
        super().__init__(name)
        self.setCheckable(True)
        self.setFixedSize(200, 40) # Wider for weapon names
        self.setStyleSheet("""
            QPushButton {
                background-color: #222;
                border: 1px solid #555;
                color: #aaa;
                border-radius: 4px;
            }
            QPushButton:checked {
                border: 2px solid #FFD700;
                color: white;
                background-color: #333;
            }
            QPushButton:hover {
                border-color: #888;
            }
        """)

class RuneItem(QPushButton):
    toggled_state = pyqtSignal(object, bool) # self, is_checked
    clicked_rune = pyqtSignal(object) # self
    right_clicked_rune = pyqtSignal(object) # self

    def __init__(self, name, icon_name=None, rtype=None, prof_id=None, attr_id=None, checkable=False, icon_dir="runes_icons"):
        super().__init__()
        self.rtype = rtype # "minor", "major", "sup", "vigor", "attunement"
        self.prof_id = prof_id
        self.attr_id = attr_id 
        self.setCheckable(checkable)
        self.setFixedSize(80, 80)
        self.setToolTip(f"<b>{name}</b>")
        
        if icon_name:
            icon_path = resource_path(os.path.join("icons", icon_dir, icon_name))
            if os.path.exists(icon_path):
                self.setIcon(QIcon(icon_path))
                self.setIconSize(QSize(56, 56))
            else:
                self.setText(name)
        else:
            self.setText(name)

        self.refresh_theme()
        if checkable:
            self.toggled.connect(lambda checked: self.toggled_state.emit(self, checked))
        else:
            self.clicked.connect(lambda: self.clicked_rune.emit(self))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.right_clicked_rune.emit(self)
        else:
            super().mousePressEvent(event)

    def set_icon_size(self, size):
        self.setFixedSize(size, size)
        self.setIconSize(QSize(int(size * 0.75), int(size * 0.75)))
        if size > 100:
            self.setStyleSheet(self.styleSheet().replace("border-radius: 40px;", f"border-radius: {size//2}px;"))
        else:
            self.setStyleSheet(self.styleSheet().replace(f"border-radius: {128//2}px;", "border-radius: 40px;"))

    def refresh_theme(self):
        radius = self.width() // 2
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('slot_bg')};
                border: 1px dashed {get_color('slot_border')};
                color: {get_color('text_secondary')};
                border-radius: {radius}px; /* Circular */
            }}
            QPushButton:checked {{
                border: 2px solid {get_color('border_accent')};
                color: {get_color('text_primary')};
                background-color: {get_color('slot_bg_equipped')};
            }}
            QPushButton:hover {{
                border-color: {get_color('text_accent')};
            }}
            QPushButton:disabled {{
                background-color: {get_color('bg_secondary')};
                border: 1px solid {get_color('border')};
                opacity: 0.5;
            }}
            QToolTip {{
                background-color: {get_color('tooltip_bg')};
                color: {get_color('tooltip_text')};
                border: 1px solid {get_color('border')};
                padding: 4px;
            }}
        """)

class WeaponWidget(QWidget):
    toggled = pyqtSignal(str, bool) # weapon_key, is_checked

    def __init__(self, key, data):
        super().__init__()
        self.key = key
        self.data = data
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.button = RuneItem(data['name'], icon_name=data['icon'], checkable=True, icon_dir="weapons_icons")
        self.button.toggled.connect(lambda checked: self.toggled.emit(self.key, checked))
        
        self.label = QLabel(f'"{data["name"]}"')
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFixedWidth(140)
        self.label.setStyleSheet(f"font-size: 11px; color: {get_color('text_primary')}; font-style: italic;")
        
        layout.addWidget(self.button)
        layout.addWidget(self.label)

    def set_icon_size(self, size):
        self.button.set_icon_size(size)
        self.label.setFixedWidth(size + 60)

    def refresh_theme(self):
        self.button.refresh_theme()
        self.label.setStyleSheet(f"font-size: 11px; color: {get_color('text_primary')}; font-style: italic;")

class WeaponsPanel(QWidget):
    def __init__(self, parent_panel=None):
        super().__init__()
        self.parent_panel = parent_panel
        self.weapon_widgets = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.group = QGroupBox("Weapons")
        group_layout = QVBoxLayout(self.group)
        group_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setSpacing(15)
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        for key, data in WEAPONS.items():
            w = WeaponWidget(key, data)
            w.toggled.connect(self.on_weapon_toggled)
            self.weapon_widgets[key] = w
            vbox.addWidget(w)
                
        scroll.setWidget(container)
        group_layout.addWidget(scroll)
        layout.addWidget(self.group)
        self.refresh_theme()

    def set_icon_size(self, size):
        for w in self.weapon_widgets.values():
            w.set_icon_size(size)

    def on_weapon_toggled(self, key, checked):
        if checked:
            # Uncheck others
            for k, w in self.weapon_widgets.items():
                if k != key:
                    w.button.blockSignals(True)
                    w.button.setChecked(False)
                    w.button.blockSignals(False)
            
            if self.parent_panel:
                self.parent_panel.active_weapon = key
        else:
            if self.parent_panel and self.parent_panel.active_weapon == key:
                self.parent_panel.active_weapon = None
        
        if self.parent_panel:
            self.parent_panel.update_stats()

    def select_weapon(self, key):
        if key in self.weapon_widgets:
            self.weapon_widgets[key].button.setChecked(True)

    def refresh_theme(self):
        self.group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {get_color('text_secondary')}; border: 1px solid {get_color('border')}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        for w in self.weapon_widgets.values():
            w.refresh_theme()

class CharacterPanel(QWidget):
    stats_changed = pyqtSignal(dict, dict) # bonuses, globals

    def __init__(self):
        super().__init__()
        self.active_cons = set()
        self.applied_runes = [] # List of dicts: {"rtype": "sup", "prof_id": 1, "attr_id": 20}
        self.selected_attrs = {} # {prof_id: attr_id}
        self.active_weapon = None # Weapon key from WEAPONS
        self.primary_prof_id = 0
        self.attr_energy_bonus = 0 # Extra energy from primary attributes
        self.con_widgets = []
        self.rune_widgets = []
        self.attunement_widgets = []
        self.group_boxes = []
        self.row_labels = []
        self.combo_boxes = []
        self.base_stat_labels = []
        self.init_ui()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and isinstance(obj, QComboBox):
            event.ignore()
            return True
        return super().eventFilter(obj, event)

    def on_rune_clicked(self, rune):
        if len(self.applied_runes) >= 5:
            return

        if rune.attr_id == "vigor":
            self.applied_runes.append({"rtype": rune.rtype, "attr_id": "vigor"})
        elif rune.attr_id == "attunement":
            self.applied_runes.append({"rtype": "attunement", "attr_id": "attunement"})
        elif rune.attr_id == "vitae":
            self.applied_runes.append({"rtype": "vitae", "attr_id": "vitae"})
        else:
            # RESTRICTION: Only primary profession runes allowed
            if rune.prof_id != self.primary_prof_id:
                return

            if rune.prof_id in self.selected_attrs:
                aid = self.selected_attrs[rune.prof_id]
                self.applied_runes.append({"rtype": rune.rtype, "prof_id": rune.prof_id, "attr_id": aid})
            else:
                return # Do nothing if no attribute selected
        self.update_stats()

    def on_rune_right_clicked(self, rune):
        # Determine targets
        target_rtype = rune.rtype
        target_attr_id = rune.attr_id
        target_prof_id = rune.prof_id

        # Resolve attribute for profession runes
        if target_attr_id is None and target_prof_id is not None:
            target_attr_id = self.selected_attrs.get(target_prof_id)
            if target_attr_id is None:
                return # No attribute selected for this profession

        # Find and remove the LAST matching entry (LIFO)
        for i in range(len(self.applied_runes) - 1, -1, -1):
            entry = self.applied_runes[i]
            
            # Match Type
            if entry.get("rtype") != target_rtype:
                continue
                
            # Match Attribute
            entry_attr = entry.get("attr_id")
            if entry_attr != target_attr_id:
                continue
                
            # Match Profession (if applicable)
            entry_prof = entry.get("prof_id")
            if target_prof_id is not None:
                if entry_prof != target_prof_id:
                    continue
            
            # Found match
            self.applied_runes.pop(i)
            self.update_stats()
            return

    def clear_runes(self):
        self.applied_runes = []
        self.update_stats()

    def clear_consumables(self):
        self.active_cons = set()
        for widget in self.con_widgets:
            widget.blockSignals(True)
            widget.setChecked(False)
            widget.blockSignals(False)
        self.update_stats()

    def on_attr_changed(self, prof_id, index, combo):
        attr_id = combo.itemData(index)
        if attr_id is not None:
            self.selected_attrs[prof_id] = attr_id
        else:
            self.selected_attrs.pop(prof_id, None)
        self.update_stats()

    def set_primary_profession(self, prof_id):
        if self.primary_prof_id == prof_id:
            return
            
        self.primary_prof_id = prof_id
        
        # 1. Clear runes that are no longer valid (not vigor/attunement and not primary)
        valid_runes = []
        changed = False
        for r in self.applied_runes:
            r_prof = r.get("prof_id")
            if r_prof is None or r_prof == prof_id:
                valid_runes.append(r)
            else:
                changed = True
        
        if changed:
            self.applied_runes = valid_runes
            
        # 2. Update button states
        for rune in self.rune_widgets:
            if rune.prof_id is not None:
                rune.setEnabled(rune.prof_id == prof_id)
                
        self.update_stats()

    def set_attr_energy_bonus(self, amount):
        if self.attr_energy_bonus != amount:
            self.attr_energy_bonus = amount
            self.update_stats()

    def set_icon_size(self, size):
        for widget in self.con_widgets:
            widget.set_icon_size(size)
        for widget in self.rune_widgets:
            widget.set_icon_size(size)

    def refresh_theme(self):
        self.lbl_stats.setStyleSheet(f"color: {get_color('text_primary')};")
        self.lbl_runes.setStyleSheet(f"color: {get_color('text_primary')};")
        
        if hasattr(self, 'lbl_rune_hint'):
            self.lbl_rune_hint.setStyleSheet(f"color: {get_color('text_primary')}; font-size: 12px; font-style: italic;")
        
        if hasattr(self, 'btn_clear_runes'):
            self.btn_clear_runes.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('bg_hover')};
                    color: {get_color('text_warning')};
                    border: 1px solid {get_color('border')};
                    border-radius: 4px;
                    padding: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {get_color('bg_selected')};
                }}
            """)
            
        if hasattr(self, 'btn_clear_cons'):
            self.btn_clear_cons.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('bg_hover')};
                    color: {get_color('text_warning')};
                    border: 1px solid {get_color('border')};
                    border-radius: 4px;
                    padding: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {get_color('bg_selected')};
                }}
            """)
        
        group_style = f"QGroupBox {{ font-weight: bold; color: {get_color('text_secondary')}; border: 1px solid {get_color('border')}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}"
        for gb in self.group_boxes:
            gb.setStyleSheet(group_style)
            
        label_style = f"font-weight: bold; color: {get_color('text_secondary')}; min-width: 60px;"
        for lbl in self.row_labels:
            lbl.setStyleSheet(label_style)
            
        base_label_style = f"font-size: 10px; color: {get_color('text_secondary')};"
        for lbl in self.base_stat_labels:
            lbl.setStyleSheet(base_label_style)
            
        edit_style = f"background-color: {get_color('input_bg')}; color: {get_color('text_primary')}; border: 1px solid {get_color('border')}; font-size: 10px;"
        if hasattr(self, 'edit_hp_player'): self.edit_hp_player.setStyleSheet(edit_style)
        if hasattr(self, 'edit_en_player'): self.edit_en_player.setStyleSheet(edit_style)
        
        if hasattr(self, 'lbl_hp_adj_val'): self.lbl_hp_adj_val.setStyleSheet(f"font-weight: bold; color: {get_color('text_accent')}; font-size: 10px;")
        if hasattr(self, 'lbl_en_adj_val'): self.lbl_en_adj_val.setStyleSheet(f"font-weight: bold; color: {get_color('text_accent')}; font-size: 10px;")

        for w in self.con_widgets:
            w.refresh_theme()
        for w in self.rune_widgets:
            w.refresh_theme()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(20)

        # --- Left: Consumables ---
        self.cons_group = QGroupBox("Consumables")
        self.group_boxes.append(self.cons_group)
        self.cons_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {get_color('text_secondary')}; border: 1px solid {get_color('border')}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        cons_layout = QVBoxLayout(self.cons_group)
        
        # Clear Button
        cons_clear_hbox = QHBoxLayout()
        cons_clear_hbox.addStretch()
        self.btn_clear_cons = QPushButton("Clear Consumables")
        self.btn_clear_cons.setFixedWidth(120)
        self.btn_clear_cons.clicked.connect(self.clear_consumables)
        cons_clear_hbox.addWidget(self.btn_clear_cons)
        cons_layout.addLayout(cons_clear_hbox)
        
        scroll_cons = QScrollArea()
        scroll_cons.setWidgetResizable(True)
        scroll_cons.setStyleSheet("background: transparent; border: none;")
        
        cons_container = QWidget()
        self.cons_grid = QGridLayout(cons_container)
        self.cons_grid.setSpacing(10)
        self.cons_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Populate Cons
        ORDERED_KEYS = [
            "apple", "corn", "egg", 
            "lunar", "cupcake", "pie", 
            "green_rock", "blue_rock", "red_rock", 
            "armor", "bu", "grail"
        ]
        
        row, col = 0, 0
        for key in ORDERED_KEYS:
            data = CONSUMABLES[key]
            item = ConsumableItem(key, data)
            item.toggled_state.connect(self.on_con_toggled)
            self.con_widgets.append(item)
            self.cons_grid.addWidget(item, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        scroll_cons.setWidget(cons_container)
        cons_layout.addWidget(scroll_cons)
        
        # --- Center: Consumable Calculations ---
        self.stats_group = QGroupBox("Consumable Calculations")
        self.group_boxes.append(self.stats_group)
        self.stats_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {get_color('text_secondary')}; border: 1px solid {get_color('border')}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        stats_layout = QVBoxLayout(self.stats_group)
        
        self.lbl_stats = QLabel("No active effects.")
        self.lbl_stats.setWordWrap(True)
        self.lbl_stats.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_stats.setStyleSheet(f"color: {get_color('text_primary')};")
        
        stats_layout.addWidget(self.lbl_stats)
        
        # Rune Effects Label
        self.lbl_runes = QLabel("No rune effects.")
        self.lbl_runes.setWordWrap(True)
        self.lbl_runes.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_runes.setStyleSheet(f"color: {get_color('text_primary')};")
        stats_layout.addWidget(self.lbl_runes)
        
        stats_layout.addStretch()
        
        # --- Adjusted Base Stats ---
        stats_footer = QGridLayout()
        stats_footer.setSpacing(5)
        
        # Health row
        lbl_hp_player = QLabel("Player health:")
        self.base_stat_labels.append(lbl_hp_player)
        self.edit_hp_player = QLineEdit("480")
        self.edit_hp_player.setFixedWidth(50)
        self.edit_hp_player.textChanged.connect(self.update_stats)
        
        lbl_hp_adj_title = QLabel("Adjusted:")
        self.base_stat_labels.append(lbl_hp_adj_title)
        self.lbl_hp_adj_val = QLabel("480")
        self.lbl_hp_adj_val.setStyleSheet("font-weight: bold; color: #00AAFF;")
        
        stats_footer.addWidget(lbl_hp_player, 0, 0)
        stats_footer.addWidget(self.edit_hp_player, 0, 1)
        stats_footer.addWidget(lbl_hp_adj_title, 0, 2)
        stats_footer.addWidget(self.lbl_hp_adj_val, 0, 3)
        
        # Energy row
        lbl_en_player = QLabel("Player energy:")
        self.base_stat_labels.append(lbl_en_player)
        self.edit_en_player = QLineEdit("30")
        self.edit_en_player.setFixedWidth(50)
        self.edit_en_player.textChanged.connect(self.update_stats)
        
        lbl_en_adj_title = QLabel("Adjusted:")
        self.base_stat_labels.append(lbl_en_adj_title)
        self.lbl_en_adj_val = QLabel("20")
        self.lbl_en_adj_val.setStyleSheet("font-weight: bold; color: #00AAFF;")
        
        stats_footer.addWidget(lbl_en_player, 1, 0)
        stats_footer.addWidget(self.edit_en_player, 1, 1)
        stats_footer.addWidget(lbl_en_adj_title, 1, 2)
        stats_footer.addWidget(self.lbl_en_adj_val, 1, 3)
        
        stats_layout.addLayout(stats_footer)
        
        # --- Right: Runes ---
        self.runes_group = QGroupBox("Runes")
        self.group_boxes.append(self.runes_group)
        self.runes_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {get_color('text_secondary')}; border: 1px solid {get_color('border')}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        runes_layout = QVBoxLayout(self.runes_group)
        
        # Clear Button
        clear_hbox = QHBoxLayout()
        clear_hbox.addStretch()
        
        self.lbl_rune_hint = QLabel("Right click to remove a single rune")
        self.lbl_rune_hint.setStyleSheet(f"color: {get_color('text_primary')}; font-size: 12px; font-style: italic;")
        clear_hbox.addWidget(self.lbl_rune_hint)
        
        self.btn_clear_runes = QPushButton("Clear Runes")
        self.btn_clear_runes.setFixedWidth(100)
        self.btn_clear_runes.clicked.connect(self.clear_runes)
        clear_hbox.addWidget(self.btn_clear_runes)
        runes_layout.addLayout(clear_hbox)
        
        scroll_runes = QScrollArea()
        scroll_runes.setWidgetResizable(True)
        scroll_runes.setStyleSheet("background: transparent; border: none;")
        
        runes_container = QWidget()
        self.runes_grid = QGridLayout(runes_container)
        self.runes_grid.setSpacing(10)
        self.runes_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # Adjust column stretches: Label (0), Icons (1-3), Dropdown (4), Spacer (5)
        self.runes_grid.setColumnStretch(0, 0)
        self.runes_grid.setColumnStretch(1, 0)
        self.runes_grid.setColumnStretch(2, 0)
        self.runes_grid.setColumnStretch(3, 0)
        self.runes_grid.setColumnStretch(4, 0)
        self.runes_grid.setColumnStretch(5, 1) # Absorbs extra horizontal space
        
        # 1. Attunement Row (Top)
        att_label = QLabel("Attunement")
        self.row_labels.append(att_label)
        att_label.setStyleSheet(f"font-weight: bold; color: {get_color('text_tertiary')}; min-width: 60px;")
        self.runes_grid.addWidget(att_label, 0, 0)
        
        # Single Stackable Icon (Using existing Vigor logic flow)
        self.att_rune = RuneItem("Attunement Rune", "attunement.png", rtype="attunement", attr_id="attunement")
        self.att_rune.clicked_rune.connect(self.on_rune_clicked)
        self.att_rune.right_clicked_rune.connect(self.on_rune_right_clicked)
        self.rune_widgets.append(self.att_rune)
        self.runes_grid.addWidget(self.att_rune, 0, 1)

        # Vitae label in middle column (2), icon in right column (3)
        vitae_label = QLabel("Vitae")
        self.row_labels.append(vitae_label)
        vitae_label.setStyleSheet(f"font-weight: bold; color: {get_color('text_tertiary')}; min-width: 60px;")
        vitae_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.runes_grid.addWidget(vitae_label, 0, 2)

        self.vitae_rune = RuneItem("Rune of Vitae", "attunement.png", rtype="vitae", attr_id="vitae")
        self.vitae_rune.clicked_rune.connect(self.on_rune_clicked)
        self.vitae_rune.right_clicked_rune.connect(self.on_rune_right_clicked)
        self.rune_widgets.append(self.vitae_rune)
        self.runes_grid.addWidget(self.vitae_rune, 0, 3)

        # 2. Vigor Row
        vig_label = QLabel("Vigor")
        self.row_labels.append(vig_label)
        vig_label.setStyleSheet(f"font-weight: bold; color: {get_color('text_tertiary')}; min-width: 60px;")
        self.runes_grid.addWidget(vig_label, 1, 0)
        
        vig_icons = ["minor_vig.png", "major_vig.png", "sup_vig.png"]
        vig_names = ["Minor Vigor", "Major Vigor", "Superior Vigor"]
        vig_types = ["minor", "major", "sup"]
        for i in range(3):
            rune = RuneItem(vig_names[i], vig_icons[i], rtype=vig_types[i], attr_id="vigor")
            rune.clicked_rune.connect(self.on_rune_clicked)
            rune.right_clicked_rune.connect(self.on_rune_right_clicked)
            self.rune_widgets.append(rune)
            self.runes_grid.addWidget(rune, 1, i + 1)
        
        # 3. Profession Runes
        from src.constants import PROF_ATTRS, ATTR_MAP
        
        prefix_map = {
            1: "war", 2: "ran", 3: "mo", 4: "nec", 5: "mes",
            6: "ele", 7: "sin", 8: "rit", 9: "para", 10: "derv"
        }
        suffixes = ["minor", "major", "sup"]
        suffix_names = ["Minor", "Major", "Superior"]
        
        r_row = 2
        for pid in sorted(PROF_MAP.keys()):
            if pid == 0: continue
            pname = PROF_MAP[pid]
            
            # Profession Label
            p_label = QLabel(pname)
            self.row_labels.append(p_label)
            p_label.setStyleSheet(f"font-weight: bold; color: {get_color('text_tertiary')}; min-width: 60px;")
            self.runes_grid.addWidget(p_label, r_row, 0)
            
            prefix = prefix_map.get(pid, pname[:3].lower())
            
            for i in range(3):
                suf = suffixes[i]
                sname = suffix_names[i]
                icon_file = f"{prefix}_{suf}.png"
                rune = RuneItem(f"{sname} {pname} Rune", icon_file, rtype=suf, prof_id=pid)
                rune.clicked_rune.connect(self.on_rune_clicked)
                rune.right_clicked_rune.connect(self.on_rune_right_clicked)
                self.rune_widgets.append(rune)
                self.runes_grid.addWidget(rune, r_row, i + 1)
            
            # Attribute Dropdown
            attr_combo = QComboBox()
            self.combo_boxes.append(attr_combo)
            attr_combo.installEventFilter(self) # Disable scrolling
            attr_combo.setFixedWidth(120)
            attr_combo.addItem("Select Attribute", None)
            attr_combo.setStyleSheet("""
                QComboBox {
                    background-color: #333;
                    color: white;
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 2px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background-color: #222;
                    color: white;
                    selection-background-color: #00AAFF;
                    selection-color: white;
                    border: 1px solid #555;
                }
            """)
            if pid in PROF_ATTRS:
                for aid in PROF_ATTRS[pid]:
                    attr_name = ATTR_MAP.get(aid, f"Attr {aid}")
                    attr_combo.addItem(attr_name, aid)
            attr_combo.currentIndexChanged.connect(lambda idx, p=pid, c=attr_combo: self.on_attr_changed(p, idx, c))
            self.runes_grid.addWidget(attr_combo, r_row, 4)
            
            r_row += 1

        scroll_runes.setWidget(runes_container)
        runes_layout.addWidget(scroll_runes)

        # Add to main
        main_layout.addWidget(self.cons_group, stretch=5)
        main_layout.addWidget(self.stats_group, stretch=3)
        main_layout.addWidget(self.runes_group, stretch=10)

    def on_con_toggled(self, key, checked):
        if checked:
            self.active_cons.add(key)
        else:
            self.active_cons.discard(key)
        self.update_stats()

    def toggle_consumable(self, key, checked):
        for widget in self.con_widgets:
            if widget.key == key:
                widget.setChecked(checked)
                break

    def add_rune_direct(self, rtype, prof_id=None, attr_id=None):
        if len(self.applied_runes) < 5:
            self.applied_runes.append({
                "rtype": rtype,
                "prof_id": prof_id,
                "attr_id": attr_id
            })
            self.update_stats()

    def get_total_energy(self):
        try:
            player_en = int(self.edit_en_player.text())
        except ValueError:
            player_en = 30
            
        bonus_energy = self.attr_energy_bonus
        for key in self.active_cons:
            bonus_energy += CONSUMABLES[key]["stats"].get("energy", 0)

        # Add Attunement
        if hasattr(self, 'att_rune') and hasattr(self.att_rune, 'current_stacks'):
             bonus_energy += (self.att_rune.current_stacks * 2)
        elif hasattr(self, 'att_combo'):
             bonus_energy += (self.att_combo.currentIndex() * 2)
             
        return player_en + bonus_energy

    def update_stats(self):
        # 1. Gather Consumable Totals
        cons_totals = {
            "hp": 0, "energy": 0, "all_atts": 0, "armor": 0, "hp_regen": 0, "incoming_dmg": 0,
            "attack_speed": 0.0, "activation": 0.0, "move_speed": 0.0, "recharge": 0.0, "crit_immunity": 0.0
        }

        for key in self.active_cons:
            stats = CONSUMABLES[key]["stats"]
            for k, v in stats.items():
                if k in cons_totals:
                    cons_totals[k] += v

        # 2. Gather Rune Totals
        attr_tracking = {} # {attr_id: {rtype: count}}
        vigor_counts = {"minor": 0, "major": 0, "sup": 0}
        attunement_count = 0
        vitae_count = 0
        rune_hp_penalty = 0
        
        for entry in self.applied_runes:
            aid = entry.get("attr_id")
            if aid == "attunement":
                attunement_count += 1
                continue
            if aid == "vitae":
                vitae_count += 1
                continue

            rtype = entry["rtype"]
            is_vigor = aid == "vigor"
            
            # HP Penalty Stacks for ALL non-vigor Major/Sup runes
            if not is_vigor:
                if rtype == "major":
                    rune_hp_penalty -= 35
                elif rtype == "sup":
                    rune_hp_penalty -= 75
                
                if aid not in attr_tracking:
                    attr_tracking[aid] = {}
                attr_tracking[aid][rtype] = attr_tracking[aid].get(rtype, 0) + 1
            else:
                # Vigor has no penalty, track counts for highest-bonus logic
                vigor_counts[rtype] += 1

        # Attunement logic: +2 Energy per stack
        cons_totals["energy"] += (attunement_count * 2)

        # Vitae logic: +10 Health per stack
        vitae_hp = (vitae_count * 10)

        # Vigor logic: Highest bonus applies, they do NOT stack
        vigor_hp = 0
        if vigor_counts["sup"] > 0: vigor_hp = 50
        elif vigor_counts["major"] > 0: vigor_hp = 41
        elif vigor_counts["minor"] > 0: vigor_hp = 30

        # 3. Consolidate Stats
        total_hp = cons_totals["hp"] + vigor_hp + vitae_hp + rune_hp_penalty
        
        # Apply Caps to consumable-derived values
        if cons_totals["activation"] < CAPS["activation"]: cons_totals["activation"] = CAPS["activation"]
        if cons_totals["attack_speed"] > CAPS["attack_speed"]: cons_totals["attack_speed"] = CAPS["attack_speed"]
        if cons_totals["move_speed"] > CAPS["move_speed"]: cons_totals["move_speed"] = CAPS["move_speed"]
        if cons_totals["recharge"] < CAPS["recharge"]: cons_totals["recharge"] = CAPS["recharge"]
        if cons_totals["armor"] > CAPS["armor"]: cons_totals["armor"] = CAPS["armor"]
        if cons_totals["hp_regen"] > CAPS["hp_regen"]: cons_totals["hp_regen"] = CAPS["hp_regen"]

        # 4. Format Stats Output
        stats_text = "<b>Stats:</b><br><br>"
        has_stats = False
        
        if total_hp != 0:
            val_str = f"+{total_hp}" if total_hp > 0 else str(total_hp)
            
            # Show vigor/penalty context in tooltip-like details
            hp_details = []
            if vigor_counts["sup"] > 0 or vigor_counts["major"] > 0 or vigor_counts["minor"] > 0:
                hp_details.append("Vigor")
            if vitae_count > 0:
                hp_details.append(f"x{vitae_count} Vitae")
            
            if hp_details:
                stats_text += f"• Health: {val_str} ({', '.join(hp_details)})<br><br>"
            else:
                stats_text += f"• Health: {val_str}<br><br>"
            has_stats = True
            
        if cons_totals["energy"] > 0:
            en_str = f"• Energy: +{cons_totals['energy']}"
            if attunement_count > 0:
                en_str += f" (x{attunement_count} Attunement)"
            en_str += "<br><br>"
            stats_text += en_str
            has_stats = True
            
        if cons_totals["armor"] != 0:
            stats_text += f"• Armor: +{cons_totals['armor']}<br><br>"
            has_stats = True
            
        if cons_totals["hp_regen"] != 0:
            stats_text += f"• Health Regen: +{cons_totals['hp_regen']}<br><br>"
            has_stats = True
            
        if cons_totals["incoming_dmg"] != 0:
            stats_text += f"• Incoming Damage: {cons_totals['incoming_dmg']}<br><br>"
            has_stats = True
            
        if cons_totals["crit_immunity"] > 0:
            stats_text += f"• Crit Immunity: {int(cons_totals['crit_immunity']*100)}%<br><br>"
            has_stats = True
            
        if cons_totals["attack_speed"] != 0:
            stats_text += f"• Attack Speed: +{int(cons_totals['attack_speed']*100)}%<br><br>"
            has_stats = True
            
        if cons_totals["activation"] != 0:
            stats_text += f"• Casting Time: {int(cons_totals['activation']*100)}%<br><br>"
            has_stats = True
            
        if cons_totals["recharge"] != 0:
            stats_text += f"• Skill Recharge: {int(cons_totals['recharge']*100)}%<br><br>"
            has_stats = True
            
        if cons_totals["move_speed"] != 0:
            stats_text += f"• Movement Speed: +{int(cons_totals['move_speed']*100)}%<br><br>"
            has_stats = True

        if not has_stats:
            self.lbl_stats.setText("<b>Stats:</b><br><br>No active stat effects.")
        else:
            self.lbl_stats.setText(stats_text)

        # 5. Format Attributes Output
        attr_text = "<b>Attributes:</b><br><br>"
        has_attrs = False
        
        # Consumable All Attributes
        if cons_totals["all_atts"] > 0:
            val = cons_totals["all_atts"]
            if val > 20: val = 20
            attr_text += f"• All Attributes: +{val}<br><br>"
            has_attrs = True
            
        # Add Weapon Bonus
        if self.active_weapon and self.active_weapon in WEAPONS:
            w_data = WEAPONS[self.active_weapon]
            aid = w_data["attr"]
            attr_tracking[aid] = attr_tracking.get(aid, {})
            # We don't add to tracking count, we'll handle it separately or just add to total_bonus below
            
        # Specific Rune Bonuses (Highest applies per attribute)
        from src.constants import ATTR_MAP
        for aid, rtypes in sorted(attr_tracking.items()):
            attr_name = ATTR_MAP.get(aid, f"Attr {aid}")
            
            # Calculate Max Bonus from runes
            max_bonus = 0
            if "sup" in rtypes: max_bonus = 3
            elif "major" in rtypes: max_bonus = 2
            elif "minor" in rtypes: max_bonus = 1
            
            # Add Weapon Bonus (+5)
            weapon_active = False
            if self.active_weapon and WEAPONS[self.active_weapon]["attr"] == aid:
                max_bonus += 5
                weapon_active = True
            
            # Gather details
            details = []
            if "sup" in rtypes: details.append(f"x{rtypes['sup']} Superior")
            if "major" in rtypes: details.append(f"x{rtypes['major']} Major")
            if "minor" in rtypes: details.append(f"x{rtypes['minor']} Minor")
            if weapon_active:
                details.append(f'"{WEAPONS[self.active_weapon]["name"]}"')
                
            attr_text += f"• {attr_name}: +{max_bonus} ({', '.join(details)})<br><br>"
            has_attrs = True
            
        # Check if weapon was NOT in attr_tracking (meaning no runes applied to that attribute)
        if self.active_weapon:
            w_data = WEAPONS[self.active_weapon]
            aid = w_data["attr"]
            if aid not in attr_tracking:
                attr_name = ATTR_MAP.get(aid, f"Attr {aid}")
                attr_text += f"• {attr_name}: +5 (\"{w_data['name']}\")<br><br>"
                has_attrs = True

        if not has_attrs:
            self.lbl_runes.setText("<b>Attributes:</b><br><br>No attribute effects.")
        else:
            self.lbl_runes.setText(attr_text)

        # 6. Update Adjusted Base Stats
        try:
            player_hp = int(self.edit_hp_player.text())
            self.lbl_hp_adj_val.setText(str(player_hp + total_hp))
        except ValueError:
            self.lbl_hp_adj_val.setText("---")

        try:
            player_en = int(self.edit_en_player.text())
            total_adj_en = player_en + cons_totals["energy"] + self.attr_energy_bonus
            self.lbl_en_adj_val.setText(str(total_adj_en))
        except ValueError:
            self.lbl_en_adj_val.setText("---")

        # Emit signal for MainWindow
        # Construct final bonus map for attributes
        bonus_map = {}
        for aid, rtypes in attr_tracking.items():
            max_bonus = 0
            if "sup" in rtypes: max_bonus = 3
            elif "major" in rtypes: max_bonus = 2
            elif "minor" in rtypes: max_bonus = 1
            
            if self.active_weapon and WEAPONS[self.active_weapon]["attr"] == aid:
                max_bonus += 5
            
            bonus_map[aid] = max_bonus
            
        # Handle weapon-only bonus if not in runes
        if self.active_weapon:
            w_data = WEAPONS[self.active_weapon]
            aid = w_data["attr"]
            if aid not in bonus_map:
                bonus_map[aid] = 5

        # Update Group Box Title with Count
        self.runes_group.setTitle(f"Runes ({len(self.applied_runes)}/5)")

        self.stats_changed.emit(bonus_map, cons_totals)
