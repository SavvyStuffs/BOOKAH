import os
import sys
import json
import sqlite3
import urllib.parse
import urllib.request
import time
import hashlib
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget, QMessageBox, QFileDialog, QInputDialog, QTabWidget, QTextEdit, QFrame, QScrollArea, QGridLayout, QWidget, QMenu,
    QGroupBox, QCheckBox, QRadioButton, QPlainTextEdit, QComboBox, QApplication
)
from PyQt6.QtCore import QUrl, QSettings, Qt
from PyQt6.QtGui import QPixmap, QAction

from src.ui.theme import get_color
from src.constants import PROF_MAP, JSON_FILE, ICON_DIR, ICON_SIZE, ATTR_MAP, PROF_SHORT_MAP, DB_FILE
from src.utils import GuildWarsTemplateDecoder, GuildWarsTemplateEncoder
from src.models import Build
from src.engine import CONDITION_DEFINITIONS
from src.sharing import ShareCodeManager, ShareWorker

class TeamSummaryDialog(QDialog):
    def __init__(self, team_name, builds, repo, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Team Summary: {team_name}")
        self.resize(600, 600)
        self.repo = repo
        
        layout = QVBoxLayout(self)
        
        # 1. Team-wide Conditions
        team_conditions = set()
        build_stats = []
        
        conn = sqlite3.connect(DB_FILE)
        
        for build in builds:
            total_nrg = 0
            skill_count = 0
            active_attrs = []
            
            # Attributes
            if build.attributes:
                for attr_id, rank in build.attributes:
                    if rank > 0:
                        name = ATTR_MAP.get(attr_id, f"Attr {attr_id}")
                        active_attrs.append(f"{name}: {rank}")
            
            # Skills
            for sid in build.skill_ids:
                if sid == 0: continue
                skill = repo.get_skill(sid)
                if not skill: continue
                
                total_nrg += skill.energy
                skill_count += 1
                
                # Fetch Tags
                cursor = conn.execute("SELECT tag FROM skill_tags WHERE skill_id = ?", (sid,))
                tags = {row[0] for row in cursor.fetchall()}
                
                # Verify if skill applies conditions
                if "Type_Condition" in tags:
                    desc = skill.description.lower()
                    for cond_name in CONDITION_DEFINITIONS.keys():
                        if cond_name in desc:
                            idx = desc.find(cond_name)
                            if idx != -1:
                                start = max(0, idx - 25)
                                prev_text = desc[start:idx]
                                negatives = ["remove", "cure", "lose", "end", "immune"]
                                if not any(neg in prev_text for neg in negatives):
                                    team_conditions.add(cond_name.title())

            avg_nrg = total_nrg / skill_count if skill_count > 0 else 0
            
            build_stats.append({
                'name': build.name,
                'p1': build.primary_prof,
                'p2': build.secondary_prof,
                'total_nrg': total_nrg,
                'avg_nrg': avg_nrg,
                'attrs': active_attrs
            })
            
        conn.close()

        # Conditions Header
        lbl_conds = QLabel("<b>Conditions Applied by Team:</b>")
        lbl_conds.setStyleSheet(f"font-size: 14px; color: {get_color('text_accent')};")
        layout.addWidget(lbl_conds)
        
        if team_conditions:
            cond_str = ", ".join(sorted(list(team_conditions)))
            lbl_cond_list = QLabel(cond_str)
            lbl_cond_list.setWordWrap(True)
            lbl_cond_list.setStyleSheet("color: #00FF00; font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(lbl_cond_list)
        else:
            layout.addWidget(QLabel("None detected."))
            
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background-color: {get_color('border')};")
        layout.addWidget(line)
        
        # Build List
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setSpacing(10)
        
        for stats in build_stats:
            # Build Card
            card = QFrame()
            card.setStyleSheet(f"background-color: {get_color('bg_tertiary')}; border-radius: 5px; padding: 5px; border: 1px solid {get_color('border')};")
            card_layout = QVBoxLayout(card)
            
            # Title
            p1_id = int(stats['p1']) if str(stats['p1']).isdigit() else 0
            p2_id = int(stats['p2']) if str(stats['p2']).isdigit() else 0
            p1_name = PROF_MAP.get(p1_id, "X")
            p2_name = PROF_MAP.get(p2_id, "X")
            p1_short = PROF_SHORT_MAP.get(p1_name, "X")
            p2_short = PROF_SHORT_MAP.get(p2_name, "X")
            
            name_str = f"{stats['name']} ({p1_short}/{p2_short})" if stats['name'] else f"Build ({p1_short}/{p2_short})"
            lbl_title = QLabel(f"<b>{name_str}</b>")
            lbl_title.setStyleSheet(f"font-size: 13px; color: {get_color('text_primary')};")
            card_layout.addWidget(lbl_title)
            
            # Data Grid
            grid = QGridLayout()
            grid.setContentsMargins(0,0,0,0)
            
            grid.addWidget(QLabel("Total Energy Cost:"), 0, 0)
            lbl_tot = QLabel(str(stats['total_nrg']))
            lbl_tot.setStyleSheet(f"color: {get_color('text_accent')}; font-weight: bold;")
            grid.addWidget(lbl_tot, 0, 1)
            
            grid.addWidget(QLabel("Avg Energy Cost:"), 1, 0)
            lbl_avg = QLabel(f"{stats['avg_nrg']:.1f}")
            lbl_avg.setStyleSheet(f"color: {get_color('text_accent')};")
            grid.addWidget(lbl_avg, 1, 1)
            
            grid.addWidget(QLabel("Attributes:"), 2, 0)
            attrs_str = ", ".join(stats['attrs']) if stats['attrs'] else "None"
            lbl_attrs = QLabel(attrs_str)
            lbl_attrs.setWordWrap(True)
            lbl_attrs.setStyleSheet(f"color: {get_color('text_secondary')};")
            grid.addWidget(lbl_attrs, 2, 1)
            
            card_layout.addLayout(grid)
            vbox.addWidget(card)
            
        vbox.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

class NewTeamDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Team")
        self.setFixedSize(300, 150)
        self.folder_path = None
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>Team Name:</b>"))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Enter team name...")
        layout.addWidget(self.edit_name)
        
        self.btn_import = QPushButton("Import Templates from Folder")
        self.btn_import.clicked.connect(self.choose_folder)
        layout.addWidget(self.btn_import)
        
        self.lbl_status = QLabel("No folder selected")
        self.lbl_status.setStyleSheet("font-size: 10px; color: #888;")
        layout.addWidget(self.lbl_status)
        
        btns = QHBoxLayout()
        self.btn_create = QPushButton("Create")
        self.btn_create.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_create)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

    def choose_folder(self):
        settings = QSettings("Bookah", "Builder")
        last_dir = settings.value("last_load_dir", "")
        path = QFileDialog.getExistingDirectory(self, "Select Team Build Folder", last_dir)
        if path:
            settings.setValue("last_load_dir", os.path.dirname(path))
            self.folder_path = path
            self.lbl_status.setText(f"Selected: {os.path.basename(path)}")
            if not self.edit_name.text():
                self.edit_name.setText(os.path.basename(path))

    def get_data(self):
        return self.edit_name.text().strip(), self.folder_path

