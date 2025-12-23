import os
from PyQt6.QtWidgets import (
    QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy, QListWidget, QStyle, QStyledItemDelegate, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QSize, QRect
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont, QIcon

from src.constants import ICON_DIR, ICON_SIZE, ATTR_MAP, PROF_MAP, PROF_SHORT_MAP, PIXMAP_CACHE
from src.models import Skill, Build

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
            self.setStyleSheet("border: 1px solid #555; background-color: #222; color: #fff;")

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
    clicked = pyqtSignal(int)             

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.current_skill_id = None
        self.is_ghost = False
        
        self.setFixedSize(ICON_SIZE + 4, ICON_SIZE + 4)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #555;
                background-color: #1a1a1a;
                border-radius: 4px;
            }
        """)
        
        self.icon_label = QLabel(self)
        self.icon_label.setGeometry(2, 2, ICON_SIZE, ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) 

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
            self.setStyleSheet("border: 2px solid #00AAFF; background-color: #222;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.update_style()

    def dropEvent(self, event):
        try:
            skill_id = int(event.mimeData().text())
            self.skill_equipped.emit(self.index, skill_id)
            event.accept()
        except ValueError:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_skill_id is not None:
                self.clicked.emit(self.current_skill_id)
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
            pix.fill(QColor("#333"))
            p = QPainter(pix)
            p.setPen(Qt.GlobalColor.white)
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
            self.setStyleSheet("border: 2px solid #666; background-color: #2a2a2a;")
        else:
            self.setStyleSheet("border: 2px dashed #555; background-color: #1a1a1a;")

class SkillInfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(100)
        self.setStyleSheet("background-color: #1a1a1a; border-left: 1px solid #444;")
        layout = QVBoxLayout(self)
        
        self.lbl_name = QLabel("Select a skill")
        self.lbl_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #00AAFF;")
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(128, 128)
        self.lbl_icon.setStyleSheet("border: 1px solid #444;")
        
        self.txt_desc = QLabel("")
        self.txt_desc.setWordWrap(True)
        self.txt_desc.setStyleSheet("color: #ccc; font-style: italic;")
        self.txt_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.details = QLabel("")
        self.details.setStyleSheet("color: #aaa;")
        self.details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.txt_desc)
        layout.addWidget(self.details)
        layout.addStretch()

    def update_info(self, skill: Skill, rank=0):
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
        
        self.details.setText("<br>".join(info))

class BuildPreviewWidget(QFrame):
    clicked = pyqtSignal(str) 
    skill_clicked = pyqtSignal(Skill) 

    def __init__(self, build: Build, repo, is_pvp=False, parent=None):
        super().__init__(parent)
        self.build = build
        self.repo = repo
        self.setFixedHeight(ICON_SIZE + 80) 
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QFrame {
                background-color: #222;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QFrame:hover {
                background-color: #333;
                border: 1px solid #666;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)
        
        p1_name = PROF_MAP.get(int(build.primary_prof) if build.primary_prof.isdigit() else 0, "No Profession")
        p2_name = PROF_MAP.get(int(build.secondary_prof) if build.secondary_prof.isdigit() else 0, "No Profession")
        p1 = PROF_SHORT_MAP.get(p1_name, "X")
        p2 = PROF_SHORT_MAP.get(p2_name, "X")
        
        lbl_prof = QLabel(f"{p1}/{p2}")
        lbl_prof.setStyleSheet("color: #AAA; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        lbl_prof.setFixedWidth(50)
        lbl_prof.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_prof)
        
        for sid in build.skill_ids:
            skill_widget = None
            if sid != 0:
                skill = repo.get_skill(sid, is_pvp=is_pvp)
                if skill:
                    skill_widget = DraggableSkillIcon(skill)
                    skill_widget.setStyleSheet("background: transparent; border: none;")
                    skill_widget.clicked.connect(self.skill_clicked.emit)
            
            if skill_widget:
                layout.addWidget(skill_widget)
            else:
                placeholder = QFrame()
                placeholder.setFixedSize(ICON_SIZE + 10, ICON_SIZE + 60)
                placeholder.setStyleSheet("background: transparent; border: 1px dashed #444;")
                layout.addWidget(placeholder)
            
        layout.addStretch()
        
        btn_load = QPushButton("Load")
        btn_load.setFixedSize(60, 40)
        btn_load.setStyleSheet("""
            QPushButton {
                background-color: #0066CC; 
                color: white; 
                border: none; 
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0088FF;
            }
        """)
        btn_load.clicked.connect(lambda: self.clicked.emit(self.build.code))
        layout.addWidget(btn_load)

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
            painter.setBrush(QColor("#333"))
            painter.setPen(QColor("#666"))
        elif option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor("#2a2a2a"))
            painter.setPen(QColor("#00AAFF"))
        else:
            painter.setBrush(QColor("#222"))
            painter.setPen(QColor("#444"))
            
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
        
        painter.setPen(QColor("#EEE"))
        # Scale font size: Base 8, increases slightly with icon size
        font_size = 8 if self.icon_size <= 64 else 11
        painter.setFont(QFont("Arial", font_size))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, name)
        
        painter.restore()

class SkillLibraryWidget(QListWidget):
    """
    High-performance replacement for the ScrollArea + FlowLayout.
    """
    skill_clicked = pyqtSignal(int)
    skill_double_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        self.setDragEnabled(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setSpacing(5)
        self.setStyleSheet("QListWidget { background-color: #111; border: none; }")
        
        # Attach the custom painter
        self.delegate = SkillItemDelegate(self)
        self.setItemDelegate(self.delegate)

    def set_icon_size(self, size):
        self.delegate.icon_size = size
        self.model().layoutChanged.emit()
        self.viewport().update()

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        
        skill_id = item.data(Qt.ItemDataRole.UserRole)
        icon = item.icon()
        
        # Create standard drag object compatible with your existing SkillSlot
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(skill_id))
        drag.setMimeData(mime_data)
        drag.setPixmap(icon.pixmap(64, 64))
        drag.setHotSpot(QPoint(32, 32))
        drag.exec(Qt.DropAction.CopyAction)

    def mousePressEvent(self, event):
        # Handle clicks normally, but emit signal for info panel
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        if item:
            sid = item.data(Qt.ItemDataRole.UserRole)
            self.skill_clicked.emit(sid)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            sid = item.data(Qt.ItemDataRole.UserRole)
            self.skill_double_clicked.emit(sid)
