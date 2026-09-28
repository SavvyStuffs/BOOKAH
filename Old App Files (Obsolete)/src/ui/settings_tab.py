import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QRadioButton, QButtonGroup, QLabel, QFrame, QCheckBox, QPushButton, QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QUrl
from PyQt6.QtGui import QPalette, QColor, QDesktopServices, QIcon
from src.ui.dialogs import FeedbackDialog, HistoryViewerDialog

class SettingsTab(QWidget):
    theme_changed = pyqtSignal(str) # Emits "Dark", "Light", or "Auto"
    campaigns_changed = pyqtSignal(dict) # Emits { 'Prophecies': bool, ... }
    tutorial_requested = pyqtSignal(str) # Emits section name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("Bookah", "Builder")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # --- Appearance Section ---
        group_appearance = QGroupBox("Appearance")
        group_appearance.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #444; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }")
        
        app_layout = QVBoxLayout(group_appearance)
        
        lbl_dark_mode = QLabel("Dark Mode:")
        app_layout.addWidget(lbl_dark_mode)
        
        self.btn_group_theme = QButtonGroup(self)
        self.btn_group_theme.buttonClicked.connect(self.on_theme_changed)
        
        self.radio_on = QRadioButton("On")
        self.radio_off = QRadioButton("Off")
        self.radio_auto = QRadioButton("Auto (System)")
        
        self.btn_group_theme.addButton(self.radio_on)
        self.btn_group_theme.addButton(self.radio_off)
        self.btn_group_theme.addButton(self.radio_auto)
        
        app_layout.addWidget(self.radio_on)
        app_layout.addWidget(self.radio_off)
        app_layout.addWidget(self.radio_auto)
        
        layout.addWidget(group_appearance)
        
        # --- Campaigns Section ---
        group_campaigns = QGroupBox("Campaigns")
        group_campaigns.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #444; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }")
        
        camp_layout = QVBoxLayout(group_campaigns)
        
        self.check_prophecies = QCheckBox("Prophecies")
        self.check_factions = QCheckBox("Factions")
        self.check_nightfall = QCheckBox("Nightfall")
        self.check_eotn = QCheckBox("Eye of the North")
        
        camp_layout.addWidget(self.check_prophecies)
        camp_layout.addWidget(self.check_factions)
        camp_layout.addWidget(self.check_nightfall)
        camp_layout.addWidget(self.check_eotn)
        
        self.check_prophecies.toggled.connect(self.on_campaigns_changed)
        self.check_factions.toggled.connect(self.on_campaigns_changed)
        self.check_nightfall.toggled.connect(self.on_campaigns_changed)
        self.check_eotn.toggled.connect(self.on_campaigns_changed)
        
        layout.addWidget(group_campaigns)

        # --- Feedback and Help Section ---
        group_feedback = QGroupBox("Feedback and Help")
        group_feedback.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #444; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }")
        
        feedback_layout = QVBoxLayout(group_feedback)
        
        # Feedback Button Row
        row_fb = QHBoxLayout()
        row_fb.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.btn_feedback = QPushButton("Send Feedback")
        self.btn_feedback.setFixedWidth(150)
        self.btn_feedback.setStyleSheet("""
            QPushButton { 
                background-color: #0078D7; 
                color: white; 
                padding: 8px; 
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #005A9E; }
        """)
        self.btn_feedback.clicked.connect(self.open_feedback)
        row_fb.addWidget(self.btn_feedback)
        feedback_layout.addLayout(row_fb)

        # Tutorial Buttons Row
        feedback_layout.addWidget(QLabel("Tutorials:"))
        row_tut = QHBoxLayout()
        row_tut.setAlignment(Qt.AlignmentFlag.AlignLeft)
        row_tut.setSpacing(10)

        style_tut = """
            QPushButton { 
                background-color: #CC0000; 
                color: white; 
                padding: 6px; 
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #AA0000; }
        """

        self.btn_tut_builds = QPushButton("Builds")
        self.btn_tut_builds.setFixedWidth(100)
        self.btn_tut_builds.setStyleSheet(style_tut)
        self.btn_tut_builds.clicked.connect(lambda: self.open_tutorial("Builds"))
        row_tut.addWidget(self.btn_tut_builds)

        self.btn_tut_char = QPushButton("Character")
        self.btn_tut_char.setFixedWidth(100)
        self.btn_tut_char.setStyleSheet(style_tut)
        self.btn_tut_char.clicked.connect(lambda: self.open_tutorial("Character"))
        row_tut.addWidget(self.btn_tut_char)

        self.btn_tut_teams = QPushButton("Teams")
        self.btn_tut_teams.setFixedWidth(100)
        self.btn_tut_teams.setStyleSheet(style_tut)
        self.btn_tut_teams.clicked.connect(lambda: self.open_tutorial("Teams"))
        row_tut.addWidget(self.btn_tut_teams)
        
        feedback_layout.addLayout(row_tut)
        
        layout.addWidget(group_feedback)

        # Spacer to push attribution to the bottom
        layout.addStretch()

        # Footer Layout (Attribution + Version)
        footer_layout = QHBoxLayout()
        
        self.lbl_attrib = QLabel("Brought to you by Military Mosquito")
        font = self.lbl_attrib.font()
        font.setItalic(True)
        self.lbl_attrib.setFont(font)
        self.lbl_attrib.setStyleSheet("QLabel { opacity: 0.75; letter-spacing: 1px; }")
        footer_layout.addWidget(self.lbl_attrib)
        
        footer_layout.addStretch()
        
        # Version Label
        from src.constants import resource_path
        import json
        import os
        version = "Unknown"
        try:
            with open(resource_path("version.json"), "r") as f:
                v_data = json.load(f)
                version = v_data.get("version", "Unknown")
        except:
            pass
            
        self.btn_version = QPushButton(f"v{version}")
        self.btn_version.setFlat(True)
        self.btn_version.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_version.clicked.connect(self.open_history)
        footer_layout.addWidget(self.btn_version)
        
        layout.addLayout(footer_layout)
        
        # Load saved settings
        current_theme = self.settings.value("theme", "Auto")
        
        self.refresh_theme() # Apply dynamic colors
        
        if current_theme == "Dark":
            self.radio_on.setChecked(True)
        elif current_theme == "Light":
            self.radio_off.setChecked(True)
        else:
            self.radio_auto.setChecked(True)
            
        self.check_prophecies.setChecked(True)
        self.check_factions.setChecked(True)
        self.check_nightfall.setChecked(True)
        self.check_eotn.setChecked(True)

    def open_feedback(self):
        last_time = float(self.settings.value("last_feedback_time", 0))
        elapsed = time.time() - last_time
        if elapsed < 60:
            remaining_sec = int(60 - elapsed)
            QMessageBox.warning(self, "Cooldown", f"Please wait, there is a cool down to prevent spam. {remaining_sec} seconds remaining")
            return

        dlg = FeedbackDialog(self)
        dlg.exec()
        self.settings.setValue("last_feedback_time", time.time())

    def open_tutorial(self, section="Builds"):
        self.tutorial_requested.emit(section)

    def open_history(self):
        dlg = HistoryViewerDialog(self)
        dlg.exec()

    def refresh_theme(self):
        from src.ui.theme import get_color
        text_color = get_color('text_primary')
        self.btn_version.setStyleSheet(f"QPushButton {{ border: none; background: transparent; opacity: 0.5; color: {text_color}; font-size: 10px; }} QPushButton:hover {{ color: #00AAFF; }}")
        self.lbl_attrib.setStyleSheet(f"QLabel {{ opacity: 0.75; color: {text_color}; letter-spacing: 1px; }}")

    def on_theme_changed(self, button):
        if button == self.radio_on:
            mode = "Dark"
        elif button == self.radio_off:
            mode = "Light"
        else:
            mode = "Auto"
            
        self.settings.setValue("theme", mode)
        self.refresh_theme() # Update local styles
        self.theme_changed.emit(mode)

    def on_campaigns_changed(self):
        campaigns = {
            'Prophecies': self.check_prophecies.isChecked(),
            'Factions': self.check_factions.isChecked(),
            'Nightfall': self.check_nightfall.isChecked(),
            'Eye of the North': self.check_eotn.isChecked()
        }
        
        self.settings.setValue("v2_campaign_prophecies", campaigns['Prophecies'])
        self.settings.setValue("v2_campaign_factions", campaigns['Factions'])
        self.settings.setValue("v2_campaign_nightfall", campaigns['Nightfall'])
        self.settings.setValue("v2_campaign_eotn", campaigns['Eye of the North'])
        
        self.campaigns_changed.emit(campaigns)