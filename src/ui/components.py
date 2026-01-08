import os
from PyQt6.QtWidgets import (
    QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy, QListWidget, QStyle, QStyledItemDelegate, QListWidgetItem, QAbstractItemView, QScrollArea, QWidget, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QSize, QRect, QUrl
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont, QIcon, QDesktopServices

from src.constants import ICON_DIR, ICON_SIZE, ATTR_MAP, PROF_MAP, PROF_SHORT_MAP, PIXMAP_CACHE
from src.models import Skill, Build
from src.ui.theme import get_color

class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

class DraggableSkillIcon(QLabel):
    clicked = pyqtSignal(Skill)

    def __init__(self, skill: Skill, parent=None, size=None):
        super().__init__(parent)
        self.skill = skill
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Initialize with correct size and use cache
        current_size = size or ICON_SIZE
        self.set_icon_size(current_size)

    def refresh_theme(self):
        if not self.pixmap():
            self.setStyleSheet(f"border: 1px solid {get_color('slot_border')}; background-color: {get_color('input_bg')}; color: {get_color('text_primary')};")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.skill)
            
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(str(self.skill.id))
            drag.setMimeData(mime_data)
            
            if self.pixmap():
                drag.setPixmap(self.pixmap())
                drag.setHotSpot(QPoint(self.width() // 2, self.height() // 2))
                
            drag.exec(Qt.DropAction.CopyAction)

    def set_icon_size(self, size):
        self.setFixedSize(size, size)
        
        # Use size-aware caching
        cache_key = f"{self.skill.icon_filename}_{size}"
        if cache_key in PIXMAP_CACHE:
            self.setPixmap(PIXMAP_CACHE[cache_key])
        else:
            path = os.path.join(ICON_DIR, self.skill.icon_filename)
            if os.path.exists(path):
                pix = QPixmap(path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                PIXMAP_CACHE[cache_key] = pix
                self.setPixmap(pix)
            else:
                self.setText(self.skill.name[:2])
                self.refresh_theme()

class SkillSlot(QFrame):
    skill_equipped = pyqtSignal(int, int) 
    skill_removed = pyqtSignal(int)       
    skill_swapped = pyqtSignal(int, int)
    clicked = pyqtSignal(int)             

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.current_skill_id = None
        self.is_ghost = False
        self.drag_start_pos = None
        
        self.setFixedSize(ICON_SIZE + 4, ICON_SIZE + 4)
        self.setAcceptDrops(True)
        self.refresh_theme()
        
        self.icon_label = QLabel(self)
        self.icon_label.setGeometry(2, 2, ICON_SIZE, ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) 

    def refresh_theme(self):
        self.update_style()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
            self.setStyleSheet(f"border: 2px solid {get_color('border_accent')}; background-color: {get_color('slot_bg_drag')};")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.update_style()

    def dropEvent(self, event):
        try:
            mime_text = event.mimeData().text()
            if mime_text.startswith("slot:"):
                source_index = int(mime_text.split(":")[1])
                if source_index != self.index:
                    self.skill_swapped.emit(source_index, self.index)
                event.accept()
            # Explicitly reject build reordering drops
            elif mime_text.startswith("reorder_build:"):
                event.ignore()
            else:
                skill_id = int(mime_text)
                self.skill_equipped.emit(self.index, skill_id)
                event.accept()
        except ValueError:
            event.ignore()
        finally:
            self.update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_skill_id is not None:
                self.drag_start_pos = event.position().toPoint()
                self.clicked.emit(self.current_skill_id)
                    
        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_skill_id is not None:
                self.clear_slot()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if not self.drag_start_pos:
            return
        if self.current_skill_id is None or self.is_ghost:
            return
            
        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        # Prefix with "slot:" to distinguish from library drags
        mime_data.setText(f"slot:{self.index}")
        drag.setMimeData(mime_data)
        
        pix = self.icon_label.pixmap()
        if pix and not pix.isNull():
            drag.setPixmap(pix)
            drag.setHotSpot(QPoint(ICON_SIZE // 2, ICON_SIZE // 2))
        
        # Execute Drag
        result = drag.exec(Qt.DropAction.MoveAction)
        
        # If result is IgnoreAction, it means it wasn't dropped on a valid drop target (including self)
        # So we treat it as "dragged off bar" -> remove.
        if result == Qt.DropAction.IgnoreAction:
            self.clear_slot()

    def mouseDoubleClickEvent(self, event):
        if self.current_skill_id is not None:
            if self.is_ghost:
                self.skill_equipped.emit(self.index, self.current_skill_id)
            else:
                self.clear_slot()

    def set_skill(self, skill_id, skill_obj: Skill = None, ghost=False, confidence=0.0, rank=0, bonuses: dict = None, global_act=0.0, global_rech=0.0):
        self.current_skill_id = skill_id
        self.is_ghost = ghost
        
        icon_file = skill_obj.icon_filename if skill_obj else f"{skill_id}.jpg"
        if not icon_file.lower().endswith('.jpg'):
            icon_file += '.jpg'
            
        path = os.path.join(ICON_DIR, icon_file)
        
        pix = QPixmap()
        if os.path.exists(path):
            pix.load(path)
        else:
            pix = QPixmap(ICON_SIZE, ICON_SIZE)
            pix.fill(QColor(get_color("bg_hover")))
            p = QPainter(pix)
            p.setPen(QColor(get_color("text_primary")))
            p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, skill_obj.name if skill_obj else str(skill_id))
            p.end()

        if ghost:
            transparent_pix = QPixmap(pix.size())
            transparent_pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(transparent_pix)
            p.setOpacity(0.4)
            p.drawPixmap(0, 0, pix)
            p.end()
            self.icon_label.setPixmap(transparent_pix)
        else:
            self.icon_label.setPixmap(pix)

        # Build detailed tooltip
        if skill_obj:
            desc = skill_obj.get_description_for_rank(rank, bonuses)
            attr_name = ATTR_MAP.get(skill_obj.attribute, "None")
            tooltip = f"<b>{skill_obj.name}</b><br/>"
            if skill_obj.attribute != -1:
                tooltip += f"<i>{attr_name} ({rank})</i><br/>"
            
            if skill_obj.skill_type:
                tooltip += f"<i>{skill_obj.skill_type.title()}</i><br/>"
            
            # Energy Cost in Tooltip
            eff_energy = skill_obj.get_effective_energy(rank, bonuses)
            if skill_obj.energy > 0:
                if eff_energy < skill_obj.energy:
                    tooltip += f"Energy: <span style='color:#00FF00;'>{eff_energy}</span> (Base: {skill_obj.energy})<br/>"
                else:
                    tooltip += f"Energy: {skill_obj.energy}<br/>"

            # Cast & Recharge in Tooltip
            eff_act = skill_obj.get_effective_activation(rank, bonuses, global_act)
            if eff_act < skill_obj.activation:
                tooltip += f"Activation: <span style='color:#00FF00;'>{eff_act}s</span> (Base: {skill_obj.activation}s)<br/>"
            else:
                tooltip += f"Activation: {skill_obj.activation}s<br/>"

            eff_rech = skill_obj.get_effective_recharge(rank, bonuses, global_rech)
            if skill_obj.recharge > 0:
                if eff_rech < skill_obj.recharge:
                    tooltip += f"Recharge: <span style='color:#00FF00;'>{eff_rech}s</span> (Base: {skill_obj.recharge}s)<br/>"
                else:
                    tooltip += f"Recharge: {skill_obj.recharge}s<br/>"

            tooltip += f"<br/>{desc}"
            
            if ghost:
                if isinstance(confidence, str):
                    tooltip = f"<b>Smart Synergy:</b> {confidence}<br/><hr/>" + tooltip
                else:
                    tooltip = f"<b>Synergy: {confidence:.0%}</b><br/><hr/>" + tooltip
            
            self.setToolTip(tooltip)
        else:
            self.setToolTip(str(skill_id))

        self.update_style()

    def clear_slot(self, silent=False):
        self.current_skill_id = None
        self.is_ghost = False
        self.icon_label.clear()
        self.setToolTip("")
        if not silent:
            self.skill_removed.emit(self.index)
        self.update_style()

    def update_style(self):
        if self.current_skill_id and not self.is_ghost:
            self.setStyleSheet(f"border: 2px solid {get_color('border_light')}; background-color: {get_color('slot_bg_equipped')};")
        else:
            self.setStyleSheet(f"border: 2px dashed {get_color('slot_border')}; background-color: {get_color('slot_bg')};")

class SkillInfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(100)
        self.refresh_theme()
        
        # Main Layout for the QFrame itself
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll Area Setup
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background-color: transparent;")
        
        # Container Widget for the scroll area
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        
        self.lbl_name = QLabel("Select a skill")
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(128, 128)
        self.lbl_icon.setStyleSheet(f"border: 1px solid {get_color('border')};")
        
        self.txt_desc = QLabel("")
        self.txt_desc.setWordWrap(True)
        self.txt_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.details = QLabel("")
        self.details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Manual Link Handling for Tooltips
        self.details.setOpenExternalLinks(False)
        self.details.linkHovered.connect(self.on_link_hovered)
        self.details.linkActivated.connect(self.on_link_activated)

        self.refresh_labels()
        
        self.content_layout.addWidget(self.lbl_name)
        self.content_layout.addWidget(self.lbl_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.txt_desc)
        self.content_layout.addWidget(self.details)
        self.content_layout.addStretch()
        
        # Finalize Scroll Area
        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

    def on_link_hovered(self, link):
        if link == "aftercast":
            self.details.setToolTip("What's this?<br>Every skill has an unavoidable .75s aftercast, this factors that in.")
        else:
            self.details.setToolTip("")

    def on_link_activated(self, link):
        if link == "aftercast":
            return
        QDesktopServices.openUrl(QUrl(link))

    def refresh_theme(self):
        self.setStyleSheet(f"background-color: {get_color('bg_tertiary')}; border-left: 1px solid {get_color('border')};")
        # Check if initialized fully
        if hasattr(self, 'lbl_name'):
            self.refresh_labels()

    def refresh_labels(self):
        self.lbl_name.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {get_color('text_accent')};")
        self.lbl_icon.setStyleSheet(f"border: 1px solid {get_color('border')};")
        self.txt_desc.setStyleSheet(f"color: {get_color('text_secondary')}; font-style: italic;")
        self.details.setStyleSheet(f"color: {get_color('text_tertiary')};")

    def update_info(self, skill: Skill, repo=None, rank=0, bonuses: dict = None, global_act=0.0, global_rech=0.0):
        self.lbl_name.setText(skill.name)
        
        path = os.path.join(ICON_DIR, skill.icon_filename)
        if os.path.exists(path):
            self.lbl_icon.setPixmap(QPixmap(path).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.lbl_icon.clear()
            
        self.txt_desc.setText(skill.get_description_for_rank(rank, bonuses))
        
        info = []
        info.append(f"Profession: {skill.get_profession_str()}")
        attr_name = skill.get_attribute_str()
        if skill.attribute != -1:
             info.append(f"Attribute: {attr_name} ({rank})")
        else:
             info.append(f"Attribute: {attr_name}")
        
        if skill.skill_type:
            info.append(f"Type: {skill.skill_type.title()}")
        
        # Energy Calculation
        eff_energy = skill.get_effective_energy(rank, bonuses)
        if skill.energy > 0:
            if eff_energy < skill.energy:
                info.append(f"Energy: <span style='color:#00FF00;'><b>{eff_energy}</b></span> (Base: {skill.energy})")
            else:
                info.append(f"Energy: {skill.energy}")

        if skill.health_cost: info.append(f"<b>Sacrifice: {skill.health_cost} HP</b>")
        if skill.adrenaline: info.append(f"Adrenaline: {skill.adrenaline}")
        
        # Combined Timing Display
        eff_act = skill.get_effective_activation(rank, bonuses, global_act)
        total_time = round(eff_act + skill.aftercast, 2)
        
        act_str = f"{eff_act}s"
        if eff_act < skill.activation:
            act_str = f"<span style='color:#00FF00;'><b>{eff_act}s</b></span> (Base: {skill.activation}s)"
        
        aftercast_link = f"<a href='aftercast' style='text-decoration: underline; color: {get_color('text_tertiary')};'>+ {skill.aftercast}s</a>"
        info.append(f"Cast: {act_str} {aftercast_link} ({total_time}s)") 
        
        eff_rech = skill.get_effective_recharge(rank, bonuses, global_rech)
        if skill.recharge: 
            if eff_rech < skill.recharge:
                info.append(f"Recharge: <span style='color:#00FF00;'><b>{eff_rech}s</b></span> (Base: {skill.recharge}s)")
            else:
                info.append(f"Recharge: {skill.recharge}s")
        
        if skill.is_elite: info.append("<b>Elite Skill</b>")
        if skill.is_pve_only: info.append("<i>PvE Only</i>")
        if skill.combo_req > 0: info.append(f"Combo Stage: {skill.combo_req}")

        # --- Acquisition Info ---
        if repo:
            aq = repo.get_skill_acquisition(skill.id)
            if aq:
                # Helper to format links
                def format_links(text_blob):
                    if not text_blob: return ""
                    links = []
                    # Split by newlines first
                    for line in text_blob.split('\n'):
                        parts = line.split('|')
                        if len(parts) >= 2:
                            name, url = parts[0], parts[1]
                            links.append(f'<a href="{url}" style="color: {get_color("text_accent")};">{name}</a>')
                        else:
                            links.append(line)
                    return "<br/>".join(links)

                if aq.get('campaign'):
                    info.append(f"<b>Campaign:</b> {aq['campaign']}")
                
                if aq.get('quests'):
                    links = format_links(aq['quests'])
                    if links: info.append(f"<b>Quests:</b><br/>{links}")
                    
                if aq.get('trainers'):
                    links = format_links(aq['trainers'])
                    if links: info.append(f"<b>Trainers:</b><br/>{links}")
                
                if aq.get('hero_trainers'):
                    links = format_links(aq['hero_trainers'])
                    if links: info.append(f"<b>Hero Trainers:</b><br/>{links}")
                    
                if aq.get('capture'):
                    links = format_links(aq['capture'])
                    if links: info.append(f"<b>Capture:</b><br/>{links}")
        
        self.details.setWordWrap(True)
        self.details.setText("<br/><br/>".join(info))
        self.details.setOpenExternalLinks(False)

    def update_monster_info(self, monster_data):
        self.lbl_name.setText(monster_data['name'])
        if monster_data.get('is_boss'):
            self.lbl_name.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {get_color('text_warning')};")
        else:
            self.lbl_name.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {get_color('text_accent')};")
            
        self.lbl_icon.clear()
        
        skills = monster_data.get('skills', [])
        self.txt_desc.setText("<b>Build:</b><br/>" + (", ".join(skills) if skills else "No known skills."))
        
        analysis = []
        if skills:
            analysis.append("<b>Analysis:</b>")
            text = " ".join(skills).lower()
            if "hex" in text: analysis.append("- Uses Hexes. Suggest Hex Removal.")
            if any(x in text for x in ["condition", "bleeding", "poison", "disease", "burning", "weakness"]): 
                analysis.append("- Uses Conditions. Suggest Condition Removal.")
            if "knock down" in text: analysis.append("- Uses Knockdowns. Suggest Stability.")
            if "interrupt" in text: analysis.append("- Uses Interrupts. Careful with long casts.")
            if "stance" in text: analysis.append("- Uses Stances. Suggest Wild Blow or Wild Throw.")
            if "enchantment" in text: analysis.append("- Uses Enchantments. Suggest Strip/Removal.")
            
        self.details.setText("<br/>".join(analysis))

class BuildPreviewWidget(QFrame):
    load_clicked = pyqtSignal(Build) 
    skill_clicked = pyqtSignal(Skill) 
    rename_clicked = pyqtSignal(Build) 
    populate_clicked = pyqtSignal(Build)
    edit_clicked = pyqtSignal(Build)
    import_clicked = pyqtSignal(Build)

    def __init__(self, build: Build, repo, is_pvp=False, parent=None, icon_size=64):
        super().__init__(parent)
        self.build = build
        self.repo = repo
        self.icon_size = icon_size
        self.is_editing = False
        
        # Dynamic height based on icon size
        self.setFixedHeight(icon_size + 140) 
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 2, 10, 5) # Further reduced margins
        main_layout.setSpacing(2) # Tighter spacing

        # 1. Top Row: Build Name (Compact)
        if hasattr(build, 'name') and build.name:
            lbl_name = QLabel(build.name)
            lbl_name.setStyleSheet(f"color: {get_color('text_accent')}; font-weight: bold; font-size: 20px; border: none; background: transparent;")
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            lbl_name.setFixedHeight(28) # Increased to prevent descender clipping
            main_layout.addWidget(lbl_name)
        else:
            # Small spacer to keep layout consistent
            main_layout.addSpacing(2)

        # 2. Bottom Row: Info and Icons
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(10)
        self.content_layout.setContentsMargins(0, 5, 0, 0)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # ALIGN TO TOP
        
        p1_name = PROF_MAP.get(int(build.primary_prof) if build.primary_prof.isdigit() else 0, "No Profession")
        p2_name = PROF_MAP.get(int(build.secondary_prof) if build.secondary_prof.isdigit() else 0, "No Profession")
        p1 = PROF_SHORT_MAP.get(p1_name, "X")
        p2 = PROF_SHORT_MAP.get(p2_name, "X")
        
        lbl_prof = QLabel(f"{p1}/{p2}", self) # Parented
        lbl_prof.setStyleSheet(f"color: {get_color('text_tertiary')}; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        lbl_prof.setFixedWidth(50)
        lbl_prof.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(lbl_prof)
        
        for sid in build.skill_ids:
            skill_widget = None
            if sid != 0:
                skill = repo.get_skill(sid, is_pvp=is_pvp)
                if skill:
                    skill_widget = DraggableSkillIcon(skill, parent=self, size=icon_size) # Parented
                    skill_widget.setStyleSheet("background: transparent; border: none;")
                    skill_widget.clicked.connect(self.skill_clicked.emit)
            
            if skill_widget:
                self.content_layout.addWidget(skill_widget)
            else:
                placeholder = QFrame(self) # Parented
                placeholder.setFixedSize(icon_size, icon_size)
                placeholder.setStyleSheet(f"background: transparent; border: 1px dashed {get_color('border')};")
                self.content_layout.addWidget(placeholder)
            
        self.content_layout.addStretch() 
        
        # Right Side Buttons
        btn_vbox = QVBoxLayout()
        btn_vbox.setSpacing(4)
        btn_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.btn_populate = QPushButton("Populate", self) # Parented
        self.btn_populate.setFixedSize(60, 18)
        self.btn_populate.setStyleSheet("font-size: 9px;")
        self.btn_populate.setToolTip("Overwrite this slot with the current bar skills and attributes")
        self.btn_populate.clicked.connect(lambda: self.populate_clicked.emit(self.build))
        # Only show for user builds
        is_user = getattr(build, 'is_user_build', False)
        is_user_cat = build.category in ["User Created", "User Imported"]
        self.btn_populate.setVisible(is_user or is_user_cat)

        self.btn_edit = QPushButton("Edit", self) # Parented
        self.btn_edit.setFixedSize(60, 18)
        self.btn_edit.setStyleSheet("font-size: 9px;")
        self.btn_edit.setToolTip("Load to bar and Edit")
        self.btn_edit.clicked.connect(self.toggle_edit_state)
        
        # Only show Edit button for User Created or User Imported builds
        is_user = getattr(build, 'is_user_build', False)
        is_user_cat = build.category in ["User Created", "User Imported"]
        self.btn_edit.setVisible(is_user or is_user_cat)

        self.btn_import = QPushButton("Import", self) # Parented
        self.btn_import.setFixedSize(60, 18)
        self.btn_import.setStyleSheet("font-size: 9px;")
        self.btn_import.setToolTip("Import a build code from file into this slot")
        self.btn_import.clicked.connect(lambda: self.import_clicked.emit(self.build))
        # Only show Import for user builds too
        self.btn_import.setVisible(is_user or is_user_cat)

        self.btn_load = QPushButton("Load", self) # Parented
        self.btn_load.setFixedSize(60, 18)
        self.btn_load.setStyleSheet("font-size: 9px;")
        self.btn_load.clicked.connect(lambda: self.load_clicked.emit(self.build))
        
        self.btn_rename = QPushButton("Rename", self) # Parented
        self.btn_rename.setFixedSize(60, 18)
        self.btn_rename.setStyleSheet("font-size: 9px;")
        self.btn_rename.clicked.connect(lambda: self.rename_clicked.emit(self.build))
        
        self.btn_wiki = QPushButton("Wiki Page", self) # Parented
        self.btn_wiki.setFixedSize(60, 18)
        self.btn_wiki.setStyleSheet("font-size: 9px;")
        self.btn_wiki.clicked.connect(self.open_wiki)
        # Only show if URL exists
        self.btn_wiki.setVisible(bool(getattr(self.build, 'url', '')))
        
        btn_vbox.addWidget(self.btn_populate)
        btn_vbox.addWidget(self.btn_edit)
        btn_vbox.addWidget(self.btn_import)
        btn_vbox.addWidget(self.btn_load)
        btn_vbox.addWidget(self.btn_rename)
        btn_vbox.addWidget(self.btn_wiki)
        
        self.refresh_button_style()
        self.content_layout.addLayout(btn_vbox)
        
        main_layout.addLayout(self.content_layout)
        self.refresh_theme()

    def toggle_edit_state(self):
        if self.is_editing:
            # Was Editing, now Saving
            self.populate_clicked.emit(self.build)
            self.reset_edit_state()
        else:
            # Was Normal, now Editing
            self.is_editing = True
            self.btn_edit.setText("Save")
            self.btn_edit.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('text_warning')}; 
                    color: #000000; 
                    border: none; 
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 9px;
                }}
                QPushButton:hover {{
                    background-color: #FFAA00;
                }}
            """)
            self.edit_clicked.emit(self.build)

    def set_edit_mode(self, active=True):
        if self.is_editing == active: return
        self.is_editing = active
        
        if self.is_editing:
            self.btn_edit.setText("Save")
            self.btn_edit.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('text_warning')}; 
                    color: #000000; 
                    border: none; 
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 9px;
                }}
                QPushButton:hover {{
                    background-color: #FFAA00;
                }}
            """)
        else:
            self.btn_edit.setText("Edit")
            self.refresh_button_style()

    def reset_edit_state(self):
        self.set_edit_mode(False)

    def open_wiki(self):
        url = getattr(self.build, 'url', '')
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def set_icon_size(self, size):
        self.setFixedHeight(size + 140) # Dynamic height based on icon size
        
        # Update placeholder and skill icon sizes
        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            if not item: continue
            widget = item.widget()
            if not widget: continue
            
            if isinstance(widget, DraggableSkillIcon):
                widget.set_icon_size(size)
            elif isinstance(widget, QFrame): # Placeholder
                widget.setFixedSize(size, size)

    def refresh_theme(self):
        self.setStyleSheet(f"""
            BuildPreviewWidget {{
                background-color: {get_color('bg_secondary')};
                border: 1px solid {get_color('border')};
                border-radius: 8px;
            }}
        """)
        if hasattr(self, 'btn_load'):
            self.refresh_button_style()

    def refresh_button_style(self):
        style = f"""
            QPushButton {{
                background-color: {get_color('border_accent')}; 
                color: #FFFFFF; 
                border: none; 
                border-radius: 4px;
                font-weight: bold;
                font-size: 9px;
            }}
            QPushButton:hover {{
                background-color: {get_color('text_link')};
            }}
        """
        if hasattr(self, 'btn_populate'):
            self.btn_populate.setStyleSheet(style)
        if hasattr(self, 'btn_edit'):
            # Only apply default style if NOT in edit mode
            if not getattr(self, 'is_editing', False):
                self.btn_edit.setStyleSheet(style)
        if hasattr(self, 'btn_import'):
            self.btn_import.setStyleSheet(style)
        if hasattr(self, 'btn_load'):
            self.btn_load.setStyleSheet(style)
        if hasattr(self, 'btn_rename'):
            self.btn_rename.setStyleSheet(style)
        if hasattr(self, 'btn_wiki'):
            self.btn_wiki.setStyleSheet(style)

class SkillItemDelegate(QStyledItemDelegate):
    """
    Renders the skill items with dynamic sizing support.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_size = 64 # Default size

    def sizeHint(self, option, index):
        return QSize(self.icon_size + 10, self.icon_size + 80)

    def paint(self, painter, option, index):
        if not index.isValid(): return

        painter.save()
        
        # Data Retrieval
        name = index.data(Qt.ItemDataRole.DisplayRole)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        
        # Style Setup
        rect = option.rect
        rect.adjust(2, 2, -2, -2) # Margin
        
        # Background & Border
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QColor(get_color("bg_hover")))
            painter.setPen(QColor(get_color("border_light")))
        elif option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor(get_color("bg_selected")))
            painter.setPen(QColor(get_color("border_accent")))
        else:
            painter.setBrush(QColor(get_color("bg_secondary")))
            painter.setPen(QColor(get_color("border")))
            
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawRoundedRect(rect, 4, 4)
        
        # Icon
        icon_x = rect.center().x() - (self.icon_size // 2)
        icon_y = rect.top() + 10
        icon_rect = QRect(icon_x, icon_y, self.icon_size, self.icon_size)
        
        if icon:
            painter.drawPixmap(icon_rect, icon.pixmap(self.icon_size, self.icon_size))
        
        # Text
        text_y = icon_y + self.icon_size + 5
        text_height = rect.bottom() - text_y - 2
        text_rect = QRect(rect.left() + 2, text_y, rect.width() - 4, text_height)
        
        painter.setPen(QColor(get_color("text_primary")))
        # Scale font size: Base 8, increases slightly with icon size
        font_size = 8 if self.icon_size <= 64 else 11
        painter.setFont(QFont("Arial", font_size))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, name)
        
        painter.restore()

class SkillLibraryWidget(QListWidget):
    """
    Smart Widget that handles both standard lists and AI-driven suggestions.
    """
    skill_clicked = pyqtSignal(object)
    skill_double_clicked = pyqtSignal(object)
    builds_reordered = pyqtSignal(int, int) # source_index, target_index

    def __init__(self, repo, engine=None, parent=None):
        super().__init__(parent)
        self.repo = repo      
        self.engine = engine  
        self.drop_row = -1 # Track for manual painting
        
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setSpacing(5)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        self.delegate = SkillItemDelegate(self)
        self.setItemDelegate(self.delegate)

        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.refresh_theme()

    def wheelEvent(self, event):
        """ Override wheel event to make scrolling less sensitive. """
        # Adjust the delta to scroll by a smaller amount
        # Standard delta is 120 per 'click'
        delta = event.angleDelta().y()
        # Scale down the scroll amount - 80 pixels per click (approx one row)
        scroll_amount = -1 * (delta / 120) * 80 
        self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() + scroll_amount))
        event.accept()

    def _on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, Build):
            self.skill_clicked.emit(data)

    def _on_item_double_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, Build):
            self.skill_double_clicked.emit(data)

    def refresh_theme(self):
        self.setStyleSheet(f"""
            QListWidget {{ 
                background-color: {get_color('bg_primary')}; 
                border: none; 
            }}
            QListWidget::item {{
                border-bottom: 1px solid {get_color('border')};
            }}
            QListWidget::item:hover {{
                background-color: {get_color('bg_hover')};
            }}
            QListWidget::item:selected {{
                background-color: {get_color('bg_selected')};
            }}
        """)
        self.viewport().update()

    def update_suggestions(self, suggestions):
        self.clear() 
        sorted_suggestions = sorted(suggestions, key=lambda x: x[1], reverse=True)

        for item in sorted_suggestions:
            if len(item) == 3:
                sid, score, reason = item
            else:
                sid, score = item
                reason = "Neural Synergy"

            skill = self.repo.get_skill(sid)
            if not skill: continue

            list_item = QListWidgetItem()
            list_item.setText(skill.name)
            list_item.setData(Qt.ItemDataRole.UserRole, sid)
            
            confidence_pct = int(score * 100)
            attr_name = skill.get_attribute_str()
            type_str = f"<i>{skill.skill_type.title()}</i><br/>" if skill.skill_type else ""
            attr_str = f"<i>{attr_name}</i><br/>" if skill.attribute != -1 else ""

            tooltip_text = (
                f"<b>{skill.name}</b><br/>"
                f"{attr_str}"
                f"{type_str}"
                f"<span style='color:{get_color('text_accent')};'>Match: {reason}</span><br/>"
                f"Confidence: {confidence_pct}%<br/><hr/>"
                f"{skill.description}"
            )
            list_item.setToolTip(tooltip_text)
            
            icon_path = os.path.join(ICON_DIR, skill.icon_filename)
            if os.path.exists(icon_path):
                key = f"{skill.icon_filename}_{self.delegate.icon_size}"
                if key in PIXMAP_CACHE:
                    pixmap = PIXMAP_CACHE[key]
                else:
                    pixmap = QPixmap(icon_path).scaled(
                        self.delegate.icon_size, self.delegate.icon_size, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    PIXMAP_CACHE[key] = pixmap
                list_item.setIcon(QIcon(pixmap))
            
            if score > 0.85:
                font = list_item.font()
                font.setBold(True)
                list_item.setFont(font)

            self.addItem(list_item)

    def update_standard_list(self, skill_ids):
        self.clear()
        for sid in skill_ids:
            skill = self.repo.get_skill(sid)
            if not skill: continue
            
            list_item = QListWidgetItem()
            list_item.setText(skill.name)
            list_item.setData(Qt.ItemDataRole.UserRole, sid)
            
            attr_name = skill.get_attribute_str()
            type_str = f"<i>{skill.skill_type.title()}</i><br/>" if skill.skill_type else ""
            attr_str = f"<i>{attr_name}</i><br/>" if skill.attribute != -1 else ""
            
            list_item.setToolTip(f"<b>{skill.name}</b><br/>{attr_str}{type_str}<hr/>{skill.description}")
            
            icon_path = os.path.join(ICON_DIR, skill.icon_filename)
            if os.path.exists(icon_path):
                current_size = self.delegate.icon_size
                key = f"{skill.icon_filename}_{current_size}"
                if key in PIXMAP_CACHE:
                    pix = PIXMAP_CACHE[key]
                else:
                    pix = QPixmap(icon_path).scaled(
                        current_size, current_size,
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                    )
                    PIXMAP_CACHE[key] = pix
                list_item.setIcon(QIcon(pix))
            
            self.addItem(list_item)

    def update_zone_summary(self, monsters):
        self.clear()
        self.setViewMode(QListWidget.ViewMode.ListMode)
        self.setSpacing(2)
        
        for m in monsters:
            item = QListWidgetItem(m['name'])
            item.setData(Qt.ItemDataRole.UserRole, m) 
            if m.get('is_boss'):
                item.setForeground(QColor(get_color("text_warning")))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.addItem(item)

    def set_icon_size(self, size):
        self.delegate.icon_size = size
        
        # Propagate to BuildPreviewWidgets if they exist
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if isinstance(widget, BuildPreviewWidget):
                widget.set_icon_size(size)
                # Adjust item size hint
                item.setSizeHint(QSize(500, widget.sizeHint().height()))
        
        self.model().layoutChanged.emit()
        self.viewport().update()

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, Build):
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(f"reorder_build:{self.row(item)}")
            drag.setMimeData(mime_data)
            
            widget = self.itemWidget(item)
            if widget:
                # Create a semi-transparent thumbnail
                pixmap = widget.grab()
                transparent_pix = QPixmap(pixmap.size())
                transparent_pix.fill(Qt.GlobalColor.transparent)
                p = QPainter(transparent_pix)
                p.setOpacity(0.6)
                p.drawPixmap(0, 0, pixmap)
                p.end()
                
                drag.setPixmap(transparent_pix.scaled(400, widget.height(), Qt.AspectRatioMode.KeepAspectRatio))
                drag.setHotSpot(QPoint(200, widget.height() // 2))
            
            drag.exec(Qt.DropAction.MoveAction)
            return

        skill_id = data
        icon = item.icon()
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(skill_id))
        drag.setMimeData(mime_data)
        if not icon.isNull():
            drag.setPixmap(icon.pixmap(64, 64))
            drag.setHotSpot(QPoint(32, 32))
        drag.exec(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("reorder_build:"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self.drop_row = -1
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        if event.mimeData().hasText() and event.mimeData().text().startswith("reorder_build:"):
            event.acceptProposedAction()
            
            # Update manual drop indicator
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            if item:
                self.drop_row = self.row(item)
                # If in bottom half of item, indicate drop AFTER it
                if pos.y() > self.visualItemRect(item).center().y():
                    self.drop_row += 1
            else:
                self.drop_row = self.count()
            self.viewport().update()

    def dropEvent(self, event):
        self.drop_row = -1
        self.viewport().update()
        
        if event.mimeData().hasText() and event.mimeData().text().startswith("reorder_build:"):
            source_row = int(event.mimeData().text().split(":")[1])
            drop_pos = event.position().toPoint()
            target_item = self.itemAt(drop_pos)
            
            if target_item:
                target_row = self.row(target_item)
                if drop_pos.y() > self.visualItemRect(target_item).center().y():
                    target_row += 1
            else:
                target_row = self.count()
            
            if source_row < target_row:
                target_row -= 1
                
            if source_row != target_row and target_row >= 0:
                self.builds_reordered.emit(source_row, target_row)
                event.acceptProposedAction()
            else:
                event.ignore()
            return
        super().dropEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        
        # Show placeholder text if empty
        if self.count() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(QColor(get_color("text_tertiary")))
            # Use a reasonably sized font
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            
            rect = self.viewport().rect()
            text = "Select a category or teambuild to view"
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
            painter.end()

        if self.drop_row != -1:
            from PyQt6.QtGui import QPen
            painter = QPainter(self.viewport())
            pen = QPen(QColor(get_color("text_link")))
            pen.setWidth(3)
            painter.setPen(pen)
            
            # Calculate line position
            if self.drop_row < self.count():
                rect = self.visualItemRect(self.item(self.drop_row))
                y = rect.top()
            else:
                rect = self.visualItemRect(self.item(self.count() - 1))
                y = rect.bottom()
            
            painter.drawLine(0, y, self.viewport().width(), y)
            painter.end()

    