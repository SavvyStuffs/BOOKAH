import os
import json
import sqlite3
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget, QMessageBox, QFileDialog, QInputDialog, QTabWidget
)
from src.constants import PROF_MAP, JSON_FILE
from src.utils import GuildWarsTemplateDecoder
from src.models import Build

class TeamManagerDialog(QDialog):
    def __init__(self, parent=None, engine=None):
        super().__init__(parent)
        self.setWindowTitle("Team Build Manager")
        self.resize(400, 300)
        self.engine = engine
        self.parent_window = parent # Reference to MainWindow to get current build
        
        layout = QVBoxLayout(self)
        
        # Header with Plus button
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Teams:</b>"))
        header.addStretch()

        self.btn_export = QPushButton("Export")
        self.btn_export.setFixedSize(60, 24)
        self.btn_export.setToolTip("Export Selected Team Builds")
        self.btn_export.clicked.connect(self.export_team)
        header.addWidget(self.btn_export)

        self.btn_add_folder = QPushButton("+")
        self.btn_add_folder.setFixedSize(24, 24)
        self.btn_add_folder.setToolTip("Import Team from Folder")
        self.btn_add_folder.setStyleSheet("font-weight: bold; color: #00AAFF;")
        self.btn_add_folder.clicked.connect(self.add_from_folder)
        header.addWidget(self.btn_add_folder)
        layout.addLayout(header)
        
        # Search Bar
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Search teams...")
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

    def add_from_folder(self):
        # Open directory dialog
        folder_path = QFileDialog.getExistingDirectory(self, "Select Team Build Folder")
        if folder_path:
            # Use logic from main window
            self.parent_window.process_folder_drop(folder_path)
            self.refresh_list()
        
    def edit_team(self):
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        dlg = TeamEditorDialog(team_name, self.engine, self)
        dlg.exec()

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

            entry = {
                "build_code": code,
                "primary_profession": str(decoded['profession']['primary']),
                "secondary_profession": str(decoded['profession']['secondary']),
                "skill_ids": decoded['skills'],
                "category": "User Team",
                "team": name
            }
            
            # Append to engine data and save
            self.engine.builds.append(Build(
                code=entry['build_code'],
                primary_prof=entry['primary_profession'],
                secondary_prof=entry['secondary_profession'],
                skill_ids=entry['skill_ids'],
                category=entry['category'],
                team=entry['team']
            ))
            self.engine.teams.add(name)
            
            # Persist to JSON
            self.save_to_json(entry)
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
            
            # Remove from JSON
            self.remove_from_json(team_name)
            self.refresh_list()

    def save_to_json(self, entry):
        try:
            data = []
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data.append(entry)
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving: {e}")

    def remove_from_json(self, team_name):
        try:
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                new_data = [d for d in data if d.get('team') != team_name]
                
                with open(JSON_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, indent=4)
        except Exception as e:
            print(f"Error removing: {e}")

class TeamEditorDialog(QDialog):
    def __init__(self, team_name, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Team: {team_name}")
        self.resize(500, 400)
        self.team_name = team_name
        self.engine = engine
        
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.refresh_list()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        self.btn_del = QPushButton("Remove Selected Build")
        self.btn_del.clicked.connect(self.remove_build)
        btn_layout.addWidget(self.btn_del)
        
        layout.addLayout(btn_layout)

    def refresh_list(self):
        self.list_widget.clear()
        self.team_builds = [b for b in self.engine.builds if b.team == self.team_name]
        
        for i, b in enumerate(self.team_builds):
            # Try to describe the build
            p1 = PROF_MAP.get(int(b.primary_prof), "X")
            p2 = PROF_MAP.get(int(b.secondary_prof), "X")
            item_text = f"#{i+1}: {p1}/{p2} - {b.code}"
            self.list_widget.addItem(item_text)

    def remove_build(self):
        row = self.list_widget.currentRow()
        if row < 0: return

        build_to_remove = self.team_builds[row]

        # Remove from engine
        if build_to_remove in self.engine.builds:
            self.engine.builds.remove(build_to_remove)

        # Remove from JSON
        self.remove_specific_build_from_json(build_to_remove.code)

        self.refresh_list()

    def remove_specific_build_from_json(self, code):
        try:
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Remove FIRST match of code and team (in case of dupes)
                new_data = []
                removed = False
                for d in data:
                    if not removed and d.get('build_code') == code and d.get('team') == self.team_name:
                        removed = True # Skip this one
                    else:
                        new_data.append(d)
                
                with open(JSON_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, indent=4)
        except Exception as e:
            print(f"Error removing build: {e}")

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
