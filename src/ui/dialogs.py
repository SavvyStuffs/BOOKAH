import os
import json
import sqlite3
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget, QMessageBox, QFileDialog, QInputDialog, QTabWidget
)
from src.constants import PROF_MAP, JSON_FILE
from src.utils import GuildWarsTemplateDecoder
from src.models import Build

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
        path = QFileDialog.getExistingDirectory(self, "Select Team Build Folder")
        if path:
            self.folder_path = path
            self.lbl_status.setText(f"Selected: {os.path.basename(path)}")
            if not self.edit_name.text():
                self.edit_name.setText(os.path.basename(path))

    def get_data(self):
        return self.edit_name.text().strip(), self.folder_path

class TeamManagerDialog(QDialog):
    def __init__(self, parent=None, engine=None):
        super().__init__(parent)
        self.setWindowTitle("Team Build Manager")
        self.resize(400, 300)
        self.engine = engine
        self.parent_window = parent # Reference to MainWindow to get current build
        
        layout = QVBoxLayout(self)
        
        # Header with Buttons
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Teams:</b>"))
        header.addStretch()

        self.btn_export = QPushButton("Export")
        self.btn_export.setFixedSize(60, 24)
        self.btn_export.setToolTip("Export Selected Team Builds")
        self.btn_export.clicked.connect(self.export_team)
        header.addWidget(self.btn_export)

        self.btn_new_team = QPushButton("+")
        self.btn_new_team.setFixedSize(24, 24)
        self.btn_new_team.setToolTip("Create New Team")
        self.btn_new_team.setStyleSheet("font-weight: bold; color: #00AAFF;")
        self.btn_new_team.clicked.connect(self.open_new_team_dialog)
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
        self.btn_del.setStyleSheet("background-color: #552222;")
        btn_layout.addWidget(self.btn_del)
        
        layout.addLayout(btn_layout)

    def refresh_list(self):
        self.list_widget.clear()
        search_text = self.edit_search.text().lower()
        teams = sorted(list(self.engine.teams))
        filtered_teams = [t for t in teams if search_text in t.lower()]
        self.list_widget.addItems(filtered_teams)
        
    def open_new_team_dialog(self):
        dlg = NewTeamDialog(self)
        if dlg.exec():
            name, folder = dlg.get_data()
            if not name:
                return
                
            if folder:
                self.parent_window.process_folder_drop(folder, team_name=name)
            else:
                self.engine.teams.add(name)
            
            self.refresh_list()
        
    def export_team(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Export", "Please select a team to export.")
            return
        team_name = item.text()
        # Set the combo box in parent so export_team_builds knows what to export
        idx = self.parent_window.combo_team.findText(team_name)
        if idx != -1:
            self.parent_window.combo_team.setCurrentIndex(idx)
            self.parent_window.export_team_builds()
        
    def edit_team(self):
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        dlg = TeamEditorDialog(team_name, self.engine, self)
        dlg.exec()
        self.refresh_list()

    def add_team(self):
        # Save current build as a new Team Build entry
        name, ok = QInputDialog.getText(self, "New Team Build", "Enter Team Name:")
        if ok and name:
            code = self.parent_window.edit_code.text()
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
                category="User Team",
                team=name
            )
            new_build.is_user_build = True
            
            self.engine.builds.append(new_build)
            self.engine.teams.add(name)
            
            # Save using centralized engine logic
            self.engine.save_user_builds()
            self.refresh_list()
            
    def load_team(self):
        # Set the main window's team filter to the selected team
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        
        # Find the team in the parent's combo box
        index = self.parent_window.combo_team.findText(team_name)
        if index != -1:
            self.parent_window.combo_team.setCurrentIndex(index)
            self.close()
        else:
            QMessageBox.warning(self, "Error", f"Team '{team_name}' not found in main list.")

    def remove_team(self):
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        
        confirm = QMessageBox.question(self, "Confirm", f"Delete all builds for team '{team_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            # Remove from memory
            self.engine.builds = [b for b in self.engine.builds if b.team != team_name]
            self.engine.teams.discard(team_name)
            
            # Save using centralized engine logic
            self.engine.save_user_builds()
            self.refresh_list()

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
                    b.is_user_build = True # Mark as user build to ensure it persists in user_builds.json
            
            self.engine.teams.discard(self.team_name)
            self.engine.teams.add(new_name)
            
            # Save using centralized engine logic
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

class BuildUniquenessDialog(QDialog):
    def __init__(self, matches, total_builds, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Build Uniqueness Check")
        self.resize(500, 400)
        
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
            
        layout.addWidget(self.list_widget)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
