import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QScrollArea, QFrame, QPushButton, QCheckBox, QGroupBox, QComboBox, QLineEdit,
    QApplication, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QIcon, QPixmap
from src.constants import resource_path, PROF_MAP
from src.ui.theme import get_color

# --- Data Definitions ---

CONSUMABLES = {
    "apple": {"name": "Candy Apple", "icon": "apple.png", "stats": {"hp": 100, "energy": 10}},
    "corn": {"name": "Candy Corn", "icon": "corn.png", "stats": {"all_atts": 1}},
    "egg": {"name": "Golden Egg", "icon": "egg.png", "stats": {"all_atts": 1}},
    "lunar": {"name": "Lunar Fortune", "icon": "lunar.png", "stats": {"all_atts": 1}},
    "green_rock": {"name": "Green Rock Candy", "icon": "green_rock.png", "stats": {"attack_speed": 0.15, "activation": -0.15}},
    "blue_rock": {"name": "Blue Rock Candy", "icon": "blue_rock.png", "stats": {"attack_speed": 0.25, "activation": -0.20}},
    "red_rock": {"name": "Red Rock Candy", "icon": "red_rock.png", "stats": {"attack_speed": 0.33, "activation": -0.25}},
    "pie": {"name": "Pumpkin Pie", "icon": "pie.png", "stats": {"attack_speed": 0.25, "activation": -0.15}},
    "armor": {"name": "Armor of Salvation", "icon": "armor.png", "stats": {"crit_immunity": 0.50, "armor": 10, "hp_regen": 1, "incoming_dmg": -5}},
    "bu": {"name": "Essence of Celerity", "icon": "bu.png", "stats": {"move_speed": 0.20, "attack_speed": 0.20, "activation": -0.20, "recharge": -0.20}},
    "grail": {"name": "Grail of Might", "icon": "grail.png", "stats": {"hp": 100, "energy": 10, "all_atts": 1}},
    "cupcake": {"name": "Birthday Cupcake", "icon": "cupcake.png", "stats": {"hp": 100, "energy": 10, "move_speed": 0.25}}
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

CAPS = {"activation": -0.25, "attack_speed": 0.33, "move_speed": 0.34, "hp_regen": 10, "recharge": -0.50, "armor": 25, "all_atts": 20}

class ConsumableItem(QPushButton):
    toggled_state = pyqtSignal(str, bool)
    def __init__(self, key, data):
        super().__init__(); self.key, self.data = key, data
        self.setCheckable(True); self.setFixedSize(64, 64); self.setIconSize(QSize(48, 48))
        self.setToolTip(f"<b>{data['name']}</b><br/><br/>{self._format_stats(data['stats'])}")
        icon_path = resource_path(os.path.join("icons", "cons_icons", data['icon']))
        if os.path.exists(icon_path): self.setIcon(QIcon(icon_path))
        else: self.setText(data['name'][:2])
        self.refresh_theme(); self.toggled.connect(lambda checked: self.toggled_state.emit(self.key, checked))
    def refresh_theme(self):
        self.setStyleSheet(f"QPushButton {{ background-color: {get_color('slot_bg')}; border: 2px solid {get_color('slot_border')}; border-radius: 8px; padding: 0px; text-align: center; }} QPushButton:checked {{ background-color: {get_color('slot_bg_equipped')}; border: 2px solid #00FF00; }} QPushButton:hover {{ border-color: {get_color('border_accent')}; }} QToolTip {{ background-color: {get_color('tooltip_bg')}; color: {get_color('tooltip_text')}; border: 1px solid {get_color('border')}; padding: 4px; }}")
    def set_icon_size(self, size): self.setFixedSize(size, size); self.setIconSize(QSize(int(size * 0.75), int(size * 0.75)))
    def _format_stats(self, stats):
        lines = []
        for k, v in stats.items():
            val = f"{int(v*100)}%" if any(x in k for x in ["speed", "activation", "recharge", "crit"]) else str(v)
            lines.append(f"{k.replace('_', ' ').title()}: {val}")
        return "<br/>".join(lines)

class WeaponWidget(QWidget):
    toggled = pyqtSignal(str, bool)
    def __init__(self, key, data):
        super().__init__(); self.key, self.data = key, data
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(2); layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.button = QPushButton(); self.button.setCheckable(True); self.button.setFixedSize(80, 80)
        icon_path = resource_path(os.path.join("icons", "weapons_icons", data['icon']))
        if os.path.exists(icon_path): self.button.setIcon(QIcon(icon_path)); self.button.setIconSize(QSize(56, 56))
        self.button.toggled.connect(lambda checked: self.toggled.emit(self.key, checked))
        self.label = QLabel(f'"{data["name"]}"'); self.label.setWordWrap(True); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.label.setFixedWidth(140); self.label.setStyleSheet(f"font-size: 11px; color: {get_color('text_primary')}; font-style: italic;")
        layout.addWidget(self.button); layout.addWidget(self.label); self.refresh_theme()
    def set_icon_size(self, size): self.button.setFixedSize(size, size); self.button.setIconSize(QSize(int(size * 0.75), int(size * 0.75))); self.label.setFixedWidth(size + 60)
    def refresh_theme(self):
        radius = self.button.width() // 2
        self.button.setStyleSheet(f"QPushButton {{ background-color: {get_color('slot_bg')}; border: 1px dashed {get_color('slot_border')}; border-radius: {radius}px; }} QPushButton:checked {{ border: 3px solid #00FF00; background-color: {get_color('slot_bg_equipped')}; }} QPushButton:hover {{ border-color: {get_color('border_accent')}; }}")
        self.label.setStyleSheet(f"font-size: 11px; color: {get_color('text_primary')}; font-style: italic;")

class WeaponsPanel(QWidget):
    def __init__(self, parent_panel=None):
        super().__init__(); self.parent_panel = parent_panel; self.weapon_widgets = {}
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.group = QGroupBox("Weapons"); group_layout = QVBoxLayout(self.group); group_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setStyleSheet("background: transparent; border: none;"); container = QWidget(); vbox = QVBoxLayout(container); vbox.setSpacing(15); vbox.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        for key, data in WEAPONS.items():
            w = WeaponWidget(key, data); w.toggled.connect(self.on_weapon_toggled); self.weapon_widgets[key] = w; vbox.addWidget(w)
        scroll.setWidget(container); group_layout.addWidget(scroll); layout.addWidget(self.group); self.refresh_theme()
    def set_icon_size(self, size):
        for w in self.weapon_widgets.values(): w.set_icon_size(size)
    def on_weapon_toggled(self, key, checked):
        if checked:
            for k, w in self.weapon_widgets.items():
                if k != key: w.button.blockSignals(True); w.button.setChecked(False); w.button.blockSignals(False)
            if self.parent_panel: self.parent_panel.active_weapon = key
        elif self.parent_panel and self.parent_panel.active_weapon == key: self.parent_panel.active_weapon = None
        if self.parent_panel: self.parent_panel.update_stats()
    def select_weapon(self, key):
        if key in self.weapon_widgets: self.weapon_widgets[key].button.setChecked(True)
    def refresh_theme(self):
        self.group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {get_color('text_secondary')}; border: 1px solid {get_color('border')}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        for w in self.weapon_widgets.values(): w.refresh_theme()

class ScaledImageLabel(QLabel):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent); self._pixmap = pixmap
        self.setAlignment(Qt.AlignmentFlag.AlignCenter); self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    def resizeEvent(self, event):
        if not self._pixmap.isNull():
            # Use exactly 90% of available space as requested for the "perfect" size
            sz = self.size()
            target_sz = QSize(int(sz.width() * 0.9), int(sz.height() * 0.9))
            super().setPixmap(self._pixmap.scaled(target_sz, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        if event: super().resizeEvent(event)

class RuneSelectionPopup(QWidget):
    def __init__(self, parent=None, on_select=None):
        super().__init__(parent, Qt.WindowType.Popup); self.on_select = on_select
        self.setFixedSize(300, 400); self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(f"QWidget {{ background-color: {get_color('bg_secondary')}; border: 1px solid {get_color('border')}; border-radius: 8px; }} QScrollArea {{ border: none; }}")
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); layout.addWidget(scroll)
        self.container = QWidget(); self.vbox = QVBoxLayout(self.container); self.vbox.setSpacing(5); self.vbox.setAlignment(Qt.AlignmentFlag.AlignTop); scroll.setWidget(self.container)
    def add_option(self, text, icon_path, data, subtext=None):
        btn = QPushButton(); btn.setFixedHeight(64); btn.setStyleSheet(f"QPushButton {{ background-color: {get_color('slot_bg')}; border: 1px solid {get_color('slot_border')}; border-radius: 8px; text-align: left; padding-left: 10px; color: {get_color('text_primary')}; font-size: 14px; font-weight: bold; }} QPushButton:hover {{ background-color: {get_color('bg_hover')}; border: 1px solid {get_color('border_accent')}; }}")
        if icon_path and os.path.exists(icon_path): btn.setIcon(QIcon(icon_path)); btn.setIconSize(QSize(48, 48))
        if subtext:
            btn.setText(""); l = QVBoxLayout(btn); l.setContentsMargins(70, 5, 5, 5); l.setSpacing(0)
            m = QLabel(text); m.setStyleSheet("font-weight: bold; font-size: 14px; background: transparent; border: none;"); l.addWidget(m)
            s = QLabel(subtext); s.setStyleSheet(f"font-weight: normal; font-size: 11px; color: {get_color('text_secondary')}; background: transparent; border: none;"); l.addWidget(s); l.addStretch()
        else: btn.setText("   " + text)
        btn.clicked.connect(lambda checked, d=data: self.select_item(d)); self.vbox.addWidget(btn)
    def add_separator(self, text=None):
        if text: lbl = QLabel(text); lbl.setStyleSheet(f"color: {get_color('text_tertiary')}; font-weight: bold; padding: 10px 0 5px 5px;"); self.vbox.addWidget(lbl)
        else: line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setStyleSheet(f"background-color: {get_color('border')}; margin: 5px 0;"); self.vbox.addWidget(line)
    def select_item(self, data):
        if self.on_select: self.on_select(data)
        self.close()

class CharacterPanel(QWidget):
    stats_changed = pyqtSignal(dict, dict)
    def __init__(self):
        super().__init__(); self.active_cons = set(); self.applied_runes = [None] * 5; self.active_weapon = None; self.primary_prof_id = -1; self.attr_energy_bonus = 0; self.gender = "m"; self.con_widgets = []; self.group_boxes = []; self.base_stat_labels = []; self.rune_rows = []; self.init_ui()
    
    def minimumSizeHint(self):
        # Allow the panel to shrink very small to avoid layout locking
        return QSize(400, 300)

    def toggle_gender(self):
        self.gender = "f" if self.gender == "m" else "m"
        self.update_body_image()

    def update_body_image(self):
        # Mapping profession IDs to file prefixes
        mapping = {
            0: "body", 1: "warrior", 2: "ranger", 3: "monk", 4: "necro",
            5: "mesmer" if self.gender == "f" else "mes", # special case for mesmer naming
            6: "ele", 7: "sin", 8: "rit", 9: "para", 10: "derv"
        }
        prefix = mapping.get(self.primary_prof_id, "body")
        if self.primary_prof_id == 0:
            fname = "body.png"
        else:
            fname = f"{prefix}_{self.gender}.png"
        
        path = resource_path(os.path.join("icons", "profession_images", fname))
        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self.lbl_body_img._pixmap = pix
                # Trigger a resize event to refresh the scaled pixmap
                self.lbl_body_img.resizeEvent(None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'cons_group'): 
            # Halved spacing and increased margin buffer to ensure icons stay contained
            self.set_icon_size(max(32, min(96, (self.cons_group.width() - 80) // 6)))
        if hasattr(self, 'runes_group'):
            # Use current width for calculations, but avoid hard-locking minimum width
            w = self.width()
            btn_size = max(48, min(256, w // 18))
            rg_h = self.runes_group.height()
            
            is_light = get_color('bg_primary') == '#FFFFFF'
            title_color = "black" if is_light else get_color('text_primary')
            empty_color = "black" if is_light else get_color('text_secondary')

            for slot in self.rune_slots:
                slot["btn"].setFixedSize(btn_size, btn_size)
                slot["btn"].setIconSize(QSize(int(btn_size * 0.75), int(btn_size * 0.75)))
                slot["btn"].setStyleSheet(slot["btn"].styleSheet().replace(f"border-radius: {getattr(self, '_last_rad', 32)}px;", f"border-radius: {btn_size//2}px;"))
                
                old_text = slot["label"].text()
                if "Empty" in old_text:
                    slot["label"].setText(f"<b style='color:{title_color};'>{slot['slot_name']}</b><br><span style='color:{empty_color};'>Empty</span>")
                else:
                    slot["label"].setText(old_text.replace("color:white", f"color:{title_color}").replace("color:black", f"color:{title_color}"))

            self.btn_weapon.setFixedSize(btn_size, btn_size)
            self.btn_weapon.setIconSize(QSize(int(btn_size * 0.75), int(btn_size * 0.75)))
            self.btn_weapon.setStyleSheet(self.btn_weapon.styleSheet().replace(f"border-radius: {getattr(self, '_last_rad', 32)}px;", f"border-radius: {btn_size//2}px;"))
            
            old_w_text = self.lbl_weapon.text()
            if "Empty" in old_w_text:
                self.lbl_weapon.setText(f"<b style='color:{title_color};'>Weapon</b><br><span style='color:{empty_color};'>Empty</span>")
            else:
                self.lbl_weapon.setText(old_w_text.replace("color:white", f"color:{title_color}").replace("color:black", f"color:{title_color}"))

            self._last_rad = btn_size // 2
            
            stagger = btn_size // 2
            for i, row in enumerate(self.rune_rows):
                if i in [0, 4]: row.setContentsMargins(0, 0, stagger, 0)
                else: row.setContentsMargins(stagger, 0, 0, 0)
            
            self.weapon_layout.setContentsMargins(0, int(rg_h * 0.18), 0, 0)
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and isinstance(obj, QComboBox): event.ignore(); return True
        return super().eventFilter(obj, event)
    def clear_runes(self):
        for i in range(5): self.set_rune_slot(i, None)
        self.update_stats()
    def clear_consumables(self):
        self.active_cons = set(); 
        for w in self.con_widgets: w.blockSignals(True); w.setChecked(False); w.blockSignals(False)
        self.update_stats()
    def set_primary_profession(self, pid):
        try: pid = int(pid)
        except: pid = 0
        if self.primary_prof_id == pid: return
        self.primary_prof_id = pid; self.combo_headpiece.blockSignals(True); self.combo_headpiece.clear(); self.combo_headpiece.addItem("None", None)
        if pid > 0:
            from src.constants import PROF_ATTRS, ATTR_MAP
            for aid in PROF_ATTRS.get(pid, []): self.combo_headpiece.addItem(f"{ATTR_MAP.get(aid, f'Attr {aid}')} +1", aid)
        self.combo_headpiece.blockSignals(False)
        self.combo_headpiece.setEnabled(pid > 0)
        # Apply current theme style to the combo
        self.refresh_theme()
        for i, r in enumerate(self.applied_runes):
            if r and r.get("prof_id") and r.get("prof_id") != pid: self.set_rune_slot(i, None)
        self.update_body_image(); self.update_stats()

    def set_attr_energy_bonus(self, amount):
        if self.attr_energy_bonus != amount: self.attr_energy_bonus = amount; self.update_stats()
    def set_icon_size(self, size):
        for w in self.con_widgets: w.set_icon_size(size)
    def refresh_theme(self):
        is_light = get_color('bg_primary') == '#FFFFFF'
        h_color = "black" if is_light else "#FFD700"
        v_color = "#00AAFF" if is_light else "white"
        t_color = "black" if is_light else get_color('text_primary')
        
        self.lbl_stats.setStyleSheet(f"color: {get_color('text_primary')};")
        self.lbl_runes.setStyleSheet(f"color: {get_color('text_primary')};")
        
        # Explicit combo styling to ensure visibility
        combo_s = f"QComboBox {{ background-color: {get_color('btn_bg')}; color: {get_color('btn_text')}; border: 1px solid {get_color('border')}; border-radius: 4px; padding-left: 5px; }} QComboBox::drop-down {{ border: none; }} QComboBox QAbstractItemView {{ background-color: {get_color('bg_secondary')}; color: {get_color('text_primary')}; selection-background-color: {get_color('bg_selected')}; }}"
        if hasattr(self, 'combo_headpiece'): self.combo_headpiece.setStyleSheet(combo_s)

        # Remove shadows in light mode
        if is_light:
            self.lbl_hp_adj_val.setGraphicsEffect(None)
            self.lbl_en_adj_val.setGraphicsEffect(None)
            self.lbl_stats.setGraphicsEffect(None)
            self.lbl_runes.setGraphicsEffect(None)

        if hasattr(self, 'lbl_rune_hint'): self.lbl_rune_hint.setStyleSheet(f"color: {get_color('text_primary')}; font-size: 12px; font-style: italic;")
        btn_s = f"QPushButton {{ background-color: {get_color('bg_hover')}; color: {get_color('text_warning')}; border: 1px solid {get_color('border')}; border-radius: 4px; padding: 4px; font-weight: bold; }} QPushButton:hover {{ background-color: {get_color('bg_selected')}; }}"
        if hasattr(self, 'btn_clear_runes'): self.btn_clear_runes.setStyleSheet(btn_s)
        if hasattr(self, 'btn_clear_cons'): self.btn_clear_cons.setStyleSheet(btn_s)
        if hasattr(self, 'btn_swap_gender'):
            self.btn_swap_gender.setStyleSheet(f"QPushButton {{ background-color: {get_color('bg_secondary')}; border: 1px solid {get_color('border')}; border-radius: 4px; color: {get_color('text_primary')}; font-size: 16px; }} QPushButton:hover {{ background-color: {get_color('bg_hover')}; }}")
        gs = f"QGroupBox {{ font-weight: bold; color: {get_color('text_secondary')}; border: 1px solid {get_color('border')}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}"
        for gb in self.group_boxes: gb.setStyleSheet(gs)
        if hasattr(self, 'lbl_stats_header'): self.lbl_stats_header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {h_color};")
        if hasattr(self, 'lbl_runes_header'): self.lbl_runes_header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {h_color};")
        if hasattr(self, 'lbl_hp_player'): self.lbl_hp_player.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {h_color};")
        if hasattr(self, 'lbl_en_player'): self.lbl_en_player.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {h_color};")
        if hasattr(self, 'lbl_hb'): self.lbl_hb.setStyleSheet(f"font-size: 11px; color: {t_color}; font-weight: bold;")
        if hasattr(self, 'lbl_hp_adj_val'): self.lbl_hp_adj_val.setStyleSheet(f"font-weight: bold; color: {v_color}; font-size: 20px;")
        if hasattr(self, 'lbl_en_adj_val'): self.lbl_en_adj_val.setStyleSheet(f"font-weight: bold; color: {v_color}; font-size: 20px;")
        for w in self.con_widgets: w.refresh_theme()
        if hasattr(self, 'active_weapon'): self.set_weapon_slot(self.active_weapon)
        if hasattr(self, 'applied_runes'):
            for i, r in enumerate(self.applied_runes): self.set_rune_slot(i, r)
    def show_weapon_menu(self):
        from src.constants import ATTR_MAP; p = RuneSelectionPopup(self, on_select=self.set_weapon_slot); p.add_option("Clear Weapon", None, None); p.add_separator("Weapons")
        for k, d in WEAPONS.items():
            attr_name = ATTR_MAP.get(d['attr'], f"Attr {d['attr']}")
            p.add_option(d["name"], resource_path(os.path.join("icons", "weapons_icons", d["icon"])), k, subtext=f"{attr_name} +5")
        pos = self.btn_weapon.mapToGlobal(self.btn_weapon.rect().bottomLeft())
        if pos.y() + p.height() > QApplication.primaryScreen().geometry().height(): pos.setY(pos.y() - p.height() - self.btn_weapon.height())
        p.move(pos); p.show()
    def set_weapon_slot(self, k):
        self.active_weapon = k; is_light = get_color('bg_primary') == '#FFFFFF'; ec = "black" if is_light else get_color('text_secondary'); tc = "black" if is_light else get_color('text_primary'); eb = "#FFFFFF" if is_light else get_color('slot_bg')
        if k in WEAPONS:
            d = WEAPONS[k]; self.btn_weapon.setIcon(QIcon(resource_path(os.path.join("icons", "weapons_icons", d["icon"])))); self.btn_weapon.setStyleSheet(f"QPushButton {{ background-color: {get_color('slot_bg')}; border: 2px solid #00FF00; border-radius: {self.btn_weapon.width()//2}px; }}")
            self.lbl_weapon.setText(f"<b style='color:{tc};'>Weapon</b><br><span style='color:{get_color('text_accent')};'>{d['name']}</span>")
        else:
            self.btn_weapon.setIcon(QIcon()); self.btn_weapon.setStyleSheet(f"QPushButton {{ background-color: {eb}; border: 2px dashed {get_color('slot_border')}; border-radius: {self.btn_weapon.width()//2}px; }} QPushButton:hover {{ border: 2px solid {get_color('text_accent')}; }}")
            self.lbl_weapon.setText(f"<b style='color:{tc};'>Weapon</b><br><span style='color:{ec};'>Empty</span>")
        self.update_stats()
    def show_rune_menu(self, idx):
        p = RuneSelectionPopup(self, on_select=lambda d: self.set_rune_slot(idx, d)); p.add_option("Clear Slot", None, None); p.add_separator()
        p.add_option("Attunement Rune", resource_path(os.path.join("icons", "runes_icons", "attunement.png")), {"rtype": "attunement", "attr_id": "attunement", "name": "Attunement Rune", "icon": "attunement.png"})
        p.add_option("Rune of Vitae", resource_path(os.path.join("icons", "runes_icons", "attunement.png")), {"rtype": "vitae", "attr_id": "vitae", "name": "Rune of Vitae", "icon": "attunement.png"})
        p.add_separator(); v_icons = ["minor_vig.png", "major_vig.png", "sup_vig.png"]; v_names = ["Minor Vigor", "Major Vigor", "Superior Vigor"]; v_types = ["minor", "major", "sup"]
        for i in range(3): p.add_option(v_names[i], resource_path(os.path.join("icons", "runes_icons", v_icons[i])), {"rtype": v_types[i], "attr_id": "vigor", "name": v_names[i], "icon": v_icons[i]})
        if self.primary_prof_id > 0:
            from src.constants import PROF_ATTRS, ATTR_MAP; pid = self.primary_prof_id; pref = {1: "war", 2: "ran", 3: "mo", 4: "nec", 5: "mes", 6: "ele", 7: "sin", 8: "rit", 9: "para", 10: "derv"}.get(pid, "war"); p.add_separator()
            for aid in PROF_ATTRS.get(pid, []):
                attr_n = ATTR_MAP.get(aid, f"Attr {aid}"); p.add_separator(attr_n)
                for suf, sn in [("minor", "Minor"), ("major", "Major"), ("sup", "Superior")]:
                    ic = f"{pref}_{suf}.png"; p.add_option(f"{sn} {attr_n}", resource_path(os.path.join("icons", "runes_icons", ic)), {"rtype": suf, "prof_id": pid, "attr_id": aid, "name": f"{sn} {attr_n}", "icon": ic})
        btn = self.rune_slots[idx]["btn"]; pos = btn.mapToGlobal(btn.rect().bottomLeft())
        if idx >= 3: pos.setY(pos.y() - p.height() - btn.height())
        p.move(pos); p.show()
    def set_rune_slot(self, idx, d):
        self.applied_runes[idx] = d; slot = self.rune_slots[idx]; is_light = get_color('bg_primary') == '#FFFFFF'; ec = "black" if is_light else get_color('text_secondary'); tc = "black" if is_light else get_color('text_primary'); eb = "#FFFFFF" if is_light else get_color('slot_bg')
        if d:
            slot["btn"].setIcon(QIcon(resource_path(os.path.join("icons", "runes_icons", d["icon"])))); slot["btn"].setStyleSheet(f"QPushButton {{ background-color: {get_color('slot_bg')}; border: 2px solid #00FF00; border-radius: {slot['btn'].width()//2}px; }}")
            slot["label"].setText(f"<b style='color:{tc};'>{slot['slot_name']}</b><br><span style='color:{get_color('text_accent')};'>{d['name']}</span>")
        else:
            slot["btn"].setIcon(QIcon()); slot["btn"].setStyleSheet(f"QPushButton {{ background-color: {eb}; border: 2px dashed {get_color('slot_border')}; border-radius: {slot['btn'].width()//2}px; }} QPushButton:hover {{ border: 2px solid {get_color('text_accent')}; }}")
            slot["label"].setText(f"<b style='color:{tc};'>{slot['slot_name']}</b><br><span style='color:{ec};'>Empty</span>")
        self.update_stats()
    def init_ui(self):
        l = QHBoxLayout(self); l.setContentsMargins(10, 10, 10, 10); l.setSpacing(20); rv = QVBoxLayout(); rv.setSpacing(20)
        self.stats_group = QGroupBox("Consumable Calculations"); self.group_boxes.append(self.stats_group); rv.addWidget(self.stats_group, stretch=2)
        sm = QVBoxLayout(self.stats_group); sc_stats = QScrollArea(); sc_stats.setWidgetResizable(True); sc_stats.setStyleSheet("background: transparent; border: none;"); sm.addWidget(sc_stats)
        st_cont = QWidget(); st_lay = QHBoxLayout(st_cont); st_lay.setContentsMargins(0, 0, 0, 0); st_lay.setSpacing(40); sc_stats.setWidget(st_cont)
        
        sv = QVBoxLayout(); sv.setSpacing(10); sv.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_stats_header = QLabel("Stats:"); self.lbl_stats_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;"); sv.addWidget(self.lbl_stats_header)
        self.lbl_stats = QLabel("No effects."); self.lbl_stats.setWordWrap(True); sv.addWidget(self.lbl_stats)
        
        rv2 = QVBoxLayout(); rv2.setSpacing(10); rv2.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_runes_header = QLabel("Attributes:"); self.lbl_runes_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;"); rv2.addWidget(self.lbl_runes_header)
        self.lbl_runes = QLabel("No effects."); self.lbl_runes.setWordWrap(True); rv2.addWidget(self.lbl_runes)
        
        st_lay.addLayout(sv, stretch=1); st_lay.addLayout(rv2, stretch=1)
        self.cons_group = QGroupBox("Consumables"); self.group_boxes.append(self.cons_group); cl = QVBoxLayout(self.cons_group); self.btn_clear_cons = QPushButton("Clear Consumables"); self.btn_clear_cons.setFixedWidth(120); self.btn_clear_cons.clicked.connect(self.clear_consumables); cl.addWidget(self.btn_clear_cons)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setStyleSheet("background: transparent; border: none;"); cc = QWidget(); self.cons_grid = QGridLayout(cc); self.cons_grid.setSpacing(10)
        for i, k in enumerate(["apple", "corn", "egg", "lunar", "cupcake", "pie", "green_rock", "blue_rock", "red_rock", "armor", "bu", "grail"]):
            it = ConsumableItem(k, CONSUMABLES[k]); it.toggled_state.connect(self.on_con_toggled); self.con_widgets.append(it); self.cons_grid.addWidget(it, i//6, i%6)
        sc.setWidget(cc); cl.addWidget(sc); rv.addWidget(self.cons_group, stretch=2); self.runes_group = QGroupBox("Runes (0/5)"); self.group_boxes.append(self.runes_group); rl = QVBoxLayout(self.runes_group)
        tb = QHBoxLayout(); sg = QGridLayout(); sg.setSpacing(10); self.lbl_hp_player = QLabel("Health:"); self.lbl_hp_player.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;"); self.lbl_hp_adj_val = QLabel("480"); self.lbl_hp_adj_val.setStyleSheet("font-weight: bold; color: white; font-size: 20px;")
        sg.addWidget(self.lbl_hp_player, 0, 0); sg.addWidget(self.lbl_hp_adj_val, 0, 1); self.lbl_en_player = QLabel("Energy:"); self.lbl_en_player.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;"); self.lbl_en_adj_val = QLabel("20"); self.lbl_en_adj_val.setStyleSheet("font-weight: bold; color: white; font-size: 20px;")
        sg.addWidget(self.lbl_en_player, 1, 0); sg.addWidget(self.lbl_en_adj_val, 1, 1); tb.addLayout(sg); tb.addStretch(); self.btn_clear_runes = QPushButton("Clear Runes"); self.btn_clear_runes.setFixedWidth(100); self.btn_clear_runes.clicked.connect(self.clear_runes); tb.addWidget(self.btn_clear_runes); rl.addLayout(tb); rl.addStretch(0)
        bs = QHBoxLayout(); bs.setSpacing(20); rl.addLayout(bs, stretch=100); op = QPixmap(resource_path(os.path.join("icons", "profession_images", "body.png")))
        
        # Weapon Selection on the Left
        wc = QWidget(); self.weapon_layout = QVBoxLayout(wc); self.weapon_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter); self.weapon_layout.setContentsMargins(0, 100, 0, 0)
        self.btn_weapon = QPushButton(); self.btn_weapon.setFixedSize(64, 64); self.btn_weapon.setIconSize(QSize(48, 48)); self.btn_weapon.setStyleSheet(f"QPushButton {{ background-color: {get_color('slot_bg')}; border: 2px dashed {get_color('slot_border')}; border-radius: 32px; }} QPushButton:hover {{ border: 2px solid {get_color('text_accent')}; }}"); self.btn_weapon.clicked.connect(self.show_weapon_menu)
        self.lbl_weapon = QLabel(f"<b>Weapon</b><br><span style='color:{get_color('text_secondary')};'>Empty</span>"); self.lbl_weapon.setAlignment(Qt.AlignmentFlag.AlignHCenter); self.weapon_layout.addWidget(self.btn_weapon, alignment=Qt.AlignmentFlag.AlignHCenter); self.weapon_layout.addWidget(self.lbl_weapon, alignment=Qt.AlignmentFlag.AlignHCenter); bs.addWidget(wc, stretch=0)
        
        # Character Image in the Center with Swap Button
        mid_cont = QWidget(); mid_lay = QVBoxLayout(mid_cont); mid_lay.setContentsMargins(0, 0, 0, 0); mid_lay.setSpacing(5)
        self.lbl_body_img = ScaledImageLabel(op); mid_lay.addWidget(self.lbl_body_img, stretch=10)
        
        self.btn_swap_gender = QPushButton("⇆"); self.btn_swap_gender.setFixedSize(32, 32); self.btn_swap_gender.setToolTip("Swap Gender")
        self.btn_swap_gender.clicked.connect(self.toggle_gender)
        mid_lay.addWidget(self.btn_swap_gender, alignment=Qt.AlignmentFlag.AlignCenter)
        
        bs.addWidget(mid_cont, stretch=10)
        
        # Armor Selection on the Right
        slc = QWidget(); slc.setMinimumWidth(260); sll = QVBoxLayout(slc); sll.setSpacing(5); sll.setContentsMargins(0, 0, 0, 0)

        # Move Bonus above headpiece as requested
        hbl = QHBoxLayout(); hbl.setContentsMargins(10, 0, 0, 0); self.lbl_hb = QLabel("Headpiece Bonus:"); self.combo_headpiece = QComboBox()
        from PyQt6.QtWidgets import QListView
        self.combo_headpiece.setView(QListView())
        self.combo_headpiece.setFixedWidth(150); self.combo_headpiece.addItem("None", None); self.combo_headpiece.currentIndexChanged.connect(self.update_stats)

        # Ensure it opens upwards if space is limited
        self.combo_headpiece.setMaxVisibleItems(10)
        hbl.addWidget(self.lbl_hb); hbl.addWidget(self.combo_headpiece); hbl.addStretch(); sll.addLayout(hbl)

        self.rune_slots = []; sn = ["Headpiece", "Chestpiece", "Gloves", "Leggings", "Boots"]
        for i in range(5):
            rw = QHBoxLayout(); rw.setAlignment(Qt.AlignmentFlag.AlignLeft); self.rune_rows.append(rw); rw.setContentsMargins(0, 0, 32, 0) if i in [0, 4] else rw.setContentsMargins(32, 0, 0, 0)
            bt = QPushButton(); bt.setFixedSize(64, 64); bt.setIconSize(QSize(48, 48)); bt.setStyleSheet(f"QPushButton {{ background-color: {get_color('slot_bg')}; border: 2px dashed {get_color('slot_border')}; border-radius: 32px; }} QPushButton:hover {{ border: 2px solid {get_color('text_accent')}; }}"); bt.clicked.connect(lambda c, x=i: self.show_rune_menu(x))
            lbl = QLabel(f"<b>{sn[i]}</b><br><span style='color:{get_color('text_secondary')};'>Empty</span>"); rw.addWidget(bt); rw.addWidget(lbl); rw.addStretch(); sll.addLayout(rw); self.rune_slots.append({"btn": bt, "label": lbl, "slot_name": sn[i]})
        
        bs.addWidget(slc, stretch=0); bs.addStretch(1); l.addLayout(rv, stretch=4); l.addWidget(self.runes_group, stretch=6); self.update_stats()
    def on_con_toggled(self, k, c):
        if c: self.active_cons.add(k)
        else: self.active_cons.discard(k)
        self.update_stats()
    def toggle_consumable(self, k, c):
        for w in self.con_widgets:
            if w.key == k: w.setChecked(c); break
    def get_total_energy(self):
        be = self.attr_energy_bonus
        for k in self.active_cons: be += CONSUMABLES[k]["stats"].get("energy", 0)
        for r in self.applied_runes:
            if r and r.get("attr_id") == "attunement": be += 2
        return 20 + be
    def get_base_stats(self):
        # Default bases
        hp, energy = 480, 20
        pid = self.primary_prof_id
        
        # Base Energy mapping
        if pid in [2, 7, 10]: energy = 25 # Ranger, Assassin, Dervish
        elif pid in [3, 4, 5, 6, 8, 9]: energy = 30 # Monk, Necro, Mesmer, Ele, Rit, Paragon
        
        # Base HP mapping
        if pid == 10: hp = 505 # Dervish
        
        return hp, energy

    def update_stats(self):
        ct = {"hp": 0, "energy": 0, "all_atts": 0, "armor": 0, "hp_regen": 0, "incoming_dmg": 0, "attack_speed": 0.0, "activation": 0.0, "move_speed": 0.0, "recharge": 0.0, "crit_immunity": 0.0}
        for k in self.active_cons:
            for sk, v in CONSUMABLES[k]["stats"].items():
                if sk in ct: ct[sk] += v
        atr = {}; vc = {"minor": 0, "major": 0, "sup": 0}; ac = vtc = hp = 0
        for r in self.applied_runes:
            if not r: continue
            aid = r.get("attr_id")
            if aid == "attunement": ac += 1; continue
            if aid == "vitae": vtc += 1; continue
            rt = r["rtype"]
            if aid != "vigor":
                if rt == "major": hp -= 35
                elif rt == "sup": hp -= 75
                if aid not in atr: atr[aid] = {}
                atr[aid][rt] = atr[aid].get(rt, 0) + 1
            else: vc[rt] += 1
        
        base_hp, base_en = self.get_base_stats()
        ct["energy"] += (ac * 2); thp = ct["hp"] + (50 if vc["sup"] > 0 else 41 if vc["major"] > 0 else 30 if vc["minor"] > 0 else 0) + (vtc * 10) + hp
        for k in CAPS:
            if k in ["activation", "recharge"]: ct[k] = max(ct[k], CAPS[k])
            else: ct[k] = min(ct[k], CAPS[k])
        
        def fl(l, v, d=None):
            h = f"<span style='font-size:14px; color:{get_color('text_primary')};'>• <b>{l}:</b> {v}</span>"
            if d: h += f"<br><span style='font-size:12px; color:{get_color('text_secondary')};'>&nbsp;&nbsp;&nbsp;({', '.join(d)})</span>"
            return h + "<br><br>"

        # --- Expanded Stats Tracking ---
        stats_html = ""
        hp_details = []
        if any(vc.values()): hp_details.append("Vigor")
        if vtc > 0: hp_details.append(f"x{vtc} Vitae")
        if thp != 0 or hp_details:
            stats_html += fl("Health", f"+{thp}" if thp > 0 else str(thp), hp_details if hp_details else None)
        
        if ct["energy"] != 0: stats_html += fl("Energy", f"+{ct['energy']}")
        if ct["armor"] != 0: stats_html += fl("Armor", f"+{ct['armor']}")
        if ct["hp_regen"] != 0: stats_html += fl("HP Regen", f"+{ct['hp_regen']}")
        if ct["incoming_dmg"] != 0: stats_html += fl("Dmg Reduction", str(ct["incoming_dmg"]))
        if ct["attack_speed"] != 0: stats_html += fl("Attack Speed", f"+{int(ct['attack_speed']*100)}%")
        if ct["activation"] != 0: stats_html += fl("Faster Cast", f"{int(abs(ct['activation'])*100)}%")
        if ct["recharge"] != 0: stats_html += fl("Faster Recharge", f"{int(abs(ct['recharge'])*100)}%")
        if ct["move_speed"] != 0: stats_html += fl("Move Speed", f"+{int(ct['move_speed']*100)}%")
        if ct["crit_immunity"] != 0: stats_html += fl("Crit Immunity", f"{int(ct['crit_immunity']*100)}%")

        self.lbl_stats.setText(stats_html if stats_html else "No effects.")
        
        attr_text = ""; has_attrs = False
        if ct["all_atts"] > 0: attr_text += fl("All Attributes", f"+{min(ct['all_atts'], 20)}"); has_attrs = True
        if self.active_weapon in WEAPONS: atr[WEAPONS[self.active_weapon]["attr"]] = atr.get(WEAPONS[self.active_weapon]["attr"], {})
        hb = self.combo_headpiece.currentData()
        if hb is not None: atr[hb] = atr.get(hb, {})
        from src.constants import ATTR_MAP
        for aid, rts in sorted(atr.items()):
            mb = (3 if "sup" in rts else 2 if "major" in rts else 1 if "minor" in rts else 0)
            if self.active_weapon and WEAPONS[self.active_weapon]["attr"] == aid: mb += 5
            if hb == aid: mb += 1
            det = [f"x{rts[r]} {r.title()}" for r in ["sup", "major", "minor"] if r in rts]
            if hb == aid: det.append("Headpiece")
            if self.active_weapon and WEAPONS[self.active_weapon]["attr"] == aid: det.append(f'"{WEAPONS[self.active_weapon]["name"]}"')
            attr_text += fl(ATTR_MAP.get(aid, f"Attr {aid}"), f"+{mb}", det); has_attrs = True
        self.lbl_runes.setText(attr_text if has_attrs else "No effects.")
        
        self.lbl_hp_adj_val.setText(str(base_hp + thp)); self.lbl_en_adj_val.setText(str(base_en + ct["energy"] + self.attr_energy_bonus))
        bm = {a: (3 if "sup" in rs else 2 if "major" in rs else 1 if "minor" in rs else 0) + (5 if self.active_weapon and WEAPONS[self.active_weapon]["attr"] == a else 0) + (1 if hb == a else 0) for a, rs in atr.items()}
        if self.active_weapon:
            wa = WEAPONS[self.active_weapon]["attr"]
            if wa not in bm: bm[wa] = 5
        if hb is not None and hb not in bm: bm[hb] = 1
        self.runes_group.setTitle(f"Runes ({sum(1 for r in self.applied_runes if r is not None)}/5)"); self.stats_changed.emit(bm, ct)