class SharingDialog(QDialog):
    def __init__(self, parent=None, engine=None, team_name=None):
        super().__init__(parent)
        self.setWindowTitle("Share Team")
        self.resize(400, 300)
        self.engine = engine
        self.manager = ShareCodeManager()
        self.worker = None
        self.last_cycle_time = 0
        
        layout = QVBoxLayout(self)
        
        # --- TEAM SELECTION ---
        layout.addWidget(QLabel("<b>Select Team to Share:</b>"))
        self.combo_teams = QComboBox()
        layout.addWidget(self.combo_teams)
        
        # --- UPLOAD SECTION ---
        self.group_upload = QGroupBox("Generate Share Code:")
        self.group_upload.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {get_color('text_accent')}; border: 1px solid {get_color('border')}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        upload_layout = QVBoxLayout(self.group_upload)
        
        gen_layout = QHBoxLayout()
        self.edit_generated_code = QLineEdit()
        self.edit_generated_code.setPlaceholderText("Click cycle to find a code...")
        gen_layout.addWidget(self.edit_generated_code)
        
        self.btn_cycle = QPushButton("↻")
        self.btn_cycle.setFixedSize(24, 24)
        self.btn_cycle.setToolTip("Find a new unique code")
        self.btn_cycle.clicked.connect(self.start_generation)
        gen_layout.addWidget(self.btn_cycle)
        upload_layout.addLayout(gen_layout)
        
        self.btn_share = QPushButton("Share")
        self.btn_share.setStyleSheet("background-color: #224466; color: white; font-weight: bold;")
        self.btn_share.clicked.connect(self.upload_team)
        upload_layout.addWidget(self.btn_share)
        
        layout.addWidget(self.group_upload)
        
        layout.addSpacing(10)
        
        # Populate Teams (User Only)
        user_teams = set()
        for b in self.engine.builds:
            if b.category in ["User Created", "User Imported"]:
                user_teams.add(b.team)
        
        sorted_teams = sorted(list(user_teams))
        self.combo_teams.addItems(sorted_teams)
        
        # Select current if applicable
        if team_name and team_name in sorted_teams:
            self.combo_teams.setCurrentText(team_name)

        # Connect after population
        self.combo_teams.currentIndexChanged.connect(self.on_team_changed)
        
        # --- DOWNLOAD SECTION ---
        group_download = QGroupBox("Download Team")
        group_download.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {get_color('text_accent')}; border: 1px solid {get_color('border')}; margin-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        download_layout = QVBoxLayout(group_download)
        
        self.edit_input_code = QLineEdit()
        self.edit_input_code.setPlaceholderText("Enter share code here...")
        download_layout.addWidget(self.edit_input_code)
        
        self.btn_load_share = QPushButton("Import")
        self.btn_load_share.clicked.connect(self.download_team)
        download_layout.addWidget(self.btn_load_share)
        
        layout.addWidget(group_download)
        
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)
        
        # Init state
        self.on_team_changed()

    def calculate_team_hash(self, team_name):
        """Generates a deterministic hash of the team's current state."""
        builds = [b for b in self.engine.builds if b.team == team_name]
        # Sort by name to ensure consistent order (though list order in engine usually matters)
        # Using list order is safer for "Team position" consistency.
        
        data_str = f"{team_name}"
        for b in builds:
            # Include critical identifying info
            data_str += f"|{b.name}|{b.code}|{b.primary_prof}|{b.secondary_prof}"
            
        return hashlib.md5(data_str.encode('utf-8')).hexdigest()

    def on_team_changed(self):
        current = self.combo_teams.currentText()
        if current:
            self.group_upload.setTitle("Generate Share Code:")
            self.btn_share.setEnabled(True)
            self.team_name = current # Update current team context
            
            # Calculate current state hash
            current_hash = self.calculate_team_hash(current)
            
            # Check for existing code AND matching hash
            existing_code = None
            matches_hash = False
            
            for b in self.engine.builds:
                if b.team == current and b.share_code:
                    existing_code = b.share_code
                    if b.share_hash == current_hash:
                        matches_hash = True
                    break
            
            # Logic: We only treat it as "Shared" if the Hash matches.
            # If the code exists but hash differs, it means user modified the team locally.
            # So we allow re-sharing (generating/uploading to a NEW code).
            
            if existing_code and matches_hash:
                self.edit_generated_code.setText(existing_code)
                self.set_status("Existing code found!")
                self.btn_cycle.setEnabled(False) # Disable cycle for existing codes
                
                # Switch button to Copy mode
                self.btn_share.setText("Copy Share Code")
                self.btn_share.setStyleSheet("background-color: #0078D7; color: white; font-weight: bold;")
                try: self.btn_share.clicked.disconnect()
                except: pass
                self.btn_share.clicked.connect(self.copy_existing_code)
                
                # Stop any running generation
                if self.worker and self.worker.isRunning():
                    self.worker.terminate()
            else:
                self.btn_cycle.setEnabled(True)
                # Switch button to Share mode
                self.btn_share.setText("Share")
                self.btn_share.setStyleSheet("background-color: #224466; color: white; font-weight: bold;")
                try: self.btn_share.clicked.disconnect()
                except: pass
                self.btn_share.clicked.connect(self.upload_team)
                
                self.start_generation()
        else:
            self.group_upload.setTitle("Generate Share Code:")
            self.btn_share.setEnabled(False)

    def set_status(self, msg, error=False):
        color = "#FF5555" if error else "#55FF55"
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet(f"color: {color}; font-weight: bold;")

    def start_generation(self):
        now = time.time()
        if now - self.last_cycle_time < 1.0:
            return
        self.last_cycle_time = now

        self.btn_cycle.setEnabled(False)
        self.edit_generated_code.setText("Searching...")
        self.set_status("Finding unique code...")
        
        self.worker = ShareWorker(self.manager, "generate")
        self.worker.code_generated.connect(self.on_code_found)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(lambda: self.btn_cycle.setEnabled(True))
        self.worker.start()

    def on_code_found(self, code):
        self.edit_generated_code.setText(code)
        self.set_status("Code available!", error=False)

    def copy_existing_code(self):
        code = self.edit_generated_code.text().strip()
        if code:
            QApplication.clipboard().setText(code)
            self.set_status("Copied to clipboard!")

    def on_error(self, msg):
        self.set_status(msg, error=True)
        self.edit_generated_code.clear()

    def upload_team(self):
        code = self.edit_generated_code.text().strip()
        team_name = self.combo_teams.currentText()
        
        if not code or code == "Searching...":
            QMessageBox.warning(self, "Error", "Please wait for a valid code generation.")
            return
            
        if not team_name:
            QMessageBox.warning(self, "Error", "No team selected.")
            return
            
        # Serialize Team
        builds = [b for b in self.engine.builds if b.team == team_name]
        if not builds:
            QMessageBox.warning(self, "Error", "Empty team.")
            return
            
        # Structure matches user_builds.json format roughly, but wrapper for cloud
        # Cloud format: { "name": "Team Name", "builds": [ { ...build_obj... } ] }
        
        team_data = {
            "name": team_name,
            "builds": []
        }
        
        for b in builds:
            # We save everything needed to reconstruct
            b_entry = {
                "build_code": b.code,
                "primary_profession": b.primary_prof,
                "secondary_profession": b.secondary_prof,
                "skill_ids": b.skill_ids,
                "category": "User Imported", # Force category on import side usually
                "team": team_name,
                "name": b.name,
                "attributes": b.attributes # Important for memory
            }
            team_data["builds"].append(b_entry)
            
        self.set_status("Uploading...")
        self.btn_share.setEnabled(False)
        self.combo_teams.setEnabled(False)
        
        self.worker = ShareWorker(self.manager, "upload", code=code, data=team_data)
        self.worker.upload_success.connect(self.on_upload_success)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(lambda: [self.btn_share.setEnabled(True), self.combo_teams.setEnabled(True)])
        self.worker.start()

    def on_upload_success(self, code):
        team_name = self.combo_teams.currentText()
        new_hash = self.calculate_team_hash(team_name)
        
        # Save code to builds
        for b in self.engine.builds:
            if b.team == team_name:
                b.share_code = code
                b.share_hash = new_hash
                b.is_user_build = True
        self.engine.save_user_builds()
        
        # Refresh state so button switches to "Copy" immediately
        self.on_team_changed()
        
        self.set_status(f"Success! Code: {code}")
        QMessageBox.information(self, "Share Complete", f"Team '{team_name}' shared successfully!\n\nShare Code: {code}\n\n(Copied to clipboard)")
        QApplication.clipboard().setText(code)
        # self.accept() # Removed accept so user can see result, since we refresh state

    def download_team(self):
        code = self.edit_input_code.text().strip()
        if not code:
            return
            
        self.set_status("Downloading...")
        self.btn_load_share.setEnabled(False)
        
        self.worker = ShareWorker(self.manager, "download", code=code)
        self.worker.download_success.connect(self.on_download_success)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(lambda: self.btn_load_share.setEnabled(True))
        self.worker.start()

    def on_download_success(self, data):
        team_name = data.get("name", "Imported Team")
        builds_data = data.get("builds", [])
        
        # Check if team exists
        if team_name in self.engine.teams:
            # Rename to avoid conflict
            base_name = team_name
            counter = 1
            while team_name in self.engine.teams:
                team_name = f"{base_name} ({counter})"
                counter += 1
        
        self.engine.teams.add(team_name)
        
        for b_data in builds_data:
            # Reconstruct Build object from JSON data
            code = b_data.get("build_code") or b_data.get("code", "")
            decoder = GuildWarsTemplateDecoder(code)
            decoded = decoder.decode()
            
            if decoded:
                new_build = Build(
                    code=code,
                    primary_prof=str(decoded['profession']['primary']),
                    secondary_prof=str(decoded['profession']['secondary']),
                    skill_ids=decoded['skills'],
                    category="User Imported",
                    team=team_name,
                    name=b_data.get("name", "Imported Build"),
                    attributes=decoded['attributes'],
                    share_code=self.edit_input_code.text().strip(),
                    share_hash=self.calculate_team_hash(team_name) # Calculate hash for imported team to prevent immediate re-share prompt
                )
                new_build.is_user_build = True
                self.engine.builds.append(new_build)
        
        self.engine.save_user_builds()
        
        self.set_status("Import Successful!")
        QMessageBox.information(self, "Success", f"Imported team as '{team_name}'.")
        
        # Trigger refresh in parent
        if self.parent() and hasattr(self.parent(), 'refresh_list'):
             self.parent().refresh_list()
             
        self.accept()

