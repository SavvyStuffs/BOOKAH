import os
from PyQt6.QtWidgets import (
    QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy, QListWidget, QStyle, QStyledItemDelegate, QListWidgetItem, QAbstractItemView, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QSize, QRect
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont, QIcon

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

    def __init__(self, skill: Skill, parent=None):
        super().__init__(parent)
        self.skill = skill
        self.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        path = os.path.join(ICON_DIR, skill.icon_filename)
        if os.path.exists(path):
            self.setPixmap(QPixmap(path).scaled(ICON_SIZE, ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.setText(skill.name)
            self.refresh_theme()

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
                drag.setHotSpot(QPoint(ICON_SIZE // 2, ICON_SIZE // 2))
                
            drag.exec(Qt.DropAction.CopyAction)

class SkillSlot(QFrame):
    skill_equipped = pyqtSignal(int, int) 
    skill_removed = pyqtSignal(int)       
    skill_swapped = pyqtSignal(int, int) # NEW: source_index, target_index
    clicked = pyqtSignal(int)             

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.current_skill_id = None
        self.is_ghost = False
        
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
                else:
                    event.ignore()
            else:
                skill_id = int(mime_text)
                self.skill_equipped.emit(self.index, skill_id)
                event.accept()
        except ValueError:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_skill_id is not None:
                self.clicked.emit(self.current_skill_id)
                
                # Initiate Drag for reordering
                if not self.is_ghost:
                    drag = QDrag(self)
                    mime_data = QMimeData()
                    # Prefix with "slot:" to distinguish from library drags
                    mime_data.setText(f"slot:{self.index}")
                    drag.setMimeData(mime_data)
                    
                    pix = self.icon_label.pixmap()
                    if pix and not pix.isNull():
                        drag.setPixmap(pix)
                        drag.setHotSpot(QPoint(ICON_SIZE // 2, ICON_SIZE // 2))
                    
                    drag.exec(Qt.DropAction.MoveAction)
                    
        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_skill_id is not None:
                self.clear_slot()

    def mouseDoubleClickEvent(self, event):
        if self.current_skill_id is not None:
            if self.is_ghost:
                self.skill_equipped.emit(self.index, self.current_skill_id)
            else:
                self.clear_slot()

    def set_skill(self, skill_id, skill_obj: Skill = None, ghost=False, confidence=0.0, rank=0):
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
            desc = skill_obj.get_description_for_rank(rank)
            attr_name = ATTR_MAP.get(skill_obj.attribute, "None")
            tooltip = f"<b>{skill_obj.name}</b><br/>"
            if skill_obj.attribute != -1:
                tooltip += f"<i>{attr_name} ({rank})</i><br/>"
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

        self.refresh_labels()
        
        self.content_layout.addWidget(self.lbl_name)
        self.content_layout.addWidget(self.lbl_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.txt_desc)
        self.content_layout.addWidget(self.details)
        self.content_layout.addStretch()
        
        # Finalize Scroll Area
        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

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

    def update_info(self, skill: Skill, repo=None, rank=0):
        self.lbl_name.setText(skill.name)
        
        path = os.path.join(ICON_DIR, skill.icon_filename)
        if os.path.exists(path):
            self.lbl_icon.setPixmap(QPixmap(path).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.lbl_icon.clear()
            
        self.txt_desc.setText(skill.get_description_for_rank(rank))
        
        info = []
        info.append(f"Profession: {skill.get_profession_str()}")
        attr_name = skill.get_attribute_str()
        if skill.attribute != -1:
             info.append(f"Attribute: {attr_name} ({rank})")
        else:
             info.append(f"Attribute: {attr_name}")
        if skill.energy: info.append(f"Energy: {skill.energy}")
        if skill.health_cost: info.append(f"<b>Sacrifice: {skill.health_cost} HP</b>") # NEW
        if skill.adrenaline: info.append(f"Adrenaline: {skill.adrenaline}")
        
        # Combined Timing Display
        total_time = skill.activation + skill.aftercast
        info.append(f"Cast: {skill.activation}s + {skill.aftercast}s ({total_time}s)") # NEW
        
        if skill.recharge: info.append(f"Recharge: {skill.recharge}s")
        
        if skill.is_elite: info.append("<b>Elite Skill</b>")
        if skill.is_pve_only: info.append("<i>PvE Only</i>")
        if skill.combo_req > 0: info.append(f"Combo Stage: {skill.combo_req}") # NEW

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
        self.details.setOpenExternalLinks(True)

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

class BuildPreviewWidget(QFrame): # Restored to QFrame
    clicked = pyqtSignal(str) 
    skill_clicked = pyqtSignal(Skill) 
    rename_clicked = pyqtSignal(Build) 

    def __init__(self, build: Build, repo, is_pvp=False, parent=None):
        super().__init__(parent)
        self.build = build
        self.repo = repo
        # Increased height for a more spacious and centered layout
        self.setFixedHeight(130) 
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(0)

        # 1. Top Row: Build Name (Compact)
        if hasattr(build, 'name') and build.name:
            lbl_name = QLabel(build.name)
            lbl_name.setStyleSheet(f"color: {get_color('text_accent')}; font-weight: bold; font-size: 10px; border: none; background: transparent;")
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            lbl_name.setFixedHeight(14) 
            main_layout.addWidget(lbl_name)
            main_layout.addSpacing(15) # Increased spacing to push skills down
        else:
            # Small spacer to keep layout consistent
            main_layout.addSpacing(29)

        # 2. Bottom Row: Info and Icons (Centered in remaining space)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        p1_name = PROF_MAP.get(int(build.primary_prof) if build.primary_prof.isdigit() else 0, "No Profession")
        p2_name = PROF_MAP.get(int(build.secondary_prof) if build.secondary_prof.isdigit() else 0, "No Profession")
        p1 = PROF_SHORT_MAP.get(p1_name, "X")
        p2 = PROF_SHORT_MAP.get(p2_name, "X")
        
        lbl_prof = QLabel(f"{p1}/{p2}")
        lbl_prof.setStyleSheet(f"color: {get_color('text_tertiary')}; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        lbl_prof.setFixedWidth(50)
        lbl_prof.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(lbl_prof)
        
        for sid in build.skill_ids:
            skill_widget = None
            if sid != 0:
                skill = repo.get_skill(sid, is_pvp=is_pvp)
                if skill:
                    skill_widget = DraggableSkillIcon(skill)
                    skill_widget.setStyleSheet("background: transparent; border: none;")
                    skill_widget.clicked.connect(self.skill_clicked.emit)
            
            if skill_widget:
                content_layout.addWidget(skill_widget)
            else:
                placeholder = QFrame()
                placeholder.setFixedSize(ICON_SIZE, ICON_SIZE)
                placeholder.setStyleSheet(f"background: transparent; border: 1px dashed {get_color('border')};")
                content_layout.addWidget(placeholder)
            
        content_layout.addStretch() 
        
        # Right Side Buttons
        btn_vbox = QVBoxLayout()
        btn_vbox.setSpacing(2)
        
        self.btn_load = QPushButton("Load")
        self.btn_load.setFixedSize(60, 28)
        self.btn_load.clicked.connect(lambda: self.clicked.emit(self.build.code))
        
        self.btn_rename = QPushButton("Rename")
        self.btn_rename.setFixedSize(60, 18)
        self.btn_rename.setStyleSheet("font-size: 9px;")
        self.btn_rename.clicked.connect(lambda: self.rename_clicked.emit(self.build))
        
        btn_vbox.addWidget(self.btn_load)
        btn_vbox.addWidget(self.btn_rename)
        
        self.refresh_button_style()
        content_layout.addLayout(btn_vbox)
        
        main_layout.addStretch() # Push skills to center
        main_layout.addLayout(content_layout)
        main_layout.addStretch() # Push skills to center
        
        self.refresh_theme()

    def refresh_theme(self):
        # Remove the internal box styling. We let the QListWidget handle the item background/hover.
        self.setStyleSheet("background: transparent; border: none;")
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
            }}
            QPushButton:hover {{
                background-color: {get_color('text_link')};
            }}
        """
        if hasattr(self, 'btn_load'):
            self.btn_load.setStyleSheet(style)
        if hasattr(self, 'btn_rename'):
            self.btn_rename.setStyleSheet(style)

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
        self.setDropIndicatorShown(True) # NEW: Show where item will land
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setSpacing(5)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        self.delegate = SkillItemDelegate(self)
        self.setItemDelegate(self.delegate)

        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.refresh_theme()

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
            tooltip_text = (
                f"<b>{skill.name}</b><br/>"
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
            list_item.setToolTip(f"<b>{skill.name}</b><br>{skill.description}")
            
            icon_path = os.path.join(ICON_DIR, skill.icon_filename)
            if os.path.exists(icon_path):
                pix = QPixmap(icon_path).scaled(
                    self.delegate.icon_size, self.delegate.icon_size,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
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

    