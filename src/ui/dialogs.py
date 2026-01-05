import os
import json
import sqlite3
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget, QMessageBox, QFileDialog, QInputDialog, QTabWidget, QTextEdit, QFrame, QScrollArea, QGridLayout, QWidget
)
from PyQt6.QtCore import QUrl, QSettings
from PyQt6.QtGui import QPixmap

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineHttpRequest
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from src.ui.theme import get_color
from src.constants import PROF_MAP, JSON_FILE, ICON_DIR, ICON_SIZE, ATTR_MAP, PROF_SHORT_MAP, DB_FILE
from src.utils import GuildWarsTemplateDecoder
from src.models import Build
from src.engine import CONDITION_DEFINITIONS

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

class TeamManagerDialog(QDialog):
    def __init__(self, parent=None, engine=None):
        super().__init__(parent)
        self.setWindowTitle("Team Build Manager")
        self.resize(400, 300)
        self.engine = engine
        self.parent_window = parent
        
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
            
            # Auto-select and open the new team
            items = self.list_widget.findItems(name, Qt.MatchFlag.MatchExactly)
            if items:
                self.list_widget.setCurrentItem(items[0])
                self.load_team()
        
    def export_team(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Export", "Please select a team to export.")
            return
        team_name = item.text()
        
        # Ask for export directory
        settings = QSettings("Bookah", "Builder")
        last_dir = settings.value("last_export_dir", "")
        export_dir = QFileDialog.getExistingDirectory(self, f"Select Folder to Export '{team_name}'", last_dir)
        if not export_dir:
            return
        
        settings.setValue("last_export_dir", os.path.dirname(export_dir))

        # Get matching builds
        matching_builds = [b for b in self.engine.builds if b.team == team_name]
        if not matching_builds:
            QMessageBox.information(self, "Export", "No builds found to export.")
            return

        # Ensure we only export unique codes within this export batch
        unique_builds = []
        seen_codes = set()
        for b in matching_builds:
            if b.code not in seen_codes:
                unique_builds.append(b)
                seen_codes.add(b.code)
        
        saved_count = 0
        from src.constants import PROF_MAP, PROF_SHORT_MAP
        
        for b in unique_builds:
            # Determine File Name
            p1_id = int(b.primary_prof) if b.primary_prof.isdigit() else 0
            p2_id = int(b.secondary_prof) if b.secondary_prof.isdigit() else 0
            
            p1_name = PROF_MAP.get(p1_id, "X")
            p2_name = PROF_MAP.get(p2_id, "X")
            p1 = PROF_SHORT_MAP.get(p1_name, "X")
            p2 = PROF_SHORT_MAP.get(p2_name, "X")
            
            # Use build name if available, otherwise just professions
            if b.name:
                base_name = f"{b.name} ({p1}-{p2})"
            else:
                base_name = f"{p1}-{p2}"
                
            # Sanitize filename
            safe_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_', '(', ')')).strip()
            filename = f"{safe_name}.txt"
            full_path = os.path.join(export_dir, filename)
            
            # Handle duplicates in the file system
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
        # Get selected team
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Select Team", "Please select a team from the list to add this build to.")
            return
            
        team_name = item.text()
        
        # Determine category (Inherit from team, or default to User Created)
        existing_builds = [b for b in self.engine.builds if b.team == team_name]
        category = existing_builds[0].category if existing_builds else "User Created"
        
        # Prompt for Build Name
        build_name, ok = QInputDialog.getText(self, "Build Name", "Enter a name for this build (optional):")
        if not ok: return # User cancelled
        
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
            category=category,
            team=team_name,
            name=build_name.strip()
        )
        new_build.is_user_build = True
        
        self.engine.builds.append(new_build)
        self.engine.teams.add(team_name)
        
        # Save using centralized engine logic
        self.engine.save_user_builds()
        
        # Refresh main window if it exists
        if self.parent_window and hasattr(self.parent_window, 'apply_filters'):
            self.parent_window.apply_filters()
        
        QMessageBox.information(self, "Success", f"Build '{build_name}' added to team '{team_name}'.")
            
    def load_team(self):
        # Set the main window's team filter to the selected team
        item = self.list_widget.currentItem()
        if not item: return
        team_name = item.text()
        
        # Ensure parent dropdown is up to date
        if hasattr(self.parent_window, 'update_team_dropdown'):
            self.parent_window.update_team_dropdown()
        
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

class WebBrowserDialog(QDialog):
    def __init__(self, parent=None, title="Web Browser", url="https://google.com"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1024, 768)
        
        layout = QVBoxLayout(self)
        
        if HAS_WEBENGINE:
            self.web_view = QWebEngineView()
            
            if "youtube.com/embed" in url:
                # Wrap YouTube embeds in a local HTML page to enforce Referer/Origin
                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body, html {{ margin: 0; padding: 0; height: 100%; overflow: hidden; background: #000; }}
                        iframe {{ width: 100%; height: 100%; border: 0; }}
                    </style>
                </head>
                <body>
                    <iframe src="{url}" allow="autoplay; encrypted-media" allowfullscreen></iframe>
                </body>
                </html>
                """
                self.web_view.setHtml(html, QUrl("https://bookah.savvy-stuff.dev"))
            else:
                # Direct load for other URLs (like Google Forms)
                req = QWebEngineHttpRequest(QUrl(url))
                req.setHeader(b"Referer", b"https://bookah.savvy-stuff.dev")
                self.web_view.load(req)
                
            layout.addWidget(self.web_view)
        else:
            lbl = QLabel(f"<b>Error:</b> The embedded browser component (PyQt6-WebEngine) is not installed.<br>Cannot display: {url}")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

class FeedbackDialog(WebBrowserDialog):
    def __init__(self, parent=None):
        url = "https://forms.gle/71osvp76fPA3g8Tw8"
        super().__init__(parent, "Feedback", url)

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