class TeamManagerWidget(QWidget):
    def __init__(self, parent=None, engine=None, dialog_parent=None):
        super().__init__(parent)
        self.engine = engine
        mw_module = sys.modules.get('src.ui.main_window')
        MainWindowClass = getattr(mw_module, 'MainWindow', object) if mw_module else object
        self.parent_window = parent if isinstance(parent, MainWindowClass) else None
        # If embedded in dialog, we might need a ref to it to close it
        self.dialog_parent = dialog_parent 
        
        layout = QVBoxLayout(self)
        
        # Header with Buttons
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Teams:</b>"))
        header.addStretch()

        self.btn_sharing = QPushButton("Sharing")
        self.btn_sharing.setFixedSize(70, 24)
        self.btn_sharing.setToolTip("Generate share codes and download teambuilds")
        self.btn_sharing.setStyleSheet("""
            QPushButton { 
                background-color: #0078D7; 
                color: white; 
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #005A9E; }
        """)
        self.btn_sharing.clicked.connect(self.open_sharing_dialog)
        header.addWidget(self.btn_sharing)

        self.btn_export = QPushButton("Export")
        self.btn_export.setFixedSize(60, 24)
        self.btn_export.setToolTip("Export Selected Team Builds")
        self.btn_export.clicked.connect(self.export_team)
        header.addWidget(self.btn_export)

        self.btn_new_team = QPushButton("New...")
        self.btn_new_team.setFixedSize(60, 24)
        self.btn_new_team.setToolTip("Create New Team")
        self.btn_new_team.setStyleSheet("font-weight: bold; color: #00AAFF;")
        self.btn_new_team.clicked.connect(self.show_new_team_menu)
        header.addWidget(self.btn_new_team)
        
        layout.addLayout(header)
        
        # Search Bar
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Search teams...")
        self.edit_search.setStyleSheet("QLineEdit::placeholder { color: white; }")
        self.edit_search.textChanged.connect(self.refresh_list)
        layout.addWidget(self.edit_search)
        
        self.list_widget = QListWidget()
        self.refresh_list()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("Add Current Build to Team")
        self.btn_add.clicked.connect(self.add_team)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_edit = QPushButton("Edit Team")
        self.btn_edit.clicked.connect(self.edit_team)
        btn_layout.addWidget(self.btn_edit)
        
        self.btn_load = QPushButton("Open Team")
        self.btn_load.clicked.connect(self.load_team)
        btn_layout.addWidget(self.btn_load)
        
        self.btn_del = QPushButton("Delete Team")
        self.btn_del.clicked.connect(self.remove_team)
        self.btn_del.setStyleSheet("background-color: #552222; color: white;")
        btn_layout.addWidget(self.btn_del)
        
        layout.addLayout(btn_layout)

    def refresh_list(self):
        self.list_widget.clear()
        search_text = self.edit_search.text().lower()
        teams = sorted(list(self.engine.teams))
        filtered_teams = [t for t in teams if search_text in t.lower()]
        self.list_widget.addItems(filtered_teams)
        
    def show_new_team_menu(self):
        menu = QMenu(self)
        
        act_4 = QAction("4-Man Team", self)
        act_4.triggered.connect(lambda: self.create_empty_team(4))
        menu.addAction(act_4)
        
        act_6 = QAction("6-Man Team", self)
        act_6.triggered.connect(lambda: self.create_empty_team(6))
        menu.addAction(act_6)
        
        act_8 = QAction("8-Man Team", self)
        act_8.triggered.connect(lambda: self.create_empty_team(8))
        menu.addAction(act_8)
        
        act_12 = QAction("12-Man Team", self)
        act_12.triggered.connect(lambda: self.create_empty_team(12))
        menu.addAction(act_12)
        
        menu.addSeparator()
        
        act_import = QAction("Import from Folder...", self)
        act_import.triggered.connect(self.open_new_team_dialog)
        menu.addAction(act_import)
        
        menu.exec(self.btn_new_team.mapToGlobal(self.btn_new_team.rect().bottomLeft()))

    def create_empty_team(self, size):
        name, ok = QInputDialog.getText(self, "New Team", f"Enter name for {size}-man team:")
        if not ok or not name:
            return
            
        if name in self.engine.teams:
            QMessageBox.warning(self, "Error", f"Team '{name}' already exists!")
            return

        empty_data = {
            'header': {'type': 14, 'version': 0},
            'profession': {'primary': 0, 'secondary': 0},
            'attributes': [],
            'skills': [0] * 8
        }
        encoder = GuildWarsTemplateEncoder(empty_data)
        empty_code = encoder.encode()
        
        self.engine.teams.add(name)
        
        for i in range(size):
            b = Build(
                code=empty_code,
                primary_prof="0",
                secondary_prof="0",
                skill_ids=[0]*8,
                category="User Created",
                team=name,
                name=f"Hero {i+1}",
                attributes=[]
            )
            b.is_user_build = True
            self.engine.builds.append(b)
            
        self.engine.save_user_builds()
        self.refresh_list()
        
        items = self.list_widget.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.list_widget.setCurrentItem(items[0])
            self.load_team()

    def open_new_team_dialog(self):
        dlg = NewTeamDialog(self)
        if dlg.exec():
            name, folder = dlg.get_data()
            if not name:
                return
                
            if folder:
                # Need access to main window logic for drop processing
                if self.parent_window:
                    self.parent_window.process_folder_drop(folder, team_name=name)
            else:
                self.engine.teams.add(name)
            
            self.refresh_list()
            
            items = self.list_widget.findItems(name, Qt.MatchFlag.MatchExactly)
            if items:
                self.list_widget.setCurrentItem(items[0])
                self.load_team()
        
    def open_sharing_dialog(self):
        item = self.list_widget.currentItem()
        team_name = item.text() if item else None
        
        dlg = SharingDialog(self, self.engine, team_name)
        dlg.exec()
        # Refresh list in case a team was imported
        self.refresh_list()

    def export_team(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Export", "Please select a team to export.")
            return
        team_name = item.text()
        
        settings = QSettings("Bookah", "Builder")
        last_dir = settings.value("last_export_dir", "")
        export_dir = QFileDialog.getExistingDirectory(self, f"Select Folder to Export '{team_name}'", last_dir)
        if not export_dir:
            return
        
        settings.setValue("last_export_dir", os.path.dirname(export_dir))

        matching_builds = [b for b in self.engine.builds if b.team == team_name]
        if not matching_builds:
            QMessageBox.information(self, "Export", "No builds found to export.")
            return

        unique_builds = []
        seen_codes = set()
        for b in matching_builds:
            if b.code not in seen_codes:
                unique_builds.append(b)
                seen_codes.add(b.code)
        
        saved_count = 0
        from src.constants import PROF_MAP, PROF_SHORT_MAP
        
        for b in unique_builds:
            p1_id = int(b.primary_prof) if b.primary_prof.isdigit() else 0
            p2_id = int(b.secondary_prof) if b.secondary_prof.isdigit() else 0
            
            p1_name = PROF_MAP.get(p1_id, "X")
            p2_name = PROF_MAP.get(p2_id, "X")
            p1 = PROF_SHORT_MAP.get(p1_name, "X")
            p2 = PROF_SHORT_MAP.get(p2_name, "X")
            
            if b.name:
                base_name = f"{b.name} ({p1}-{p2})"
            else:
                base_name = f"{p1}-{p2}"
                
            safe_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_', '(', ')')).strip()
            filename = f"{safe_name}.txt"
            full_path = os.path.join(export_dir, filename)
            
            counter = 1
            while os.path.exists(full_path):
                name_part, ext = os.path.splitext(filename)
                full_path = os.path.join(export_dir, f"{name_part} ({counter}){ext}")
                counter += 1
            
            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(b.code)
                saved_count += 1
            except Exception as e:
                print(f"Error saving {filename}: {e}")
        
        QMessageBox.information(self, "Export Complete", f"Successfully exported {saved_count} builds to:\n{export_dir}")
        
    def edit_team(self):
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        dlg = TeamEditorDialog(team_name, self.engine, self)
        dlg.exec()
        self.refresh_list()

    def add_team(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Select Team", "Please select a team from the list to add this build to.")
            return
            
        team_name = item.text()
        existing_builds = [b for b in self.engine.builds if b.team == team_name]
        category = existing_builds[0].category if existing_builds else "User Created"
        
        build_name, ok = QInputDialog.getText(self, "Build Name", "Enter a name for this build (optional):")
        if not ok: return 
        
        if self.parent_window:
            code = self.parent_window.edit_code.text()
        else:
            code = "" # Should handle gracefully if no parent
            
        if not code:
            QMessageBox.warning(self, "Error", "No build code to save!")
            return
            
        decoder = GuildWarsTemplateDecoder(code)
        decoded = decoder.decode()
        if not decoded: return

        new_build = Build(
            code=code,
            primary_prof=str(decoded['profession']['primary']),
            secondary_prof=str(decoded['profession']['secondary']),
            skill_ids=decoded['skills'],
            category=category,
            team=team_name,
            name=build_name.strip()
        )
        new_build.is_user_build = True
        
        self.engine.builds.append(new_build)
        self.engine.teams.add(team_name)
        self.engine.save_user_builds()
        
        if self.parent_window and hasattr(self.parent_window, 'apply_filters'):
            self.parent_window.apply_filters()
        
        QMessageBox.information(self, "Success", f"Build '{build_name}' added to team '{team_name}'.")
            
    def load_team(self):
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        
        if self.parent_window:
            # Reset Category to "All" to ensure team is visible
            if hasattr(self.parent_window, 'combo_cat'):
                self.parent_window.combo_cat.blockSignals(True)
                self.parent_window.combo_cat.setCurrentIndex(0) # "All"
                self.parent_window.combo_cat.blockSignals(False)

            if hasattr(self.parent_window, 'update_team_dropdown'):
                self.parent_window.update_team_dropdown()
            
            index = self.parent_window.combo_team.findText(team_name)
            if index != -1:
                self.parent_window.combo_team.setCurrentIndex(index)
                if self.dialog_parent:
                    self.dialog_parent.close()
            else:
                QMessageBox.warning(self, "Error", f"Team '{team_name}' not found in main list.")

    def remove_team(self):
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        
        confirm = QMessageBox.question(self, "Confirm", f"Delete all builds for team '{team_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.engine.builds = [b for b in self.engine.builds if b.team != team_name]
            self.engine.teams.discard(team_name)
            self.engine.save_user_builds()
            self.refresh_list()
            
            if self.parent_window and hasattr(self.parent_window, 'update_team_dropdown'):
                self.parent_window.update_team_dropdown()
                # Stay on Team Manager view

class TeamManagerDialog(QDialog):
    def __init__(self, parent=None, engine=None, restricted_mode=False):
        super().__init__(parent)
        self.setWindowTitle("Team Build Manager")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        self.widget = TeamManagerWidget(parent, engine, dialog_parent=self)
        layout.addWidget(self.widget)
        
        # Expose widgets for tutorial compatibility (optional proxy)
        self.btn_export = self.widget.btn_export
        self.btn_new_team = self.widget.btn_new_team
        self.list_widget = self.widget.list_widget
        self.btn_load = self.widget.btn_load
        self.btn_add = self.widget.btn_add
        self.btn_edit = self.widget.btn_edit
        self.btn_del = self.widget.btn_del
        
        if restricted_mode:
            self.btn_new_team.setVisible(False)
            self.btn_add.setVisible(False)
            self.btn_edit.setVisible(False)
            self.btn_export.setVisible(False)

    def show_new_team_menu(self):
        self.widget.show_new_team_menu()
    
    def load_team(self):
        self.widget.load_team()


class TeamEditorDialog(QDialog):
    def __init__(self, team_name, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Team: {team_name}")
        self.resize(500, 400)
        self.team_name = team_name
        self.engine = engine
        
        layout = QVBoxLayout(self)
        
        # Header with Rename Team button
        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>Team:</b> {team_name}"))
        header.addStretch()
        self.btn_rename_team = QPushButton("Rename Team")
        self.btn_rename_team.setFixedSize(100, 24)
        self.btn_rename_team.clicked.connect(self.rename_team)
        header.addWidget(self.btn_rename_team)
        layout.addLayout(header)

        self.list_widget = QListWidget()
        self.refresh_list()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        self.btn_rename = QPushButton("Rename Selected Build")
        self.btn_rename.clicked.connect(self.rename_build)
        btn_layout.addWidget(self.btn_rename)

        self.btn_del = QPushButton("Remove Selected Build")
        self.btn_del.clicked.connect(self.remove_build)
        btn_layout.addWidget(self.btn_del)
        
        layout.addLayout(btn_layout)

    def rename_team(self):
        new_name, ok = QInputDialog.getText(self, "Rename Team", "Enter new team name:", text=self.team_name)
        if ok and new_name and new_name != self.team_name:
            # Update in memory
            for b in self.engine.builds:
                if b.team == self.team_name:
                    b.team = new_name
                    b.is_user_build = True 
            
            self.engine.teams.discard(self.team_name)
            self.engine.teams.add(new_name)
            
            # Save data
            self.engine.save_user_builds()
            
            # Update UI
            self.team_name = new_name
            self.setWindowTitle(f"Edit Team: {self.team_name}")
            # Update the label in header
            for i in range(self.layout().itemAt(0).layout().count()):
                item = self.layout().itemAt(0).layout().itemAt(i).widget()
                if isinstance(item, QLabel) and "Team:" in item.text():
                    item.setText(f"<b>Team:</b> {self.team_name}")
                    break
            
            self.refresh_list()
            
            # Refresh main window if it's showing this team
            if hasattr(self.parent(), 'parent_window'):
                self.parent().parent_window.apply_filters()

    def rename_build(self):
        row = self.list_widget.currentRow()
        if row < 0: return
        
        build = self.team_builds[row]
        new_name, ok = QInputDialog.getText(self, "Rename Build", "Enter build name:", text=build.name)
        if ok:
            build.name = new_name.strip()
            build.is_user_build = True
            self.engine.save_user_builds()
            self.refresh_list()
            
            # Refresh main window list to show new name
            if hasattr(self.parent(), 'parent_window'):
                self.parent().parent_window.apply_filters()

    def refresh_list(self):
        self.list_widget.clear()
        self.team_builds = [b for b in self.engine.builds if b.team == self.team_name]
        
        for i, b in enumerate(self.team_builds):
            # Try to describe the build
            p1 = PROF_MAP.get(int(b.primary_prof), "X")
            p2 = PROF_MAP.get(int(b.secondary_prof), "X")
            name_str = f" ({b.name})" if b.name else ""
            item_text = f"#{i+1}: {p1}/{p2}{name_str} - {b.code}"
            self.list_widget.addItem(item_text)

    def remove_build(self):
        row = self.list_widget.currentRow()
        if row < 0: return

        build_to_remove = self.team_builds[row]

        # Remove from engine
        if build_to_remove in self.engine.builds:
            self.engine.builds.remove(build_to_remove)

        # Save using centralized engine logic
        self.engine.save_user_builds()

        self.refresh_list()


class LocationManagerDialog(QDialog):
    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self.setWindowTitle("Locations")
        self.resize(450, 600)
        self.db_path = db_path
        
        layout = QVBoxLayout(self)
        
        # Search Bar
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Search locations...")
        self.edit_search.textChanged.connect(self.refresh_list)
        layout.addWidget(self.edit_search)
        
        self.tabs = QTabWidget()
        
        self.list_zones = QListWidget()
        self.list_missions = QListWidget()
        
        self.tabs.addTab(self.list_zones, "Explorable Zones")
        self.tabs.addTab(self.list_missions, "Missions")
        
        layout.addWidget(self.tabs)
        
        btn_layout = QHBoxLayout()
        self.btn_select = QPushButton("Select Location")
        self.btn_select.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_select)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.refresh_list()

    def refresh_list(self):
        self.list_zones.clear()
        self.list_missions.clear()
        search_text = self.edit_search.text().lower()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Load Explorable Zones
            cursor.execute("SELECT name FROM locations WHERE type = 'Location' ORDER BY name ASC")
            zones = [row[0] for row in cursor.fetchall() if search_text in row[0].lower()]
            self.list_zones.addItems(zones)
            
            # Load Missions
            cursor.execute("SELECT name FROM locations WHERE type = 'Mission' ORDER BY name ASC")
            missions = [row[0] for row in cursor.fetchall() if search_text in row[0].lower()]
            self.list_missions.addItems(missions)
            
            conn.close()
        except Exception as e:
            print(f"Error loading locations: {e}")

    def get_selected_location(self):
        # Check active tab
        if self.tabs.currentIndex() == 0:
            item = self.list_zones.currentItem()
        else:
            item = self.list_missions.currentItem()
        return item.text() if item else None

class BuildComparisonDialog(QDialog):
    def __init__(self, user_skills, other_build, repo, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Comparing with {other_build.name or 'Unknown Build'}")
        self.resize(600, 300)
        
        layout = QVBoxLayout(self)
        
        # User Build
        layout.addWidget(QLabel("<b>Your Build:</b>"))
        user_row = QHBoxLayout()
        user_row.setSpacing(2)
        
        other_ids = set([s for s in other_build.skill_ids if s != 0])
        
        for sid in user_skills:
            if sid == 0: continue
            lbl = self._create_skill_icon(sid, repo, sid in other_ids)
            user_row.addWidget(lbl)
        user_row.addStretch()
        layout.addLayout(user_row)
        
        layout.addSpacing(20)
        
        # Other Build
        p1 = PROF_MAP.get(int(other_build.primary_prof) if other_build.primary_prof.isdigit() else 0, "X")
        p2 = PROF_MAP.get(int(other_build.secondary_prof) if other_build.secondary_prof.isdigit() else 0, "X")
        layout.addWidget(QLabel(f"<b>Match: {p1}/{p2} - {other_build.team}:</b>"))
        
        other_row = QHBoxLayout()
        other_row.setSpacing(2)
        
        user_ids_set = set(user_skills)
        
        for sid in other_build.skill_ids:
            if sid == 0: continue
            lbl = self._create_skill_icon(sid, repo, sid in user_ids_set)
            other_row.addWidget(lbl)
        other_row.addStretch()
        layout.addLayout(other_row)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _create_skill_icon(self, sid, repo, is_match):
        skill = repo.get_skill(sid)
        lbl = QLabel()
        lbl.setFixedSize(48, 48)
        lbl.setScaledContents(True)
        
        if skill:
            path = os.path.join(ICON_DIR, skill.icon_filename)
            if os.path.exists(path):
                pix = QPixmap(path)
                lbl.setPixmap(pix)
                lbl.setToolTip(f"<b>{skill.name}</b><br>{skill.description}")
        
        if is_match:
            lbl.setStyleSheet("border: 3px solid #00FF00;")
        else:
            lbl.setStyleSheet("border: 1px solid #555; opacity: 0.7;")
            
        return lbl

class BuildUniquenessDialog(QDialog):
    def __init__(self, matches, total_builds, active_ids, repo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Build Uniqueness Check")
        self.resize(500, 400)
        self.matches = matches
        self.active_ids = active_ids
        self.repo = repo
        
        layout = QVBoxLayout(self)
        
        # Summary
        if not matches:
            summary = f"<h3>This build is Unique!</h3><p>No other builds in the database ({total_builds} total) share 8/8 skills.</p>"
        else:
            exact_matches = [m for m in matches if m['score'] == 8]
            if exact_matches:
                summary = f"<h3>Found {len(exact_matches)} Exact Matches!</h3>"
            else:
                summary = f"<h3>Partial Matches Only</h3><p>Highest overlap is {matches[0]['score']}/8 skills.</p>"
        
        lbl_summary = QLabel(summary)
        lbl_summary.setWordWrap(True)
        layout.addWidget(lbl_summary)
        
        # List of matches
        self.list_widget = QListWidget()
        
        # matches is list of {'score': int, 'build': Build}
        for m in matches:
            score = m['score']
            b = m['build']
            
            # Profession string
            p1 = PROF_MAP.get(int(b.primary_prof) if b.primary_prof.isdigit() else 0, "X")
            p2 = PROF_MAP.get(int(b.secondary_prof) if b.secondary_prof.isdigit() else 0, "X")
            
            text = f"[{score}/8 Matches] {p1}/{p2} - {b.team} ({b.category})"
            self.list_widget.addItem(text)
        
        self.list_widget.itemClicked.connect(self.show_comparison)
        layout.addWidget(self.list_widget)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def show_comparison(self, item):
        row = self.list_widget.row(item)
        if row < 0 or row >= len(self.matches): return
        
        match_data = self.matches[row]
        dlg = BuildComparisonDialog(self.active_ids, match_data['build'], self.repo, self)
        dlg.exec()

class FeedbackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Send Feedback")
        self.resize(500, 500)
        
        layout = QVBoxLayout(self)
        
        # 1. Feedback Type
        group_type = QGroupBox("Feedback Type")
        type_layout = QHBoxLayout(group_type)
        self.check_bug = QCheckBox("Bug Report")
        self.check_feat = QCheckBox("Feature Request")
        self.check_tune = QCheckBox("Tuning")
        type_layout.addWidget(self.check_bug)
        type_layout.addWidget(self.check_feat)
        type_layout.addWidget(self.check_tune)
        layout.addWidget(group_type)
        
        # 2. Feedback Message
        layout.addWidget(QLabel("Your Feedback:"))
        self.edit_feedback = QPlainTextEdit()
        self.edit_feedback.setPlaceholderText("Describe your bug, feature request, or tuning suggestion here...")
        layout.addWidget(self.edit_feedback)
        
        # 3. Helpful?
        group_help = QGroupBox("Do you find BOOKAH helpful?")
        help_layout = QHBoxLayout(group_help)
        self.radio_yes = QRadioButton("Yes")
        self.radio_no = QRadioButton("No")
        self.radio_kind = QRadioButton("Kind of")
        help_layout.addWidget(self.radio_yes)
        help_layout.addWidget(self.radio_no)
        help_layout.addWidget(self.radio_kind)
        layout.addWidget(group_help)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_submit = QPushButton("Submit Feedback")
        self.btn_submit.setStyleSheet("font-weight: bold; color: #00FF00;")
        self.btn_submit.clicked.connect(self.submit_feedback)
        btn_layout.addWidget(self.btn_submit)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)

    def submit_feedback(self):
        feedback_text = self.edit_feedback.toPlainText().strip()
        if not feedback_text:
            QMessageBox.warning(self, "Error", "Please enter some feedback before submitting.")
            return
            
        # Collect Types
        types = []
        if self.check_bug.isChecked(): types.append("Bug Report")
        if self.check_feat.isChecked(): types.append("Feature Request")
        if self.check_tune.isChecked(): types.append("Tuning")
        
        # Collect Helpful
        helpful = ""
        if self.radio_yes.isChecked(): helpful = "Yes"
        elif self.radio_no.isChecked(): helpful = "No"
        elif self.radio_kind.isChecked(): helpful = "Kind of"
        
        # Google Form POST Data
        form_url = "https://docs.google.com/forms/d/e/1FAIpQLSeqm4mSd7Yn6aDMhmLt5bOv3QBGc9jl2dVfEE7YtvQFpjyI7A/formResponse"
        
        post_data = {
            'entry.1591633300': types,
            'entry.326955045': feedback_text,
            'entry.1649013129': helpful
        }
        
        try:
            encoded_data = urllib.parse.urlencode(post_data, doseq=True).encode('utf-8')
            req = urllib.request.Request(form_url, data=encoded_data, method='POST')
            urllib.request.urlopen(req)
            QMessageBox.information(self, "Success", "Thank you! Your feedback has been submitted.")
            self.accept()
        except Exception as e:
            # Google Forms often returns a 200 even if it fails to redirect, 
            # but standard urllib might throw on the redirect. 
            # We'll assume success if no major error.
            if "HTTP Error 400" in str(e):
                 QMessageBox.critical(self, "Error", f"Submission failed (Bad Request). Please check fields.\n{e}")
            else:
                 QMessageBox.information(self, "Success", "Thank you! Your feedback has been submitted.")
                 self.accept()

class ProfessionSelectionDialog(QDialog):
    def __init__(self, current_primary, current_secondary, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Professions")
        self.setFixedSize(300, 150)
        self.selected_primary = current_primary
        self.selected_secondary = current_secondary
        
        layout = QVBoxLayout(self)
        
        # Primary Profession
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Primary:"))
        self.combo_primary = self._create_prof_combo()
        self._set_combo(self.combo_primary, current_primary)
        h1.addWidget(self.combo_primary)
        layout.addLayout(h1)
        
        # Secondary Profession
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Secondary:"))
        self.combo_secondary = self._create_prof_combo()
        self._set_combo(self.combo_secondary, current_secondary)
        h2.addWidget(self.combo_secondary)
        layout.addLayout(h2)
        
        # Buttons
        btns = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_ok.clicked.connect(self.accept_selection)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

        # Exclusion Logic
        self.combo_primary.currentIndexChanged.connect(self._update_exclusions)
        self.combo_secondary.currentIndexChanged.connect(self._update_exclusions)
        self._update_exclusions()

    def _create_prof_combo(self):
        from PyQt6.QtWidgets import QComboBox
        cb = QComboBox()
        cb.addItem("None", 0)
        # Sort by ID for consistency
        for pid in sorted(PROF_MAP.keys()):
            if pid == 0: continue
            cb.addItem(f"{PROF_MAP[pid]}", pid)
        return cb

    def _set_combo(self, combo, prof_id):
        index = combo.findData(prof_id)
        if index != -1:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentIndex(0) # None

    def _update_exclusions(self):
        p1_val = self.combo_primary.currentData()
        p2_val = self.combo_secondary.currentData()
        
        self._set_item_disabled(self.combo_secondary, p1_val)
        self._set_item_disabled(self.combo_primary, p2_val)

    def _set_item_disabled(self, combo, value_to_disable):
        model = combo.model()
        if not hasattr(model, 'item'): return

        for i in range(combo.count()):
            val = combo.itemData(i)
            item = model.item(i)
            
            # If this item matches the value to disable (and is not None/0)
            if val == value_to_disable and val != 0:
                item.setEnabled(False)
            else:
                item.setEnabled(True)

    def accept_selection(self):
        self.selected_primary = self.combo_primary.currentData()
        self.selected_secondary = self.combo_secondary.currentData()
        self.accept()

    def get_professions(self):
        return self.selected_primary, self.selected_secondary