import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QRadioButton, QButtonGroup, QLabel, QFrame, QCheckBox, QPushButton, QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QUrl
from PyQt6.QtGui import QPalette, QColor, QDesktopServices, QIcon
from src.ui.dialogs import FeedbackDialog, WebBrowserDialog

class SettingsTab(QWidget):
    theme_changed = pyqtSignal(str) # Emits "Dark", "Light", or "Auto"
    campaigns_changed = pyqtSignal(dict) # Emits { 'Prophecies': bool, ... }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("Bookah", "Builder")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Attribution Label
        self.lbl_attrib = QLabel("Brought to you by Military Mosquito")
        font = self.lbl_attrib.font()
        font.setItalic(True)
        self.lbl_attrib.setFont(font)
        self.lbl_attrib.setStyleSheet("QLabel { opacity: 0.75; letter-spacing: 1px; }")
        self.lbl_attrib.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_attrib)
        
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

        # --- Feedback & Help Section ---
        group_feedback = QGroupBox("Feedback & Help")
        group_feedback.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #444; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }")
        
        feedback_layout = QHBoxLayout(group_feedback)
        
        self.btn_feedback = QPushButton("Send Feedback")
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
        feedback_layout.addWidget(self.btn_feedback)

        self.btn_tutorial = QPushButton(" Tutorial")
        self.btn_tutorial.setStyleSheet("""
            QPushButton { 
                background-color: #CC0000; 
                color: white; 
                padding: 8px; 
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #AA0000; }
        """)
        self.btn_tutorial.clicked.connect(self.open_tutorial)
        feedback_layout.addWidget(self.btn_tutorial)
        
        layout.addWidget(group_feedback)
        
        # Load saved settings
        current_theme = self.settings.value("theme", "Auto")
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
        if elapsed < 300:
            remaining_min = int((300 - elapsed) / 60) + 1
            unit = "minute" if remaining_min == 1 else "minutes"
            QMessageBox.warning(self, "Cooldown", f"Please wait, there is a cool down to prevent spam. {remaining_min} {unit} remaining")
            return

        dlg = FeedbackDialog(self)
        dlg.exec()
        self.settings.setValue("last_feedback_time", time.time())

    def open_tutorial(self):
        # Using the actual tutorial video URL with origin parameter to help fix Error 153
        url = "https://www.youtube.com/embed/rKSEPcfZOOw?origin=https://bookah.savvy-stuff.dev" 
        dlg = WebBrowserDialog(self, "Tutorial", url)
        dlg.exec()

    def on_theme_changed(self, button):
        if button == self.radio_on:
            mode = "Dark"
        elif button == self.radio_off:
            mode = "Light"
        else:
            mode = "Auto"
            
        self.settings.setValue("theme", mode)
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