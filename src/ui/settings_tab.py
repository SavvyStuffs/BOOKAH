from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QRadioButton, QButtonGroup, QLabel, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QPalette, QColor

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
        # We can set opacity via styleSheet, but color needs to adapt. 
        # Using "color: palette(text)" allows it to adapt to the QPalette set in MainWindow.
        # However, style sheets often override palette. 
        # Let's try standard palette first. If we want 75% opacity, we can set it in color.
        # But simpler is to use the same CSS approach as before, assuming the theme engine sets global palette.
        # Actually, since main window applies a global palette, standard labels just work.
        # To get 75% opacity, we can use a style sheet that references the palette?
        # Or just specific styling.
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
        
        # Core is always included? Or implies Prophecies? 
        # Usually Core skills are available to everyone. We might need to clarify if "Prophecies" means "Prophecies Only" or includes Core.
        # Typically Core skills have campaign=0. Prophecies=1, Factions=2, Nightfall=3, EotN=4.
        
        camp_layout.addWidget(self.check_prophecies)
        camp_layout.addWidget(self.check_factions)
        camp_layout.addWidget(self.check_nightfall)
        camp_layout.addWidget(self.check_eotn)
        
        self.check_prophecies.toggled.connect(self.on_campaigns_changed)
        self.check_factions.toggled.connect(self.on_campaigns_changed)
        self.check_nightfall.toggled.connect(self.on_campaigns_changed)
        self.check_eotn.toggled.connect(self.on_campaigns_changed)
        
        layout.addWidget(group_campaigns)
        
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
