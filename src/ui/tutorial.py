from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication, QMessageBox
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QBrush, QRegion, QFont, QPen

from src.ui.theme import get_color

class TutorialOverlay(QWidget):
    """
    A full-screen overlay that dims the UI and highlights specific widgets.
    """
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        
        self.target_widgets = [] # Changed to list
        self.instructions = ""
        self.title = ""
        self.steps = []
        self.current_step = -1

        # The instruction box
        self.info_box = QFrame(self)
        self.info_box.setObjectName("tutorialInfoBox")
        self.info_layout = QVBoxLayout(self.info_box)
        
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #55AAFF;")
        self.lbl_title.setWordWrap(True)
        
        self.lbl_desc = QLabel()
        self.lbl_desc.setStyleSheet("font-size: 13px; color: #FFFFFF;")
        self.lbl_desc.setWordWrap(True)
        
        # Exit button (X) in top right
        self.btn_exit = QPushButton("×", self.info_box)
        self.btn_exit.setFixedSize(24, 24)
        self.btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exit.setStyleSheet("background: transparent; color: #888888; font-size: 18px; font-weight: bold; border: none;")
        self.btn_exit.clicked.connect(self.finish)
        
        btn_layout = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setFixedSize(80, 30)
        self.btn_back.setStyleSheet("background-color: #555555;")
        self.btn_back.clicked.connect(self.prev_step)
        
        self.btn_next = QPushButton("Next")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setFixedSize(80, 30)
        self.btn_next.clicked.connect(self.next_step)
        
        btn_layout.addWidget(self.btn_back)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_next)
        
        self.info_layout.addWidget(self.lbl_title)
        self.info_layout.addWidget(self.lbl_desc)
        self.info_layout.addLayout(btn_layout)
        
        self.refresh_styles()
        self.hide()

    def refresh_styles(self):
        self.info_box.setStyleSheet(f"""
            #tutorialInfoBox {{
                background-color: #2A2A2A;
                border: 2px solid {get_color('border_accent')};
                border-radius: 10px;
                padding: 15px;
            }}
            QPushButton {{
                background-color: {get_color('border_accent')};
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {get_color('text_link')};
            }}
        """)

    def start_tutorial(self, steps):
        self.steps = steps
        self.current_step = -1
        self.resize(self.parent().size())
        self.show()
        self.raise_()
        self.move(0, 0)
        
        # Tiny delay to let MainWindow finish tab switching/layout
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.next_step)

    def prev_step(self):
        if self.current_step > 0:
            self.current_step -= 1
            self.show_step(direction=-1)

    def next_step(self):
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.finish()
            return

        self.show_step(direction=1)

    def show_step(self, direction=1):
        step = self.steps[self.current_step]
        
        # Reset highlights
        self.target_widgets = []
        
        # Execute action if present and moving FORWARD
        # (Actions like _prep_mysticism_step may populate self.target_widgets)
        if direction > 0 and 'action' in step and callable(step['action']):
            step['action']()

        # If step explicitly provides widgets, use them (overriding action if any)
        step_widgets = step.get('widget')
        if step_widgets is not None:
            if not isinstance(step_widgets, list):
                self.target_widgets = [step_widgets]
            else:
                self.target_widgets = step_widgets
        
        self.lbl_title.setText(step['title'])
        self.lbl_desc.setText(step['desc'])
        
        # Toggle back button visibility
        self.btn_back.setVisible(self.current_step > 0)

        if self.current_step == len(self.steps) - 1:
            self.btn_next.setText("Finish")
        else:
            self.btn_next.setText("Next")

        self.position_info_box()
        self.update()

    def position_info_box(self):
        # Sizing logic
        self.info_box.setFixedWidth(400)
        self.info_box.setMinimumHeight(200) # Ensure consistent size
        self.lbl_desc.setFixedWidth(370) 
        self.lbl_desc.setAlignment(Qt.AlignmentFlag.AlignTop) # Keep text at top
        self.info_box.layout().activate()
        self.info_box.adjustSize() 
        
        # Recalculate dimensions after adjustSize
        box_width = self.info_box.width()
        box_height = self.info_box.height()

        # Position X button in corner
        self.btn_exit.move(box_width - self.btn_exit.width() - 5, 5)

        if not self.target_widgets:
            # Center if no target
            self.info_box.move((self.width() - box_width) // 2, (self.height() - box_height) // 2)
            return
        
        # Calculate bounding box of all target widgets
        min_x, min_y = 99999, 99999
        max_x, max_y = -99999, -99999
        
        for widget in self.target_widgets:
            try:
                # Ensure widget is still valid
                pos = widget.mapTo(self.parent(), QPoint(0, 0))
                min_x = min(min_x, pos.x())
                min_y = min(min_y, pos.y())
                max_x = max(max_x, pos.x() + widget.width())
                max_y = max(max_y, pos.y() + widget.height())
            except:
                continue
            
        x, y = min_x, min_y
        w, h = max_x - min_x, max_y - min_y
        
        # Logic to place box near target without overlap
        # Default: Try to place it to the right of the highlight
        new_x = x + w + 20
        new_y = y + (h // 2) - (box_height // 2)
        
        if new_x + box_width > self.width():
            new_x = x - box_width - 20
        
        if new_x < 0:
            new_x = x + (w // 2) - (box_width // 2)
            new_y = y + h + 20
            
        if new_y + box_height > self.height():
            new_y = self.height() - box_height - 20
        if new_y < 0:
            new_y = 20
            
        self.info_box.move(max(10, new_x), max(10, new_y))

    def finish(self):
        self.hide()
        self.finished.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        overlay_color = QColor(0, 0, 0, 180)
        
        if not self.target_widgets:
            painter.fillRect(self.rect(), overlay_color)
            return

        full_region = QRegion(self.rect())
        holes_region = QRegion()
        
        hole_rects = []
        for widget in self.target_widgets:
            try:
                if not widget.isVisible(): continue
                global_pos = widget.mapTo(self.parent(), QPoint(0, 0))
                hr = QRect(global_pos.x(), global_pos.y(), widget.width(), widget.height())
                hr.adjust(-5, -5, 5, 5)
                hole_rects.append(hr)
                holes_region = holes_region.united(QRegion(hr))
            except:
                continue
            
        mask_region = full_region.subtracted(holes_region)
        
        painter.setClipRegion(mask_region)
        painter.fillRect(self.rect(), overlay_color)
        
        painter.setClipping(False)
        pen = QPen(QColor("#55AAFF"), 3)
        painter.setPen(pen)
        for hr in hole_rects:
            painter.drawRect(hr)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_info_box()

class TutorialManager:
    """
    Orchestrates the tutorial flow and interacts with the MainWindow.
    """
    def __init__(self, main_window):
        self.mw = main_window
        self.overlay = TutorialOverlay(main_window)
        
    def show_if_needed(self):
        if not self.mw.settings.value("tutorial_complete", False, type=bool):
            msg = QMessageBox(self.mw)
            msg.setWindowTitle("Welcome to B.O.O.K.A.H.")
            msg.setText("Welcome to B.O.O.K.A.H.! Would you like a quick tour of the features? (Always available later in settings)")
            
            btn_tour = msg.addButton("Start Tour", QMessageBox.ButtonRole.AcceptRole)
            btn_later = msg.addButton("Maybe Later", QMessageBox.ButtonRole.RejectRole)
            btn_skip = msg.addButton("Skip Forever", QMessageBox.ButtonRole.DestructiveRole)
            
            msg.setDefaultButton(btn_tour)
            msg.exec()
            
            if msg.clickedButton() == btn_tour:
                self.start()
            elif msg.clickedButton() == btn_skip:
                self.mw.settings.setValue("tutorial_complete", True)

    def start(self):
        # Ensure we are on the Builder tab
        self.mw.tabs.setCurrentIndex(0)
        self.mw.center_stack.setCurrentIndex(0)
        self.mw.right_stack.setCurrentIndex(0)
        
        steps = [
            {
                "widget": self.mw.library_widget,
                "title": "Skill Library",
                "desc": "This is where all skills are listed. You can search by name or description using the search box above."
            },
            {
                "widget": self.mw.combo_prof,
                "title": "Profession Filtering",
                "desc": "Use this dropdown to filter skills by profession. 'All' shows everything."
            },
            {
                "widget": self.mw.combo_attr,
                "title": "Attribute Filtering",
                "desc": "Once a profession is selected, you can narrow down the list to a specific attribute here."
            },
            {
                "widget": self.mw.btn_load_file,
                "title": "Build Library",
                "desc": "Click here to load existing build templates (.txt files) from your computer."
            },
            {
                "widget": self.mw.btn_prof_select,
                "title": "Manual Profession Selection",
                "desc": "Manually select your primary and secondary professions if you aren't loading a code."
            },
            {
                "widget": self.mw.code_box,
                "title": "Build Code Management",
                "desc": "Paste codes here to load them instantly, copy your current build code, or reset the bar to start fresh."
            },
            {
                "widget": self.mw.attr_editor,
                "title": "Attribute Editor",
                "desc": "After loading a build, you can adjust your attribute points here. Let's load a sample build now."
            },
            {
                "widget": None, # Will be set in action
                "title": "Inherent Attributes",
                "desc": "The primary attribute (underlined) often has a passive bonus. At rank 12, Mysticism reduces Dervish enchantment costs by 48, as well as +12 armor.",
                "action": lambda: self._prep_mysticism_step()
            },
            {
                "widget": None, # Will be set in action
                "title": "PvE Attributes",
                "desc": "PvE Title tracks like Norn Rank don't cost points but affect the power of their associated skills.",
                "action": lambda: self._prep_norn_step()
            },
            {
                "widget": self.mw.btn_char_view,
                "title": "Character Stats Toggle",
                "desc": "Click here to toggle between the Skills and the Character Stats panel."
            },
            {
                "widget": self.mw.character_panel.cons_group,
                "title": "Consumables (Pcons)",
                "desc": "Here you can toggle various consumables. Lets add a conset.",
                "action": lambda: self.mw.btn_char_view.setChecked(True)
            },
            {
                "widget": self.mw.character_panel.stats_group,
                "title": "Live Calculations",
                "desc": "Your health, energy, and attributes are recalculated in real-time.",
                "action": lambda: [self.mw.character_panel.toggle_consumable(k, True) for k in ["armor", "bu", "grail"]]
            },
            {
                "widget": self.mw.character_panel.runes_group,
                "title": "Rune Management",
                "desc": "Manage your equipment runes here. Major and Superior runes will correctly apply HP penalties. Lets apply some runes.",
                "action": lambda: self.mw.character_panel.clear_consumables()
            },
            {
                "widget": self.mw.character_panel.stats_group,
                "title": "Final Result",
                "desc": "With our runes applied, we can see the final stats. Note the health bonus from Superior Vigor (+50) minus the penalty from Superior Earth Prayers (-75), plus energy from Attunement.",
                "action": lambda: self._prep_final_step()
            },
            {
                "widget": self.mw.weapons_panel,
                "title": "Anniversary Weapons",
                "desc": "Anniversary weapons provide unique bonuses",
                "action": None
            },
            {
                "widget": self.mw.character_panel.stats_group,
                "title": "Weapon Bonuses",
                "desc": "Selecting 'Soul's Repentance' adds an additional +5 Soul Reaping to our attributes, in addition to our runes.",
                "action": lambda: self.mw.weapons_panel.select_weapon("decade_scythe")
            },
            {
                "widget": self.mw.btn_char_view,
                "title": "Return to Builder",
                "desc": "Lets go back to the skills",
                "action": None
            },
            {
                "widget": self.mw.attr_editor,
                "title": "Applied Effects",
                "desc": "On the builder page, we can see the +5 Soul Reaping applied from the scythe. The primary attribute inherent effect is also applied (for example, a non-mesmer with the fast cast staff would see updated skill cast and recharge times).",
                "action": lambda: self.mw.btn_char_view.setChecked(False)
            },
            {
                "widget": self.mw.bar_area,
                "title": "Skill Bar",
                "desc": "Here is where you will add your skills. Lets pop one on.",
                "action": lambda: self.mw.reset_build()
            },
            {
                "widget": self.mw.bar_area,
                "title": "Pairing Suggestions",
                "desc": "The suggestions (ghost icons) are based off of how often skills are paired together on PvX Wiki. Let's add Vow of Strength.",
                "action": lambda: self.mw.handle_skill_equipped(0, 1759)
            },
            {
                "widget": self.mw.check_smart_mode,
                "title": "Smart Mode",
                "desc": "This experimental feature uses AI to find deeper synergies.",
                "action": None
            },
            {
                "widget": self.mw.bar_area,
                "title": "AI Suggestions",
                "desc": "These are not based on hard data and may provide unique suggestions (note: it may take a few seconds to load).",
                "action": lambda: self.mw.check_smart_mode.setChecked(True)
            },
            {
                "widget": [self.mw.combo_cat, self.mw.combo_team],
                "title": "PvX Wiki Data",
                "desc": "Here is where the PvX Wiki data is stored. You can select any category or teambuild. Lets look at mine.",
                "action": lambda: self.mw.check_smart_mode.setChecked(False)
            },
            {
                "widget": self.mw.library_widget,
                "title": "Team Builds",
                "desc": "Selecting a team loads all associated builds into the library for easy browsing. Here is 'Mosquito's Teambuild'.",
                "action": lambda: self._prep_mosquito_step()
            },
            {
                "widget": self.mw.btn_team_summary,
                "title": "Team Summary",
                "desc": "Click here to see a high-level overview of the entire team's composition and conditions.",
                "action": None
            },
            {
                "widget": self.mw.btn_manage_teams,
                "title": "Manage Teams",
                "desc": "Here is where teambuilds can be imported, exported, created, or modified.",
                "action": lambda: self.mw.open_team_summary()
            },
            {
                "widget": None,
                "title": "Tutorial Complete",
                "desc": "You're all set! Click Finish to reset the builder and start creating your own optimized builds.",
                "action": None
            }
        ]
        
        def on_tutorial_finished():
            self.mw.settings.setValue("tutorial_complete", True)
            self.mw.reset_build()
            
        self.overlay.finished.connect(on_tutorial_finished)
        self.overlay.start_tutorial(steps)

    def _prep_final_step(self):
        self.mw.character_panel.clear_runes()
        # Superior Vigor
        self.mw.character_panel.add_rune_direct("sup", attr_id="vigor")
        # Superior Earth Prayers (ID 43)
        self.mw.character_panel.add_rune_direct("sup", prof_id=10, attr_id=43)
        # Minor Mysticism (ID 44)
        self.mw.character_panel.add_rune_direct("minor", prof_id=10, attr_id=44)
        # 2x Attunement
        self.mw.character_panel.add_rune_direct("attunement", attr_id="attunement")
        self.mw.character_panel.add_rune_direct("attunement", attr_id="attunement")

    def _prep_mosquito_step(self):
        index = self.mw.combo_team.findText("Mosquito's Teambuild")
        if index != -1:
            self.mw.combo_team.setCurrentIndex(index)

    def _prep_mysticism_step(self):
        self.mw.load_code("OgCjsysaKScXfbzkEYsXWgPXXg")
        # Find Mysticism (ID 44)
        widgets = self.mw.attr_editor.get_attribute_widget(44)
        if widgets:
            self.overlay.target_widgets = [widgets[0]] 
        self.mw.handle_skill_id_clicked(1516) # Mystic Regen

    def _prep_norn_step(self):
        # Find Norn (ID -9)
        widgets = self.mw.attr_editor.get_attribute_widget(-9)
        if widgets:
            self.overlay.target_widgets = [widgets[0]] 
            widgets[1].setCurrentIndex(10) # Set rank 10
        self.mw.handle_skill_id_clicked(2355) # I Am The Strongest!

