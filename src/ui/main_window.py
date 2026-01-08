import sys
import os
import json
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QSplitter, 
    QTabWidget, QCheckBox, QPushButton, QFileDialog, QMessageBox, QFrame, QLineEdit, QApplication, QListWidgetItem, QListWidget, QSizePolicy, QGridLayout, QStyle, QProgressDialog, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QThread, pyqtSignal, QSize, QSettings
from PyQt6.QtGui import QIcon, QPixmap

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from src.constants import DB_FILE, JSON_FILE, PROF_MAP, PROF_SHORT_MAP, resource_path, ICON_DIR, ICON_SIZE, PIXMAP_CACHE, PROF_PRIMARY_ATTR, ATTR_MAP, PROF_ATTRS
from src.database import SkillRepository
from src.engine import MechanicsEngine, SynergyEngine
from src.models import Build, Skill
from src.utils import GuildWarsTemplateDecoder, GuildWarsTemplateEncoder
from src.core.mechanics import get_primary_bonus_value
from src.ui.components import SkillSlot, SkillInfoPanel, SkillLibraryWidget, BuildPreviewWidget
from src.ui.attribute_editor import AttributeEditor
from src.ui.character_panel import CharacterPanel, WeaponsPanel, WEAPONS
from src.ui.tutorial import TutorialOverlay, TutorialManager
from src.ui.dialogs import TeamManagerDialog, LocationManagerDialog, BuildUniquenessDialog, ProfessionSelectionDialog, TeamManagerWidget
from src.ui.settings_tab import SettingsTab
from src.ui.theme import update_theme, get_color
from src.updater import UpdateChecker, UpdateDownloader, install_and_restart

class FilterWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, db_path, engine, filters):
        super().__init__()
        self.db_path = db_path
        self.engine = engine
        self.filters = filters

    def run(self):
        try:
            # SQLite connections cannot be shared across threads.
            local_repo = SkillRepository(self.db_path)
            
            prof = self.filters['prof']
            cat = self.filters['cat']
            team = self.filters['team']
            search_text = self.filters['search_text']
            search_desc_mode = self.filters.get('search_desc_mode', False)
            # Ensure is_pvp is strictly a boolean
            is_pvp = bool(self.filters['is_pvp'])
            is_pve_only = bool(self.filters['is_pve_only'])
            is_elites_only = self.filters['is_elites_only']
            is_no_elites = self.filters['is_no_elites']
            is_pre_only = self.filters['is_pre_only']
            allowed_campaigns = self.filters.get('allowed_campaigns')

            # 1. Get initial list of IDs based on team/category
            if cat == "All" and team == "All":
                valid_ids = local_repo.get_all_skill_ids(is_pvp=is_pvp)
            else:
                valid_ids = self.engine.filter_skills(prof, cat, team) 
            
            filtered_skills = []
            target_prof_id = -1
            if prof != "All":
                try:
                    target_prof_id = int(prof)
                except:
                    pass

            target_attr_id = self.filters.get('attr_id', -1)

            for sid in valid_ids:
                if sid == 0: continue
                
                if self.isInterruptionRequested():
                    return
                
                # Fetch skill using the correct mode
                skill = local_repo.get_skill(sid, is_pvp=is_pvp)
                
                if skill:
                    # --- STRICT MODE CHECKS ---
                    if is_pvp:
                        # In PvP Mode: Hide PvE-Only skills
                        if skill.is_pve_only:
                            continue
                    else:
                        # In PvE Mode: Hide explicit PvP skills
                        # (This catches skills named "Abc (PvP)" which often slip into the main table)
                        if "(PvP)" in skill.name:
                            continue

                    # --- PvE ONLY ---
                    if is_pve_only and not skill.is_pve_only:
                        continue

                    # --- SEARCH ---
                    if search_text:
                        if search_desc_mode:
                            if not skill.description or search_text not in skill.description.lower():
                                continue
                        else:
                            if search_text not in skill.name.lower():
                                continue
                        
                    # --- ELITE FILTERS ---
                    if is_elites_only and not skill.is_elite:
                        continue
                    if is_no_elites and skill.is_elite:
                        continue
                        
                    # --- PRE-SEARING ---
                    if is_pre_only and not skill.in_pre:
                        continue
                        
                    # --- CAMPAIGN FILTER ---
                    if allowed_campaigns is not None:
                        if skill.campaign != 0 and skill.campaign not in allowed_campaigns:
                            continue
                        
                    # --- PROFESSION ---
                    if target_prof_id != -1:
                        if skill.profession != target_prof_id:
                            continue

                    # --- ATTRIBUTE ---
                    if target_attr_id != -1:
                        if skill.attribute != target_attr_id:
                            continue
                        
                    filtered_skills.append(skill)

            # Sort by profession (ascending), then by attribute (ascending), then by name (ascending)
            filtered_skills.sort(key=lambda x: (x.profession, x.attribute, x.name))

            self.finished.emit(filtered_skills)
        except Exception as e:
            print(f"FilterWorker Error: {e}")
        finally:
            if 'local_repo' in locals():
                local_repo.conn.close()

class SynergyWorker(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, engine, active_skill_ids, prof_id=0, mode="legacy", debug=False, is_pre=False, allowed_campaigns=None, is_pvp=False, attr_dist=None, total_energy=30):
        super().__init__()
        self.engine = engine
        self.active_skill_ids = active_skill_ids
        self.prof_id = prof_id 
        self.mode = mode
        self.debug = debug
        self.is_pre = is_pre
        self.allowed_campaigns = allowed_campaigns
        self.is_pvp = is_pvp
        self.attr_dist = attr_dist or {}
        self.total_energy = total_energy
        self._is_interrupted = False

    def run(self):
        try:
            # UNIFIED PIPELINE: Always use the Neural/Hybrid Engine
            results = self.engine.get_suggestions(
                self.active_skill_ids, 
                limit=100, 
                mode=self.mode, 
                is_pre=self.is_pre,
                allowed_campaigns=self.allowed_campaigns,
                is_pvp=self.is_pvp,
                primary_prof_id=self.prof_id,
                attr_dist=self.attr_dist,
                max_energy=self.total_energy
            )
            
            if not self.isInterruptionRequested():
                self.results_ready.emit(results)
        except Exception as e:
            print(f"Worker Error: {e}")

    def stop(self):
        self.requestInterruption()
        self.quit()
        self.wait(500)

class MainWindow(QMainWindow):
    def __init__(self, engine=None):
        super().__init__()
        self.setWindowTitle("B.O.O.K.A.H. (Build Optimization & Organization for Knowledge-Agnostic Hominids)")
        self.resize(1400, 800)
        
        # Set Window Icon
        icon_path = resource_path(os.path.join("icons", "bookah_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Load Data
        self.repo = SkillRepository(DB_FILE)
        
        if engine:
            self.engine = engine
        else:
            # Fallback if run directly (shouldn't happen via bookah.py)
            from src.engine import SynergyEngine
            self.engine = SynergyEngine(JSON_FILE, DB_FILE)
            
        # self.smart_engine removed - functionality merged into SynergyEngine
        
        # State
        self.bar_skills = [None] * 8 
        self.suggestion_offset = 0
        self.current_suggestions = [] 
        self.all_icon_widgets = []
        self.skill_widgets = {} # {skill_id: DraggableSkillIcon}
        self.is_swapped = False 
        self.template_path = ""
        self.current_selected_skill_id = None
        self.team_synergy_skills = [] # Skills from loaded team for Smart Mode
        self.current_primary_prof = 0
        self.current_secondary_prof = 0
        self._last_attr_state = None
        self.settings = QSettings("Bookah", "Builder")
        self.loading_from_selection = False 
        self.dirty_build_ids = set() 
        self.active_edit_build = None
        self.build_on_bar = None
        
        self.current_bonuses = {}
        self.current_global_effects = {}
        
        self.pending_update = None # Store update info if window is not visible

        self.setAcceptDrops(True) # Enable Drag & Drop
        # Debounce timer for search/filter inputs
        self.filter_debounce_timer = QTimer()
        self.filter_debounce_timer.setSingleShot(True)
        self.filter_debounce_timer.timeout.connect(self._run_filter)
        
        self.tutorial_manager = TutorialManager(self)
        self.init_ui()
        
        # Apply initial theme
        initial_theme = self.settings_tab.settings.value("theme", "Auto")
        self.apply_theme(initial_theme)
        
        self.apply_filters() 

        # Auto-Update Check
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.error.connect(lambda e: print(f"Update Check Error: {e}"))
        
        self._update_check_triggered = False

    def on_update_available(self, new_version, download_url, release_notes=""):
        self._update_dialog_shown = True
        if self.isVisible():
            self._show_update_dialog(new_version, download_url, release_notes)
        else:
            self.pending_update = (new_version, download_url, release_notes)

    def showEvent(self, event):
        super().showEvent(event)
        
        # Trigger update check once when window is shown
        if not self._update_check_triggered:
            self._update_check_triggered = True
            
            # Chain: Update Check -> (Update Dialog) -> Tutorial
            def on_check_finished():
                # If update checker didn't trigger a dialog, show tutorial now
                if not getattr(self, '_update_dialog_shown', False):
                    self.tutorial_manager.show_if_needed()

            # Ensure UpdateChecker emits finished
            self.update_checker.finished.connect(on_check_finished)
            QTimer.singleShot(1000, self.update_checker.check)

        if self.pending_update:
            new_version, download_url, release_notes = self.pending_update
            self.pending_update = None
            QTimer.singleShot(500, lambda: self._show_update_dialog(new_version, download_url, release_notes))

    def _show_update_dialog(self, new_version, download_url, release_notes=""):
        msg = f"A new version ({new_version}) is available.\n\n"
        if release_notes:
            msg += f"Updates:\n{release_notes}\n\n"
        msg += "Do you want to download and update now?"
        
        reply = QMessageBox.question(
            self, 
            "Update Available", 
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_update(download_url)
        else:
            # If they chose No, continue to tutorial
            self.tutorial_manager.show_if_needed()

    def start_update(self, url):
        self.progress_dlg = QProgressDialog("Downloading Update...", "Cancel", 0, 100, self)
        self.progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dlg.setAutoClose(False)
        self.progress_dlg.setAutoReset(False)
        self.progress_dlg.show()

        self.downloader = UpdateDownloader(url)
        self.downloader.progress.connect(self.on_update_progress)
        self.downloader.finished.connect(self.on_update_downloaded)
        self.downloader.error.connect(self.on_update_error)
        
        self.progress_dlg.canceled.connect(self.downloader.terminate)
        self.downloader.start()

    def on_update_progress(self, percent):
        self.progress_dlg.setValue(percent)

    def on_update_downloaded(self, zip_path):
        self.progress_dlg.setValue(100)
        self.progress_dlg.setLabelText("Installing... App will restart.")
        
        # Give UI a moment to update
        QTimer.singleShot(500, lambda: install_and_restart(zip_path))

    def on_update_error(self, message):
        self.progress_dlg.close()
        QMessageBox.critical(self, "Update Failed", f"An error occurred:\n{message}")

    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.builder_tab = QWidget()
        self.tabs.addTab(self.builder_tab, "Builder")
        self.init_builder_ui(self.builder_tab)

        self.map_tab = QWidget()
        self.tabs.addTab(self.map_tab, "Synergy Map")
        self.init_map_ui(self.map_tab)

        self.settings_tab = SettingsTab()
        self.settings_tab.theme_changed.connect(self.apply_theme)
        self.settings_tab.campaigns_changed.connect(self.on_campaigns_changed)
        self.settings_tab.tutorial_requested.connect(self.tutorial_manager.start)
        self.tabs.addTab(self.settings_tab, "Settings")

    def on_campaigns_changed(self, campaigns):
        # Refresh both UI list and AI suggestions
        self.apply_filters()
        self.update_suggestions()

    def init_map_ui(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        if HAS_WEBENGINE:
            try:
                view = QWebEngineView()
                file_path = resource_path("synergy_map.html")
                view.load(QUrl.fromLocalFile(file_path))
                layout.addWidget(view)
            except Exception as e:
                layout.addWidget(QLabel(f"Error loading map: {e}"))
        else:
            layout.addWidget(QLabel("PyQt6-WebEngine is not installed."))

    def apply_theme(self, mode):
        # Update Global Theme State & Palette
        palette = update_theme(mode)
        app = QApplication.instance()
        app.setPalette(palette)
        
        # Enforce global tooltip style on the application instance
        # This fixes the "black box" issue by ensuring high-contrast colors and no transparency conflicts
        app.setStyleSheet(f"""
            QToolTip {{ 
                background-color: {get_color('tooltip_bg')}; 
                color: {get_color('tooltip_text')}; 
                border: 1px solid {get_color('border')}; 
                padding: 4px;
            }}
        """)
        
        # Propagate to Children
        self.refresh_theme()
        
        if hasattr(self, 'library_widget'): self.library_widget.refresh_theme()
        if hasattr(self, 'info_panel'): self.info_panel.refresh_theme()
        if hasattr(self, 'attr_editor'): self.attr_editor.refresh_theme()
        if hasattr(self, 'character_panel'): self.character_panel.refresh_theme()
        if hasattr(self, 'weapons_panel'): self.weapons_panel.refresh_theme()
        if hasattr(self, 'settings_tab'): self.settings_tab.refresh_theme()
        
        # Refresh slots
        if hasattr(self, 'slots'):
            for slot in self.slots:
                slot.refresh_theme()
                
        # Force a repaint of the window to apply palette changes
        self.update()

    def refresh_theme(self):
        # Update stylesheets that were hardcoded
        self.setStyleSheet(f"QMainWindow {{ background-color: {get_color('bg_secondary')}; }}")
        
        # Bar Container
        if hasattr(self, 'bar_container'):
            self.bar_container.setStyleSheet(f"background-color: {get_color('bg_tertiary')}; border-top: 1px solid {get_color('border')};")
            
        # Code Box
        if hasattr(self, 'edit_code'):
            self.edit_code.setStyleSheet(f"background-color: {get_color('input_bg')}; color: {get_color('input_text')}; font-weight: bold; border: 1px solid {get_color('border')};")
            
        # Buttons
        btn_style = f"""
            QPushButton {{ background-color: {get_color('btn_bg')}; color: {get_color('btn_text')}; border-radius: 4px; font-size: 10px; }}
            QPushButton:hover {{ background-color: {get_color('btn_bg_hover')}; }}
        """
        
        cycle_style = f"""
            QPushButton {{ background-color: {get_color('btn_bg')}; color: {get_color('btn_text')}; border-radius: 4px; font-size: 10px; }}
            QPushButton:hover {{ background-color: {get_color('btn_bg_hover')}; }}
        """
        
        if hasattr(self, 'btn_cycle'): self.btn_cycle.setStyleSheet(cycle_style)
        if hasattr(self, 'btn_select_zone'): 
            # Only if not active? Actually active style overrides this.
            # We can leave specialized buttons alone if they have dynamic styles
            pass
            
        if hasattr(self, 'btn_reset'):
            self.btn_reset.setStyleSheet(f"background-color: {get_color('bg_hover')}; color: {get_color('text_warning')}; border-radius: 4px;")

        if hasattr(self, 'btn_prof_select'):
            self.btn_prof_select.setStyleSheet(f"color: {get_color('text_tertiary')}; font-weight: bold; background: transparent; border: 1px solid {get_color('border')}; border-radius: 4px; padding: 2px 5px;")

        if hasattr(self, 'check_smart_mode'):
            self.check_smart_mode.setStyleSheet(f"color: {get_color('text_link')}; font-weight: bold;")

    def update_team_dropdown(self):
        selected_cat = self.combo_cat.currentText()
        current_team = self.combo_team.currentText()
        
        valid_teams = set()
        if selected_cat == "All":
            valid_teams = self.engine.teams
        else:
            for b in self.engine.builds:
                if b.category == selected_cat:
                    valid_teams.add(b.team)
        
        self.combo_team.blockSignals(True) 
        self.combo_team.clear()
        self.combo_team.addItem("All")
        
        # Priority sort: Solo first, then others
        if "Solo" in valid_teams:
            self.combo_team.addItem("Solo")
            others = sorted([t for t in valid_teams if t != "Solo"])
        else:
            others = sorted(list(valid_teams))
        
        self.combo_team.addItems(others)
        
        index = self.combo_team.findText(current_team)
        if index != -1:
            self.combo_team.setCurrentIndex(index)
        else:
            self.combo_team.setCurrentIndex(0) # Default to "All"
            
        self.combo_team.blockSignals(False)
        self.apply_filters()
        
        # Visibility Update for Build Search
        show_search = (selected_cat != "All")
        self.edit_build_search.setVisible(show_search)

    def on_team_changed(self, text):
        is_team = (text != "All" and text != "Solo")
        show_summary = (text != "All")
        
        if hasattr(self, 'btn_team_summary'):
            self.btn_team_summary.setVisible(show_summary)
        if hasattr(self, 'btn_duplicate_team'):
            self.btn_duplicate_team.setVisible(is_team)
            
        # Update search visibility: Show if Team!=All OR Cat!=All
        cat = self.combo_cat.currentText()
        show_search = (text != "All") or (cat != "All")
        if hasattr(self, 'edit_build_search'):
            self.edit_build_search.setVisible(show_search)
            
        # Auto-switch to Team View if a specific team is selected
        if is_team:
            self.btn_team_view.setChecked(True)
            
        self.apply_filters()

    def duplicate_current_team(self):
        current_team = self.combo_team.currentText()
        if current_team == "All" or current_team == "Solo": return
        
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "Duplicate Team", "Enter name for the new team:", text=f"Copy of {current_team}")
        
        if not ok or not new_name: return
        if new_name in self.engine.teams:
            QMessageBox.warning(self, "Error", f"Team '{new_name}' already exists!")
            return
            
        # Clone builds
        source_builds = [b for b in self.engine.builds if b.team == current_team]
        self.engine.teams.add(new_name)
        
        for b in source_builds:
            new_build = Build(
                code=b.code,
                primary_prof=b.primary_prof,
                secondary_prof=b.secondary_prof,
                skill_ids=list(b.skill_ids), # Clone list
                category="User Created",
                team=new_name,
                name=b.name,
                attributes=list(b.attributes) if b.attributes else [] # Clone attributes
            )
            new_build.is_user_build = True
            self.engine.builds.append(new_build)
            
        self.engine.save_user_builds()
        
        # Manual Refresh of Dropdown
        self.combo_team.blockSignals(True)
        self.combo_team.clear()
        self.combo_team.addItem("All")
        
        all_teams = self.engine.teams
        if "Solo" in all_teams:
            self.combo_team.addItem("Solo")
            others = sorted([t for t in all_teams if t != "Solo"])
        else:
            others = sorted(list(all_teams))
        self.combo_team.addItems(others)
        
        # Select New Team
        idx = self.combo_team.findText(new_name)
        if idx != -1: self.combo_team.setCurrentIndex(idx)
        self.combo_team.blockSignals(False)
        
        # Trigger update
        self.on_team_changed(new_name)
        QMessageBox.information(self, "Success", f"Team duplicated as '{new_name}'.")

    def init_builder_ui(self, parent_widget):
        main_layout = QVBoxLayout(parent_widget)

        # --- Top Filter Grid ---
        top_grid = QGridLayout()
        
        # Helper to create tightly grouped label + widget
        def grouped_widget(label_text, widget):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            layout.addWidget(QLabel(label_text))
            layout.addWidget(widget)
            layout.addStretch(1)
            return container

        # Col 0-1: Profession
        self.combo_prof = QComboBox()
        self.combo_prof.addItem("All", "All")
        for pid in sorted(PROF_MAP.keys()):
            self.combo_prof.addItem(PROF_MAP[pid], pid)
        self.combo_prof.currentTextChanged.connect(self.apply_filters)
        top_grid.addWidget(grouped_widget("Profession:", self.combo_prof), 0, 0, 1, 2)
        
        # Row 1: Attribute (Under Profession)
        self.combo_attr = QComboBox()
        self.combo_attr.setFixedWidth(150)
        self.combo_attr.addItem("All", -1)
        self.combo_attr.currentTextChanged.connect(self.apply_filters)
        self.combo_prof.currentIndexChanged.connect(self.update_attribute_dropdown)
        top_grid.addWidget(grouped_widget("Attribute:", self.combo_attr), 1, 0, 1, 2)
        
        # Col 2-3: Category
        self.combo_cat = QComboBox()
        self.combo_cat.addItem("All")
        self.combo_cat.addItems(sorted(list(self.engine.categories)))
        self.combo_cat.currentTextChanged.connect(self.update_team_dropdown)
        top_grid.addWidget(grouped_widget("Category:", self.combo_cat), 0, 2, 1, 2)
        
        # Col 4-5: Team
        self.combo_team = QComboBox()
        self.combo_team.addItem("All")
        all_teams = self.engine.teams
        if "Solo" in all_teams:
            self.combo_team.addItem("Solo")
            others = sorted([t for t in all_teams if t != "Solo"])
        else:
            others = sorted(list(all_teams))
        self.combo_team.addItems(others)
        self.combo_team.currentTextChanged.connect(self.on_team_changed)
        self.combo_team.setCurrentIndex(0) 
        top_grid.addWidget(grouped_widget("Team:", self.combo_team), 0, 4, 1, 2)
        
        # Col 6: Manage Teams
        self.btn_manage_teams = QPushButton("Manage Teams")
        self.btn_manage_teams.setCheckable(True)
        self.btn_manage_teams.setToolTip("Open Team Manager Pane")
        self.btn_manage_teams.clicked.connect(self.toggle_team_manager_view)
        top_grid.addWidget(self.btn_manage_teams, 0, 6)
        
        # Summary & Duplicate Buttons (Row 1)
        btn_action_layout = QHBoxLayout()
        btn_action_layout.setContentsMargins(0, 0, 0, 0)
        btn_action_layout.setSpacing(2)
        
        self.btn_team_summary = QPushButton("Summary")
        self.btn_team_summary.setVisible(False)
        self.btn_team_summary.clicked.connect(self.open_team_summary)
        btn_action_layout.addWidget(self.btn_team_summary)
        
        self.btn_duplicate_team = QPushButton("Duplicate")
        self.btn_duplicate_team.setToolTip("Duplicate current team to edit")
        self.btn_duplicate_team.setVisible(False)
        self.btn_duplicate_team.clicked.connect(self.duplicate_current_team)
        btn_action_layout.addWidget(self.btn_duplicate_team)
        
        top_grid.addLayout(btn_action_layout, 1, 6)

        # Build Search (Row 1, Col 4-5) - Left of Summary
        self.edit_build_search = QLineEdit()
        self.edit_build_search.setPlaceholderText("Search for builds")
        self.edit_build_search.setVisible(False)
        self.edit_build_search.textChanged.connect(self.apply_filters)
        top_grid.addWidget(self.edit_build_search, 1, 4, 1, 2)
        
        # Col 7-9: Checkbox Group
        self.check_pvp = QCheckBox("PvP")
        self.check_pvp.toggled.connect(self.on_pvp_toggled)
        
        self.check_pve_only = QCheckBox("PvE Only")
        self.check_pve_only.toggled.connect(self.apply_filters)

        self.check_pre = QCheckBox("Pre")
        self.check_pre.toggled.connect(self.apply_filters)
        self.check_pre.toggled.connect(self.update_suggestions)

        self.check_elites_only = QCheckBox("Elites")
        self.check_no_elites = QCheckBox("No Elites")
        self.check_elites_only.toggled.connect(self.toggle_elites)
        self.check_no_elites.toggled.connect(self.toggle_no_elites)

        # Create a horizontal layout for the three groups
        cb_hbox = QHBoxLayout()
        cb_hbox.setContentsMargins(0, 0, 0, 0)
        cb_hbox.setSpacing(10)

        # Group 1: PvP & PvE Only
        vbox_pvp = QVBoxLayout()
        vbox_pvp.addWidget(self.check_pvp)
        vbox_pvp.addWidget(self.check_pve_only)
        cb_hbox.addLayout(vbox_pvp)

        # Group 2: Pre
        vbox_pve = QVBoxLayout()
        vbox_pve.addWidget(self.check_pre)
        vbox_pve.addStretch()
        cb_hbox.addLayout(vbox_pve)
        
        cb_hbox.addSpacing(10) 

        # Group 3: Elites
        vbox_elites = QVBoxLayout()
        vbox_elites.addWidget(self.check_elites_only)
        vbox_elites.addWidget(self.check_no_elites)
        cb_hbox.addLayout(vbox_elites)

        top_grid.addLayout(cb_hbox, 0, 7, 2, 3)

        # Col 10-11: Search
        self.edit_search = QLineEdit()
        self.edit_search.setFixedWidth(200)
        self.edit_search.setPlaceholderText("Search skills...")
        self.edit_search.textChanged.connect(self.apply_filters)
        
        search_vbox = QVBoxLayout()
        search_vbox.setSpacing(2)
        search_vbox.addWidget(grouped_widget("Search:", self.edit_search))
        
        # Align "Description" checkbox under the line edit
        desc_hbox = QHBoxLayout()
        desc_hbox.setContentsMargins(0, 0, 0, 0)
        # 45px is approximately the width of "Search:" label + spacing
        desc_hbox.addSpacing(45) 
        self.check_search_desc = QCheckBox("Description")
        self.check_search_desc.setStyleSheet(f"font-size: 10px; color: {get_color('text_primary')};")
        self.check_search_desc.toggled.connect(self.apply_filters)
        desc_hbox.addWidget(self.check_search_desc)
        desc_hbox.addStretch()
        
        search_vbox.addLayout(desc_hbox)
        
        top_grid.addLayout(search_vbox, 0, 10, 2, 2)
        
        # --- Row 1: Export Controls + Maximize Button ---
        
        # --- Row 1: Export Controls + Maximize Button ---
        
        # Button Row: Magnifier + Character Toggle
        btn_row_layout = QHBoxLayout()
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(5)
        
        self.btn_char_view = QPushButton("Character")
        self.btn_char_view.setFixedSize(70, 24)
        self.btn_char_view.setCheckable(True)
        self.btn_char_view.setToolTip("Toggle Character View")
        self.btn_char_view.setStyleSheet("""
            QPushButton { 
                border: 1px solid transparent; 
                background: transparent; 
                font-size: 11px; 
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:checked {
                color: #00FF00;
                border: 2px solid #00FF00;
                background-color: #2a2a2a;
            }
            QPushButton:hover {
                background-color: #333;
            }
        """)
        self.btn_char_view.toggled.connect(self.toggle_character_view)
        btn_row_layout.addWidget(self.btn_char_view)

        self.btn_team_view = QPushButton("Teams")
        self.btn_team_view.setFixedSize(60, 24)
        self.btn_team_view.setCheckable(True)
        self.btn_team_view.setToolTip("Toggle Team View")
        self.btn_team_view.setStyleSheet("""
            QPushButton { 
                border: 1px solid transparent; 
                background: transparent; 
                font-size: 11px; 
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:checked {
                color: #00AAFF;
                border: 2px solid #00AAFF;
                background-color: #2a2a2a;
            }
            QPushButton:hover {
                background-color: #333;
            }
        """)
        self.btn_team_view.toggled.connect(self.toggle_team_view)
        btn_row_layout.addWidget(self.btn_team_view)

        self.btn_max_icons = QPushButton("🔍")
        self.btn_max_icons.setFixedSize(24, 24)
        self.btn_max_icons.setCheckable(True)
        self.btn_max_icons.setToolTip("Toggle Large Icons")
        self.btn_max_icons.setStyleSheet("""
            QPushButton { 
                border: 1px solid transparent; 
                background: transparent; 
                font-size: 14px; 
                border-radius: 4px;
            }
            QPushButton:checked {
                color: #00AAFF;
                border: 2px solid #00AAFF;
                background-color: #2a2a2a;
            }
            QPushButton:hover {
                background-color: #333;
            }
        """)
        self.btn_max_icons.clicked.connect(self.toggle_icon_size)
        btn_row_layout.addWidget(self.btn_max_icons)
        
        btn_row_layout.addStretch()
        
        top_grid.addLayout(btn_row_layout, 1, 2, 1, 2) # Span 2 cols (Next to Attribute)

        # Add grid to main layout
        main_layout.addLayout(top_grid)
        
        # --- 2. Center Stack (Skills vs Character vs Teams) ---
        self.center_stack = QStackedWidget()
        
        # Page 0: Sub-Splitter: Library + Info
        self.sub_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.library_widget = SkillLibraryWidget(parent=None, repo=self.repo, engine=self.engine)
        self.library_widget.skill_clicked.connect(self.handle_skill_id_clicked)
        self.library_widget.skill_double_clicked.connect(lambda sid: self.handle_skill_equipped_auto(sid))
        # Note: builds_reordered is now relevant for team_view_widget mostly, but left here for consistency
        self.sub_splitter.addWidget(self.library_widget)
        
        self.info_panel = SkillInfoPanel()
        self.sub_splitter.addWidget(self.info_panel)
        
        # Set stretch for sub-splitter
        self.sub_splitter.setStretchFactor(0, 1)
        self.sub_splitter.setStretchFactor(1, 0)
        self.sub_splitter.setSizes([800, 255])
        
        self.center_stack.addWidget(self.sub_splitter)
        
        # Page 1: Character Panel
        self.character_panel = CharacterPanel()
        self.character_panel.stats_changed.connect(self.on_stats_changed)
        self.center_stack.addWidget(self.character_panel)

        # Page 2: Team View Panel
        self.team_view_widget = SkillLibraryWidget(repo=self.repo, engine=self.engine)
        self.team_view_widget.builds_reordered.connect(self.handle_builds_reordered)
        self.team_view_widget.itemSelectionChanged.connect(self.on_team_list_selection_changed)
        self.center_stack.addWidget(self.team_view_widget)
        
        # Page 3: Team Manager Panel
        self.team_manager_widget = TeamManagerWidget(self, self.engine)
        self.center_stack.addWidget(self.team_manager_widget)
        
        # Master Splitter: Stack (Left) + Attribute Editor (Right)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.center_stack)
        
        self.right_stack = QStackedWidget()
        self.attr_editor = AttributeEditor()
        self.attr_editor.setMinimumWidth(100)
        self.attr_editor.attributes_changed.connect(self.on_attributes_changed)
        self.right_stack.addWidget(self.attr_editor)
        
        self.weapons_panel = WeaponsPanel(parent_panel=self.character_panel)
        self.right_stack.addWidget(self.weapons_panel)
        
        self.splitter.addWidget(self.right_stack)
        
        # Master Splitter Stretch
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([980, 220])
        
        main_layout.addWidget(self.splitter, stretch=1)

        # --- 3. Build Bar (Updated Layout) ---
        self.bar_container = QFrame()
        self.bar_container.setFixedHeight(140) # Increased height slightly to fit checkbox
        self.bar_container.setStyleSheet(f"background-color: {get_color('bg_primary')}; border-top: 1px solid {get_color('border')};")
        container_layout = QHBoxLayout(self.bar_container)

        # --- NEW: Cycle & Debug Column ---
        cycle_container = QWidget()
        cycle_layout = QVBoxLayout(cycle_container)
        cycle_layout.setContentsMargins(0, 5, 0, 5)
        cycle_layout.setSpacing(5)

        self.btn_select_zone = QPushButton("Select Zone")
        self.btn_select_zone.setFixedSize(90, 50)
        self.btn_select_zone.setStyleSheet("""
            QPushButton { background-color: #444; color: #888; border-radius: 4px; font-weight: bold; font-size: 10px; }
        """)
        # self.btn_select_zone.clicked.connect(self.open_location_manager) # Disabled
        self.btn_select_zone.setVisible(False)
        cycle_layout.addWidget(self.btn_select_zone)

        self.btn_load_team_synergy = QPushButton("Load Teambuild\nto Bar")
        self.btn_load_team_synergy.setFixedSize(90, 50)
        self.btn_load_team_synergy.setStyleSheet("""
            QPushButton { background-color: #224466; color: white; border-radius: 4px; font-weight: bold; font-size: 10px; }
            QPushButton:hover { background-color: #335577; }
        """)
        self.btn_load_team_synergy.setVisible(False)
        self.btn_load_team_synergy.clicked.connect(self.open_team_manager_for_synergy)
        cycle_layout.addWidget(self.btn_load_team_synergy)
        
        container_layout.addWidget(cycle_container)

        # --- Skill Bar Area (Vertical wrapper for Bar + Cycle Button) ---
        self.bar_area = QWidget()
        bar_area_layout = QVBoxLayout(self.bar_area)
        bar_area_layout.setContentsMargins(0, 0, 0, 0)
        bar_area_layout.setSpacing(5)

        bar_layout = QHBoxLayout()
        bar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.slots = []
        for i in range(8):
            slot = SkillSlot(i)
            slot.skill_equipped.connect(self.handle_skill_equipped)
            slot.skill_removed.connect(self.handle_skill_removed)
            slot.skill_swapped.connect(self.handle_skill_swapped)
            slot.clicked.connect(self.handle_skill_id_clicked)
            bar_layout.addWidget(slot)
            self.slots.append(slot)
            
        bar_area_layout.addLayout(bar_layout)

        # Loading Indicator (Left Aligned, fixed height to prevent jumping)
        loading_hbox = QHBoxLayout()
        loading_hbox.setContentsMargins(10, 0, 0, 0) # Small indent from the edge
        self.lbl_bar_loading = QLabel("Loading...")
        self.lbl_bar_loading.setStyleSheet("color: #00AAFF; font-weight: bold; font-size: 10px;")
        
        # Prevent layout from shifting when label is hidden
        sp = self.lbl_bar_loading.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.lbl_bar_loading.setSizePolicy(sp)
        
        self.lbl_bar_loading.setVisible(False)
        loading_hbox.addWidget(self.lbl_bar_loading)
        loading_hbox.addStretch()
        bar_area_layout.addLayout(loading_hbox)

        # Button row (Cycle + Unique Check)
        btn_hbox = QHBoxLayout()
        btn_hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_hbox.setSpacing(10)

        self.btn_cycle = QPushButton("Cycle Suggestions")
        self.btn_cycle.setFixedSize(150, 24)
        self.btn_cycle.setStyleSheet("""
            QPushButton { background-color: #444; color: white; border-radius: 4px; font-size: 10px; }
            QPushButton:hover { background-color: #555; }
        """)
        self.btn_cycle.clicked.connect(self.cycle_suggestions)
        btn_hbox.addWidget(self.btn_cycle)

        self.btn_check_unique = QPushButton("Is this unique?")
        self.btn_check_unique.setFixedSize(150, 24)
        self.btn_check_unique.setStyleSheet("""
            QPushButton { background-color: #6644AA; color: white; border-radius: 4px; font-size: 10px; font-weight: bold;}
            QPushButton:hover { background-color: #7755BB; }
        """)
        self.btn_check_unique.setVisible(False)
        self.btn_check_unique.clicked.connect(self.check_build_uniqueness)
        btn_hbox.addWidget(self.btn_check_unique)

        bar_area_layout.addLayout(btn_hbox)

        container_layout.addStretch(1)
        container_layout.addWidget(self.bar_area)
        container_layout.addSpacing(20) 
        
        # --- Control Layout (Right Side) ---
        control_layout = QVBoxLayout()
        
        self.check_show_others = QCheckBox("Show Other\nProfessions")
        self.check_show_others.toggled.connect(self.update_suggestions)
        control_layout.addWidget(self.check_show_others)

        self.check_lock_suggestions = QCheckBox("Freeze Suggestions")
        self.check_lock_suggestions.toggled.connect(self.update_suggestions)
        control_layout.addWidget(self.check_lock_suggestions)
        
        self.check_smart_mode = QCheckBox("Smart Mode")
        self.check_smart_mode.setStyleSheet("color: #FFD700; font-weight: bold;")
        self.check_smart_mode.toggled.connect(self.on_smart_mode_toggled)
        control_layout.addWidget(self.check_smart_mode)

        container_layout.addLayout(control_layout)
        container_layout.addStretch(1)

        # --- Build Code Box (Rightmost) ---
        self.code_box = QFrame()
        self.code_box.setFixedWidth(250)
        code_layout = QVBoxLayout(self.code_box)
        
        header_layout = QHBoxLayout()
        self.btn_load_file = QPushButton("Builds")
        self.btn_load_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_file.setToolTip("Click to load a build template file")
        self.btn_load_file.clicked.connect(self.load_build_from_file)
        self.btn_load_file.setStyleSheet(f"color: {get_color('text_primary')}; font-weight: bold; background: transparent; border: 1px solid {get_color('border')}; border-radius: 4px; padding: 2px 5px;")
        header_layout.addWidget(self.btn_load_file)
        
        self.btn_prof_select = QPushButton("Prof: X/X")
        self.btn_prof_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prof_select.setToolTip("Click to select professions manually")
        self.btn_prof_select.clicked.connect(self.open_prof_selection)
        self.btn_prof_select.setStyleSheet(f"color: {get_color('text_primary')}; font-weight: bold; background: transparent; border: 1px solid {get_color('border')}; border-radius: 4px; padding: 2px 5px;")
        header_layout.addWidget(self.btn_prof_select)
        
        self.btn_swap_prof = QPushButton("Swap")
        self.btn_swap_prof.setFixedSize(40, 20)
        self.btn_swap_prof.setStyleSheet("font-size: 10px; padding: 0px;")
        self.btn_swap_prof.clicked.connect(self.swap_professions)
        header_layout.addWidget(self.btn_swap_prof)
        
        header_layout.addStretch()
        code_layout.addLayout(header_layout)
        
        self.edit_code = QLineEdit()
        self.edit_code.setPlaceholderText("Paste build code here...")
        self.edit_code.setStyleSheet(f"background-color: {get_color('input_bg')}; color: {get_color('input_text')}; font-weight: bold;")
        code_layout.addWidget(self.edit_code)

        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load")
        self.btn_load.clicked.connect(self.load_code)
        btn_layout.addWidget(self.btn_load)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.clicked.connect(self.copy_code)
        btn_layout.addWidget(self.btn_copy)
        
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setStyleSheet("background-color: #552222;")
        self.btn_reset.clicked.connect(self.reset_build)
        btn_layout.addWidget(self.btn_reset)
        
        code_layout.addLayout(btn_layout)
        container_layout.addWidget(self.code_box)
        main_layout.addWidget(self.bar_container)

    def on_smart_mode_toggled(self, checked):
        if hasattr(self, 'btn_load_team_synergy'):
            self.btn_load_team_synergy.setVisible(checked)
        # self.btn_select_zone.setVisible(checked) # Feature disabled
        self.update_suggestions()

    def open_team_manager_for_synergy(self):
        # Toggle Off if already active
        if self.team_synergy_skills:
            self.reset_team_mode()
            self.update_suggestions()
            return

        # We'll use a modified TeamManagerDialog logic or just a specialized call
        dlg = TeamManagerDialog(self, self.engine, restricted_mode=True)
        # Change button text to indicate synergy mode
        dlg.btn_load.setText("Load Team")
        dlg.btn_load.setToolTip("Load all skills from this team to use as synergy context")
        
        # Override the load_team method logic by reconnecting the button
        def synergy_load():
            item = dlg.list_widget.currentItem()
            if not item: return
            team_name = item.text()
            
            # 1. Load the context (Activates the AI/Visual mode)
            self.load_team_for_synergy(team_name)
            
            # 2. Update the library view (Show the builds in the list)
            index = self.combo_team.findText(team_name)
            if index != -1:
                self.combo_team.setCurrentIndex(index)
                
            dlg.accept()
            
        try:
            dlg.btn_load.clicked.disconnect()
        except:
            pass
        dlg.btn_load.clicked.connect(synergy_load)
        
        dlg.exec()

    def open_location_manager(self):
        # Toggle Off if already active
        if getattr(self, 'active_zone_mode', False):
            self.reset_zone_mode()
            self.update_suggestions()
            return

        dlg = LocationManagerDialog(self, DB_FILE)
        if dlg.exec():
            selected_zone = dlg.get_selected_location()
            if selected_zone:
                self.load_zone_counters(selected_zone)

    def load_zone_counters(self, zone_name):
        print(f"[UI] Loading summary for zone: {zone_name}")
        
        # Mutual Exclusion
        self.reset_team_mode()
        
        # Set Mode Flag
        self.active_zone_mode = True
        
        # 1. Get Summary
        monsters = self.engine.get_zone_summary(zone_name)
        
        # 2. Update Library List
        self.library_widget.update_zone_summary(monsters)
        
        # 3. Update Visuals
        self.btn_select_zone.setText(f"Active Zone:\n{zone_name}")
        self.btn_select_zone.setStyleSheet("QPushButton { background-color: #444; color: white; border: 2px solid #AA00FF; border-radius: 4px; font-weight: bold; font-size: 10px; } QPushButton:hover { background-color: #555; }")
        
        # 4. Clear Bar Suggestions (Agency Mode)
        self.current_suggestions = [] 
        self.display_suggestions()

    def open_team_summary(self):
        team_name = self.combo_team.currentText()
        if team_name == "All": return
        
        # Gather builds for this team
        builds = [b for b in self.engine.builds if b.team == team_name]
        
        if not builds:
            QMessageBox.information(self, "Summary", "No builds found for this team.")
            return
            
        from src.ui.dialogs import TeamSummaryDialog
        dlg = TeamSummaryDialog(team_name, builds, self.repo, self)
        dlg.exec()

    def load_team_for_synergy(self, team_name):
        # Mutual Exclusion
        self.reset_zone_mode()

        print(f"[UI] Activating Team Context: {team_name}")
        self.lbl_bar_loading.setVisible(True)
        QApplication.processEvents()
        
        self.team_synergy_skills = []
        builds = [b for b in self.engine.builds if b.team == team_name]
        
        all_ids = set()
        for b in builds:
            for sid in b.skill_ids:
                if sid != 0:
                    all_ids.add(sid)
        
        self.team_synergy_skills = list(all_ids)
        print(f"[UI] Loaded {len(self.team_synergy_skills)} skills from team '{team_name}' for synergy context.")
        
        # Visual Indication
        self.btn_load_team_synergy.setText(f"Active Team:\n{team_name}")
        self.btn_load_team_synergy.setStyleSheet("QPushButton { background-color: #224466; color: white; border: 2px solid #00FF00; border-radius: 4px; font-weight: bold; font-size: 10px; } QPushButton:hover { background-color: #335577; }")
        
        self.update_suggestions()

    def toggle_team_manager_view(self, checked=None):
        if checked is None:
            checked = self.btn_manage_teams.isChecked()

        if checked:
            self.btn_char_view.blockSignals(True)
            self.btn_char_view.setChecked(False)
            self.btn_char_view.blockSignals(False)
            
            self.btn_team_view.blockSignals(True)
            self.btn_team_view.setChecked(False)
            self.btn_team_view.blockSignals(False)

            self.center_stack.setCurrentWidget(self.team_manager_widget)
            self.right_stack.setCurrentIndex(0) 
        else:
            if not self.btn_char_view.isChecked() and not self.btn_team_view.isChecked():
                self.center_stack.setCurrentIndex(0)



    def on_pvp_toggled(self, checked):
        # Update both engines and refresh
        mode = "pvp" if checked else "pve"
        self.engine.mechanics.set_mode(mode)
        
        # Refresh current info panel if visible
        if self.current_selected_skill_id:
            self.handle_skill_id_clicked(self.current_selected_skill_id)
            
        self.apply_filters()
        self.update_suggestions()
        self.refresh_equipped_skills()

    def import_build_to_db(self):
        code = self.edit_code.text().strip()
        if not code:
            QMessageBox.warning(self, "Import Error", "Please enter or load a build code first.")
            return
            
        decoder = GuildWarsTemplateDecoder(code)
        decoded = decoder.decode()
        
        if not decoded:
            QMessageBox.warning(self, "Import Error", "Invalid Build Code.")
            return
            
        entry = {
            "build_code": code,
            "primary_profession": str(decoded['profession']['primary']),
            "secondary_profession": str(decoded['profession']['secondary']),
            "skill_ids": decoded['skills'],
            "category": "User Imported",
            "team": "User Imported"
        }
        
        try:
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []
                
            if any(d.get('build_code') == code for d in data):
                QMessageBox.information(self, "Import", "This build is already in the database.")
                return
                
            data.append(entry)
            
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
                
            self.engine = SynergyEngine(JSON_FILE, DB_FILE)
            self.apply_filters()
            self.update_team_dropdown() 
            
            QMessageBox.information(self, "Success", "Build successfully imported into the synergy database!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save build: {e}")

    def reset_build(self):
        self.bar_skills = [None] * 8
        self.suggestion_offset = 0
        self.is_swapped = False
        
        self.current_primary_prof = 0
        self.current_secondary_prof = 0
        
        self.reset_zone_mode()
        self.reset_team_mode()
        
        # Clear Stats Panel (Runes, Cons, Weapons)
        if hasattr(self, 'character_panel'):
            self.character_panel.clear_runes()
            self.character_panel.clear_consumables()
        if hasattr(self, 'weapons_panel'):
            # Manually reset active weapon since CharacterPanel.clear_runes doesn't do it
            self.character_panel.active_weapon = None
            for w in self.weapons_panel.weapon_widgets.values():
                w.button.blockSignals(True)
                w.button.setChecked(False)
                w.button.blockSignals(False)
            self.character_panel.update_stats()

        self.btn_team_view.blockSignals(True)
        self.btn_team_view.setChecked(False)
        self.btn_team_view.blockSignals(False)
        self.center_stack.setCurrentIndex(0) # Back to Library
        
        self.attr_editor.set_read_only(False) # Ensure editable on reset
        
        self.combo_prof.setCurrentIndex(0) 
        self.combo_cat.setCurrentIndex(0) 
        self.combo_team.setCurrentIndex(0) 
        self.check_pvp.setChecked(False)
        self.check_pve_only.setChecked(False)
        if hasattr(self, 'check_pre'):
             self.check_pre.setChecked(False)
        self.check_show_others.setChecked(False)
        self.check_lock_suggestions.setChecked(False)
        if hasattr(self, 'check_smart_mode'):
             self.check_smart_mode.setChecked(False)
        self.edit_search.clear()
        self.edit_code.clear()
        
        for slot in self.slots:
            slot.clear_slot(silent=True)
            
        self.apply_filters()
        self.update_suggestions()

    def reset_zone_mode(self):
        self.active_zone_mode = False
        if hasattr(self, 'btn_select_zone'):
             self.btn_select_zone.setText("Select Zone")
             self.btn_select_zone.setStyleSheet("QPushButton { background-color: #444; color: white; border-radius: 4px; font-weight: bold; font-size: 10px; } QPushButton:hover { background-color: #555; }")

    def reset_team_mode(self):
        self.team_synergy_skills = []
        if hasattr(self, 'btn_load_team_synergy'):
            self.btn_load_team_synergy.setText("Load Teambuild\nto Bar")
            self.btn_load_team_synergy.setStyleSheet("""
                QPushButton { background-color: #224466; color: white; border-radius: 4px; font-weight: bold; font-size: 10px; }
                QPushButton:hover { background-color: #335577; }
            """)


    def copy_code(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.edit_code.text())

    def load_code(self, code_str=None):
        if not code_str:
            code = self.edit_code.text().strip()
        else:
            code = code_str.strip()
            self.edit_code.setText(code) 
            
        if not code:
            return

        decoder = GuildWarsTemplateDecoder(code)
        build_data = decoder.decode()
        
        if not build_data or "error" in build_data:
            print("Failed to decode build code.")
            return

        primary_prof_id = build_data.get("profession", {}).get("primary", 0)
        secondary_prof_id = build_data.get("profession", {}).get("secondary", 0)
        
        self.current_primary_prof = primary_prof_id
        self.current_secondary_prof = secondary_prof_id
        self.is_swapped = False
        
        # Only auto-switch profession filter if we are NOT in a specific Team/Category view
        # This prevents the list from suddenly filtering out other members of the team
        current_team = self.combo_team.currentText()
        current_cat = self.combo_cat.currentText()
        should_switch_prof = (current_team == "All" and current_cat == "All")

        if primary_prof_id != 0 and should_switch_prof:
            for i in range(self.combo_prof.count()):
                if self.combo_prof.itemData(i) == primary_prof_id:
                    self.combo_prof.setCurrentIndex(i)
                    break
        
        skills = build_data.get("skills", [])
        if len(skills) < 8:
            skills.extend([0] * (8 - len(skills)))
        skills = skills[:8]
        
        is_pvp = self.check_pvp.isChecked()
        
        # Collect active skill objects for PvE attribute detection & Attribute Panel update
        active_skill_objs = []
        
        for i, skill_id in enumerate(skills):
            if skill_id == 0:
                self.bar_skills[i] = None
                self.slots[i].clear_slot(silent=True)
            else:
                self.bar_skills[i] = skill_id
                skill_obj = self.repo.get_skill(skill_id, is_pvp=is_pvp)
                self.slots[i].set_skill(skill_id, skill_obj, ghost=False)
                if skill_obj:
                    active_skill_objs.append(skill_obj)

        # Sync professions and reset editor
        self.update_build_code()
        
        # Set Attributes safely
        attributes_list = build_data.get("attributes", [])
        attr_dist = {attr[0]: attr[1] for attr in attributes_list}
        
        self.attr_editor.blockSignals(True)
        try:
            self.attr_editor.set_distribution(attr_dist)
        finally:
            self.attr_editor.blockSignals(False)
            
        # Update code box with final attributes
        self.update_build_code()

        self.update_suggestions()

    def toggle_elites(self, checked):
        if checked:
            self.check_no_elites.blockSignals(True)
            self.check_no_elites.setChecked(False)
            self.check_no_elites.blockSignals(False)
        self.apply_filters()

    def toggle_no_elites(self, checked):
        if checked:
            self.check_elites_only.blockSignals(True)
            self.check_elites_only.setChecked(False)
            self.check_elites_only.blockSignals(False)
        self.apply_filters()

    def handle_skill_clicked(self, skill: Skill):
        self.current_selected_skill_id = skill.id
        dist = self.attr_editor.get_distribution()
        rank = dist.get(skill.attribute, 0)
        self.info_panel.update_info(skill, repo=self.repo, rank=rank)

    def update_attribute_dropdown(self):
        # We now use the actual ID stored in currentData()
        pid = self.combo_prof.currentData()
        
        self.combo_attr.blockSignals(True)
        self.combo_attr.clear()
        self.combo_attr.addItem("All", -1)
        
        if pid != "All":
            try:
                pid = int(pid)
                if pid in PROF_ATTRS:
                    attrs = PROF_ATTRS[pid][:] # Copy list
                    # Also include primary attribute if not in list
                    if pid in PROF_PRIMARY_ATTR:
                        pa = PROF_PRIMARY_ATTR[pid]
                        if pa not in attrs:
                            attrs.append(pa)
                    
                    # Sort by Name
                    sorted_attrs = sorted(attrs, key=lambda x: ATTR_MAP.get(x, ""))
                    
                    for aid in sorted_attrs:
                        name = ATTR_MAP.get(aid, f"Attr {aid}")
                        self.combo_attr.addItem(name, aid)
            except:
                pass
                
        self.combo_attr.blockSignals(False)
        self.apply_filters()

    def apply_filters(self):
        # Debounce filter changes
        self.filter_debounce_timer.start(250)

    def get_allowed_campaigns(self):
        # Map names to IDs
        # Prophecies=1, Factions=2, Nightfall=3, EotN=4
        camp_map = {
            'Prophecies': 1,
            'Factions': 2,
            'Nightfall': 3,
            'Eye of the North': 4
        }
        
        # Read directly from checkboxes in settings tab if possible, or use saved settings
        # The SettingsTab updates QSettings immediately.
        # We can read QSettings or ask the tab. Reading from tab UI is safer for sync.
        
        allowed = set()
        if self.settings_tab.check_prophecies.isChecked(): allowed.add(1)
        if self.settings_tab.check_factions.isChecked(): allowed.add(2)
        if self.settings_tab.check_nightfall.isChecked(): allowed.add(3)
        if self.settings_tab.check_eotn.isChecked(): allowed.add(4)
        
        return allowed

    def _run_filter(self):
        # Stop any active filtering to prevent crashes
        if hasattr(self, 'filter_worker') and self.filter_worker.isRunning():
            self.filter_worker.requestInterruption()
            self.filter_worker.wait(200)

        # Use currentData() to get the actual ID (int or "All")
        prof = self.combo_prof.currentData()
        target_attr_id = self.combo_attr.currentData()
        if target_attr_id is None: target_attr_id = -1

        cat = self.combo_cat.currentText()
        team = self.combo_team.currentText()
        search_text = self.edit_search.text().lower()

        # --- Mode Logic ---
        # Update Center Panel (Team View) if context exists
        if not search_text:
            if team != "All":
                self.show_team_builds(team)
            elif cat != "All":
                self.show_category_builds(cat)
            else:
                # All/All - Clear Team View but don't force switch
                if hasattr(self, 'team_view_widget'):
                    self.team_view_widget.clear()

        # Update Left Panel (Skills) - Always run FilterWorker
        
        # Override context filters if searching
        # FIX: We always want the Left Panel to show the FULL Skill Database (filtered by Prof/Attr)
        # even if we are viewing a specific Team or Category in the Center Panel.
        # Otherwise, selecting a new (empty) team results in an empty skill list!
        target_team = "All" 
        target_cat = "All" 
        
        if search_text:
             # Search text logic is handled inside worker, but we ensure base is All
             pass

        # Gather filters
        filters = {
            'prof': prof,
            'attr_id': target_attr_id,
            'cat': target_cat,
            'team': target_team,
            'search_text': search_text,
            'search_desc_mode': self.check_search_desc.isChecked() if hasattr(self, 'check_search_desc') else False,
            'is_pvp': self.check_pvp.isChecked(),
            'is_pve_only': self.check_pve_only.isChecked(),
            'is_elites_only': self.check_elites_only.isChecked(),
            'is_no_elites': self.check_no_elites.isChecked(),
            'is_pre_only': self.check_pre.isChecked() if hasattr(self, 'check_pre') else False,
            'allowed_campaigns': self.get_allowed_campaigns()
        }

        self.filter_worker = FilterWorker(DB_FILE, self.engine, filters)
        self.filter_worker.finished.connect(self._on_filter_finished)
        self.filter_worker.start()

    def _apply_profession_filter(self, builds):
        target_prof_id = self.combo_prof.currentData()
        
        if target_prof_id == "All":
            return builds
            
        filtered = []
        for b in builds:
            try:
                # Handle string vs int mismatch safely
                b_prof = int(b.primary_prof)
            except:
                b_prof = 0
                
            if b_prof == target_prof_id or b_prof == 0:
                filtered.append(b)
        return filtered

    def _apply_name_filter(self, builds):
        text = self.edit_build_search.text().lower().strip()
        if not text: return builds
        return [b for b in builds if text in b.name.lower()]

    def show_team_builds(self, team_name):
        # We target the Team View (Center) via _populate_build_list
        # Left Panel (Skills) remains untouched here (handled by FilterWorker)
        
        matching_builds = [b for b in self.engine.builds if b.team == team_name]
        matching_builds = self._apply_profession_filter(matching_builds)
        matching_builds = self._apply_name_filter(matching_builds)
        
        # Smart Deduplication:
        # We want to hide accidental duplicates (Same Name + Same Code)
        # But we want to SHOW distinct slots that might share a code (e.g. "Hero 1" (Empty) vs "Hero 2" (Empty))
        
        unique_builds = []
        seen_keys = set()
        
        for b in matching_builds:
            # key = (Name, Code)
            key = (b.name, b.code)
            
            if key not in seen_keys:
                unique_builds.append(b)
                seen_keys.add(key)
        
        self._populate_build_list(unique_builds)

    def show_category_builds(self, category_name):
        # Filter builds by category (team is "All")
        matching_builds = [b for b in self.engine.builds if b.category == category_name]
        
        matching_builds = self._apply_profession_filter(matching_builds)
        matching_builds = self._apply_name_filter(matching_builds)

        # Deduplicate by Code (Standard behavior for Meta libraries)
        unique_builds = []
        seen_codes = set()
        for b in matching_builds:
            if b.code not in seen_codes:
                unique_builds.append(b)
                seen_codes.add(b.code)

        self._populate_build_list(unique_builds)

    def _populate_build_list(self, matching_builds):
        is_pvp = self.check_pvp.isChecked()
        # Use button state as source of truth for magnification
        current_icon_size = 128 if self.btn_max_icons.isChecked() else 64
        
        # Target the Team View Widget now
        target_widget = self.team_view_widget
        target_widget.delegate.icon_size = current_icon_size
        
        # Ensure Team View is active (unless we are in Manage Teams mode)
        if not self.btn_team_view.isChecked() and not self.btn_manage_teams.isChecked():
            self.btn_team_view.setChecked(True) # This triggers toggle_team_view -> switches stack
        
        # Turn off updates for batch insertion speed and to prevent flickering
        target_widget.setUpdatesEnabled(False)
        target_widget.clear()
        target_widget.setViewMode(QListWidget.ViewMode.ListMode)
        target_widget.setSpacing(0)
        target_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)

        try:
            for b in matching_builds:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, b)
                target_widget.addItem(item)
                
                # Pass parent explicitly to prevent the widget from being created as a separate window
                widget = BuildPreviewWidget(b, self.repo, is_pvp=is_pvp, parent=target_widget, icon_size=current_icon_size)
                item.setSizeHint(QSize(500, widget.height() + 10)) # Match dynamic height with buffer
                
                # RESTORE SAVE STATE
                if b in self.dirty_build_ids:
                    widget.set_edit_mode(True)
                
                widget.load_clicked.connect(self.handle_build_load)
                widget.skill_clicked.connect(self.handle_skill_clicked)
                widget.rename_clicked.connect(self.handle_build_rename)
                widget.populate_clicked.connect(self.handle_build_populate)
                widget.edit_clicked.connect(self.handle_build_edit_start)
                widget.import_clicked.connect(self.handle_build_import)
                target_widget.setItemWidget(item, widget)
        finally:
            target_widget.setUpdatesEnabled(True)

    def handle_build_load(self, build):
        self.build_on_bar = build
        self.load_code(build.code)

    def handle_build_edit_start(self, build):
        # 1. Reset all other widgets in the list to non-edit state (Mutual Exclusion)
        count = self.team_view_widget.count()
        for i in range(count):
            item = self.team_view_widget.item(i)
            widget = self.team_view_widget.itemWidget(item)
            if widget and widget.build != build:
                widget.reset_edit_state()

        # 2. Track this build as being on the bar
        self.build_on_bar = build

        # 3. Load the build to the main bar (Only if it has content)
        # Check if the build is effectively empty (all skills 0)
        is_empty = True
        if build.skill_ids:
            if any(sid != 0 for sid in build.skill_ids):
                is_empty = False
        
        if not is_empty:
            self.load_code(build.code)
        else:
            print(f"Edit started on empty build '{build.name}'. Preserving current bar.")
        
        # 4. No longer switching view automatically per user request

    def handle_build_import(self, build):
        last_dir = self.settings.value("last_load_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Build to Slot", last_dir, "Build Templates (*.txt);;All Files (*)")
        
        if not file_path:
            return

        try:
            # Save dir
            directory = os.path.dirname(file_path)
            self.settings.setValue("last_load_dir", directory)
            
            with open(file_path, 'r') as f:
                code = f.read().strip()
                
            if not code:
                return

            # Validate
            decoder = GuildWarsTemplateDecoder(code)
            decoded = decoder.decode()
            if not decoded:
                QMessageBox.warning(self, "Import Error", "Invalid build template file.")
                return

            # Update Build Object
            build.code = code
            build.primary_prof = str(decoded['profession']['primary'])
            build.secondary_prof = str(decoded['profession']['secondary'])
            build.skill_ids = decoded['skills']
            build.attributes = decoded['attributes']
            build.is_user_build = True

            # Save
            self.engine.save_user_builds()

            # Refresh View (Re-render the list to show new icons)
            team_name = self.combo_team.currentText()
            cat_name = self.combo_cat.currentText()
            if team_name != "All":
                self.show_team_builds(team_name)
            elif cat_name != "All":
                self.show_category_builds(cat_name)
            
            QMessageBox.information(self, "Success", f"Imported build to slot '{build.name}'.")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import file: {e}")

    def handle_build_populate(self, build):
        # DETECT SOURCE: Is this build currently loaded on the main bar?
        # If so, we use the bar code (Foreground Save).
        # Otherwise, we use its original skills + memory attributes (Background Save).
        
        if build == self.build_on_bar:
            # Foreground Save: Read from Bar
            code = self.edit_code.text().strip()
            if not code: return
            
            decoder = GuildWarsTemplateDecoder(code)
            decoded = decoder.decode()
            if decoded:
                build.code = code
                build.primary_prof = str(decoded['profession']['primary'])
                build.secondary_prof = str(decoded['profession']['secondary'])
                build.skill_ids = decoded['skills']
                build.attributes = decoded['attributes']
        else:
            # Background Save: Preserve existing skills, update code from memory attributes
            data = {
                "header": {"type": 14, "version": 0},
                "profession": {
                    "primary": int(build.primary_prof) if build.primary_prof.isdigit() else 0,
                    "secondary": int(build.secondary_prof) if build.secondary_prof.isdigit() else 0
                },
                "attributes": build.attributes, 
                "skills": build.skill_ids 
            }
            encoder = GuildWarsTemplateEncoder(data)
            build.code = encoder.encode()

        build.is_user_build = True
        self.dirty_build_ids.discard(build) 

        # Save & Refresh
        self.engine.save_user_builds()
        team_name = self.combo_team.currentText()
        cat_name = self.combo_cat.currentText()
        if team_name != "All": self.show_team_builds(team_name)
        elif cat_name != "All": self.show_category_builds(cat_name)
        
        if build == self.build_on_bar:
            QMessageBox.information(self, "Success", f"Build slot '{build.name}' updated.")

    def handle_build_rename(self, build):
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "Rename Build", "Enter build name:", text=build.name)
        if ok:
            build.name = new_name.strip()
            build.is_user_build = True
            self.engine.save_user_builds()
            # Refresh current view
            team_name = self.combo_team.currentText()
            cat_name = self.combo_cat.currentText()
            if team_name != "All":
                self.show_team_builds(team_name)
            else:
                self.show_category_builds(cat_name)

    def handle_builds_reordered(self, source_row, target_row):
        team_name = self.combo_team.currentText()
        cat_name = self.combo_cat.currentText()
        
        # 1. Get the list of builds currently visible
        if team_name != "All":
            matching_builds = [b for b in self.engine.builds if b.team == team_name]
            if cat_name != "All":
                matching_builds = [b for b in matching_builds if b.category == cat_name]
        else:
            matching_builds = [b for b in self.engine.builds if b.category == cat_name]
            
        matching_builds = self._apply_profession_filter(matching_builds)
            
        if not matching_builds or source_row >= len(matching_builds) or target_row >= len(matching_builds):
            return

        # 2. Get global indices of these specific builds in the master engine list
        # We use object identity (id()) to be absolutely sure we map the correct objects
        visible_ids = [id(b) for b in matching_builds]
        global_indices = [i for i, b in enumerate(self.engine.builds) if id(b) in visible_ids]

        if len(global_indices) != len(matching_builds):
            return

        # 3. Reorder the visible list
        build_to_move = matching_builds.pop(source_row)
        matching_builds.insert(target_row, build_to_move)

        # 4. Map the reordered builds back to the original global positions
        for idx, build in zip(global_indices, matching_builds):
            self.engine.builds[idx] = build
            build.is_user_build = True

        # 5. Save and Refresh
        self.engine.save_user_builds()
        if team_name != "All":
            self.show_team_builds(team_name)
        else:
            self.show_category_builds(cat_name)

    def _on_filter_finished(self, filtered_skills):
        self.library_widget.clear()
        # Reset View Mode for Skills
        self.library_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.library_widget.setSpacing(5)
        # Enable dragging skills OUT, but not dropping IN or reordering
        self.library_widget.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        
        # Sync delegate with magnifier state
        current_size = 128 if self.btn_max_icons.isChecked() else 64
        self.library_widget.delegate.icon_size = current_size
        
        # Turn off updates briefly for insertion speed
        self.library_widget.setUpdatesEnabled(False)
        
        for skill in filtered_skills:
            item = QListWidgetItem(skill.name)
            item.setData(Qt.ItemDataRole.UserRole, skill.id)
            item.setData(Qt.ItemDataRole.DisplayRole, skill.name) # Explicitly set display role for delegate
            
            # Icon Loading (Size-Aware Caching)
            cache_key = f"{skill.icon_filename}_{current_size}"
            pix = None
            
            if cache_key in PIXMAP_CACHE:
                pix = PIXMAP_CACHE[cache_key]
            else:
                path = os.path.join(ICON_DIR, skill.icon_filename)
                if os.path.exists(path):
                    pix = QPixmap(path)
                    # Cache based on current magnification size
                    pix = pix.scaled(current_size, current_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    PIXMAP_CACHE[cache_key] = pix
            
            if pix:
                item.setIcon(QIcon(pix))
                item.setData(Qt.ItemDataRole.DecorationRole, QIcon(pix)) # Ensure delegate gets the icon
            
            self.library_widget.addItem(item)
            
        self.library_widget.setUpdatesEnabled(True)

    def handle_skill_equipped_auto(self, data):
        if isinstance(data, dict): return

        skill_id = data
        # Find first empty slot
        empty_index = -1
        for i, s_id in enumerate(self.bar_skills):
            if s_id is None:
                empty_index = i
                break
        
        if empty_index != -1:
            self.handle_skill_equipped(empty_index, skill_id)           

    def get_current_bonuses(self):
        # Returns { "Attribute Name": calculated_bonus_value } for all primary attributes
        bonuses = {}
        eff_dist = self.get_effective_distribution()
        
        for prof_id, attr_id in PROF_PRIMARY_ATTR.items():
            rank = eff_dist.get(attr_id, 0)
            if rank > 0:
                val = get_primary_bonus_value(attr_id, rank)
                attr_name = ATTR_MAP.get(attr_id, "")
                if attr_name:
                    bonuses[attr_name] = val
        return bonuses

    def handle_skill_id_clicked(self, data):
        if isinstance(data, dict):
            self.info_panel.update_monster_info(data)
            return

        skill_id = data
        self.current_selected_skill_id = skill_id
        is_pvp = self.check_pvp.isChecked()
        skill = self.repo.get_skill(skill_id, is_pvp=is_pvp)
        if skill:
            eff_dist = self.get_effective_distribution()
            rank = eff_dist.get(skill.attribute, 0)
            
            all_bonuses = self.get_current_bonuses()
            glob_act = self.current_global_effects.get('activation', 0.0)
            glob_rech = self.current_global_effects.get('recharge', 0.0)
            
            self.info_panel.update_info(skill, repo=self.repo, rank=rank, 
                                      bonuses=all_bonuses,
                                      global_act=glob_act, global_rech=glob_rech)

    def handle_skill_equipped(self, index, skill_id):
        # 1. Duplicate Check: Don't allow same skill twice
        if skill_id in self.bar_skills and self.bar_skills.index(skill_id) != index:
            return

        # 2. PvE Limit Check
        is_pvp = self.check_pvp.isChecked()
        skill_obj = self.repo.get_skill(skill_id, is_pvp=is_pvp)
        
        if skill_obj and skill_obj.is_pve_only:
            current_pve_count = 0
            for i, sid in enumerate(self.bar_skills):
                if i == index: continue # Ignore slot being replaced
                if sid is not None:
                    s = self.repo.get_skill(sid, is_pvp=is_pvp)
                    if s and s.is_pve_only:
                        current_pve_count += 1
            
            if current_pve_count >= 3:
                return # Block adding the 4th PvE skill

        self.bar_skills[index] = skill_id
        self.suggestion_offset = 0 
        
        eff_dist = self.get_effective_distribution()
        rank = eff_dist.get(skill_obj.attribute, 0) if skill_obj else 0
        
        all_bonuses = self.get_current_bonuses()
        glob_act = self.current_global_effects.get('activation', 0.0)
        glob_rech = self.current_global_effects.get('recharge', 0.0)
        
        self.slots[index].set_skill(skill_id, skill_obj, ghost=False, rank=rank, 
                                  bonuses=all_bonuses,
                                  global_act=glob_act, global_rech=glob_rech)
        
        self.update_suggestions()
        self.update_build_code()

    def handle_skill_removed(self, index):
        self.bar_skills[index] = None
        self.suggestion_offset = 0 
        self.update_suggestions()
        
    def handle_skill_swapped(self, source_index, target_index):
        # Swap in the internal list
        self.bar_skills[source_index], self.bar_skills[target_index] = \
            self.bar_skills[target_index], self.bar_skills[source_index]
        
        # Refresh the visual slots
        self.refresh_equipped_skills()
        self.update_suggestions()
    def refresh_equipped_skills(self):
        is_pvp = self.check_pvp.isChecked()
        eff_dist = self.get_effective_distribution()
        all_bonuses = self.get_current_bonuses()
        glob_act = self.current_global_effects.get('activation', 0.0)
        glob_rech = self.current_global_effects.get('recharge', 0.0)

        for i, sid in enumerate(self.bar_skills):
            if sid is not None:
                skill_obj = self.repo.get_skill(sid, is_pvp=is_pvp)
                rank = eff_dist.get(skill_obj.attribute, 0) if skill_obj else 0
                self.slots[i].set_skill(sid, skill_obj, ghost=False, rank=rank,
                                      bonuses=all_bonuses,
                                      global_act=glob_act, global_rech=glob_rech)
        self.update_suggestions()

    def cycle_suggestions(self):
        empty_slots = sum(1 for s in self.bar_skills if s is None)
        if empty_slots == 0: 
            print("Cycle: No empty slots.")
            return

        if self.current_suggestions:
            old_offset = self.suggestion_offset
            # Shift offset by number of visible slots
            self.suggestion_offset = (self.suggestion_offset + empty_slots) % len(self.current_suggestions)
            print(f"Cycling: Offset {old_offset} -> {self.suggestion_offset} (Total: {len(self.current_suggestions)})")
            self.display_suggestions()
        else:
            print("Cycle: No suggestions to cycle.")

    def on_synergies_loaded(self, suggestions):
        self.lbl_bar_loading.setVisible(False)
        self.current_suggestions = []
        is_pvp = self.check_pvp.isChecked()
        show_others = self.check_show_others.isChecked()
        
        # Ensure all equipped IDs are integers for reliable comparison
        equipped_ids = set()
        equipped_names = set()
        for sid in self.bar_skills:
            if sid is not None:
                try:
                    sid_int = int(sid)
                    equipped_ids.add(sid_int)
                    # Also track names for cross-version (PvP/PvE) duplicate prevention
                    skill_obj = self.repo.get_skill(sid_int)
                    if skill_obj:
                        clean = skill_obj.name.lower().replace(" (pvp)", "").strip()
                        equipped_names.add(clean)
                except (ValueError, TypeError):
                    pass
        
        # Determine allowed professions: Primary, Secondary, and Common (0)
        allowed_profs = {0}
        try:
            if self.current_primary_prof: 
                allowed_profs.add(int(self.current_primary_prof))
            if self.current_secondary_prof: 
                allowed_profs.add(int(self.current_secondary_prof))
        except (ValueError, TypeError):
            pass
        
        # Enforce limits if user hasn't opted out AND both professions are chosen
        enforce_prof_limit = not show_others and self.current_primary_prof != 0 and self.current_secondary_prof != 0

        print(f"[UI] Suggestions received: {len(suggestions)}")
        filtered_count = 0

        for item in suggestions:
            if len(item) == 3:
                sid, conf, reason = item
            else:
                sid, conf = item
                reason = None

            if sid == 0: continue
            
            # Use integer comparison for equipped check
            try:
                if int(sid) in equipped_ids:
                    continue
            except:
                pass

            skill = self.repo.get_skill(sid, is_pvp=is_pvp)
            if not skill: continue
            
            # Duplicate prevention by name (Secondary check)
            clean_name = skill.name.lower().replace(" (pvp)", "").strip()
            if clean_name in equipped_names:
                continue

            if is_pvp and skill.is_pve_only: continue
            
            # Strict Profession Filter
            if enforce_prof_limit and skill.profession not in allowed_profs:
                filtered_count += 1
                continue
            
            # Spirit Redundancy
            if hasattr(self, 'check_smart_mode') and self.check_smart_mode.isChecked():
                if sid in self.team_synergy_skills:
                    # Check if it's a spirit
                    # We can use the tag map logic or just check the description
                    # Since we standardized tags, let's query the DB for this skill's tags if not already cached
                    # Or simpler: check if "Type_Spirit" is in its stats (if we had tags in Skill class)
                    # We'll do a quick check against the skill_tags table
                    cursor = self.repo.conn.cursor()
                    cursor.execute("SELECT 1 FROM skill_tags WHERE skill_id=? AND tag='Type_Spirit'", (sid,))
                    if cursor.fetchone():
                        continue # Skip duplicate spirit

            self.current_suggestions.append((sid, conf, reason))
        
        print(f"[UI] Suggestions kept after filter: {len(self.current_suggestions)} (Filtered: {filtered_count})")

        self.suggestion_offset = 0
        self.display_suggestions()

    def update_suggestions(self):
        # Prevent updates if "Lock" is checked OR Zone Mode is active
        if (hasattr(self, 'check_lock_suggestions') and self.check_lock_suggestions.isChecked()) or getattr(self, 'active_zone_mode', False):
            return
            
        # Optimization: Restart worker if parameters changed
        if hasattr(self, 'worker') and self.worker.isRunning():
            try: self.worker.results_ready.disconnect()
            except: pass
            self.worker.stop()
            
        # Normalize all IDs to integers
        active_ids = []
        for sid in self.bar_skills:
            if sid is not None:
                try:
                    active_ids.append(int(sid))
                except:
                    pass
        
        # Always include the loaded team context if available (Active Team Mode)
        bar_set = set(active_ids)
        for sid in self.team_synergy_skills:
            try:
                sid_int = int(sid)
                if sid_int not in bar_set:
                    active_ids.append(sid_int)
            except:
                pass

        print(f"[UI] Sending {len(active_ids)} active IDs to engine (Bar + Team Context).")

        # Get Profession ID
        prof_text = self.combo_prof.currentText()
        try:
            pid = int(prof_text.split(' ')[0])
        except:
            pid = 0

        is_debug = False
        mode = "smart" if hasattr(self, 'check_smart_mode') and self.check_smart_mode.isChecked() else "legacy"
        is_pre = self.check_pre.isChecked() if hasattr(self, 'check_pre') else False
        allowed_campaigns = self.get_allowed_campaigns()
        is_pvp = self.check_pvp.isChecked()

        if mode == "smart":
            self.lbl_bar_loading.setVisible(True)

        dist = self.attr_editor.get_distribution()
        current_max_energy = self.character_panel.get_total_energy()

        # ALWAYS use self.engine (Neural/Hybrid)
        self.worker = SynergyWorker(self.engine, active_ids, pid, mode, debug=is_debug, is_pre=is_pre, allowed_campaigns=allowed_campaigns, is_pvp=is_pvp, attr_dist=dist, total_energy=current_max_energy)
        self.worker.results_ready.connect(self.on_synergies_loaded)
        self.worker.start()

    def display_suggestions(self):
        empty_indices = [i for i, s in enumerate(self.bar_skills) if s is None]
        
        display_list = []
        is_pvp = self.check_pvp.isChecked()

        if self.current_suggestions:
            total_suggestions = len(self.current_suggestions)
            needed = len(empty_indices)
            
            # LOGIC FIX: Do not wrap around. Stop if we run out of unique items.
            # We take a slice of the list starting at the offset.
            # If the offset + needed exceeds the list, we just take what's left.
            
            for i in range(needed):
                idx = self.suggestion_offset + i
                if idx < total_suggestions:
                    display_list.append(self.current_suggestions[idx])
                else:
                    # We ran out of suggestions to show. Stop filling.
                    break
        
        s_idx = 0
        eff_dist = self.get_effective_distribution()
        all_bonuses = self.get_current_bonuses()
        glob_act = self.current_global_effects.get('activation', 0.0)
        glob_rech = self.current_global_effects.get('recharge', 0.0)
        
        for slot_idx in empty_indices:
            slot = self.slots[slot_idx]
            
            if s_idx < len(display_list):
                # Fill slot with suggestion
                item = display_list[s_idx]
                if len(item) == 3:
                    s_id, conf, reason = item
                    display_val = reason if reason else conf
                else:
                    s_id, conf = item
                    display_val = conf

                skill_obj = self.repo.get_skill(s_id, is_pvp=is_pvp)
                rank = eff_dist.get(skill_obj.attribute, 0) if skill_obj else 0
                slot.set_skill(s_id, skill_obj, ghost=True, confidence=display_val, rank=rank,
                             bonuses=all_bonuses,
                             global_act=glob_act, global_rech=glob_rech)
                s_idx += 1
            else:
                # Ran out of suggestions? Clear the slot.
                slot.clear_slot(silent=True)
                
        self.update_build_code()

    def on_team_list_selection_changed(self):
        selected_items = self.team_view_widget.selectedItems()
        if not selected_items:
            self.active_edit_build = None
            self.attr_editor.set_read_only(False) # Default to editable
            return
        
        item = selected_items[0]
        build = item.data(Qt.ItemDataRole.UserRole)
        
        if not isinstance(build, Build): 
            self.active_edit_build = None
            self.attr_editor.set_read_only(False) # Default to editable
            return
        
        self.active_edit_build = build # BINDING
        
        # --- READ ONLY LOGIC ---
        is_user = getattr(build, 'is_user_build', False)
        self.attr_editor.set_read_only(not is_user)
        
        self.loading_from_selection = True
        try:
            # 1. Update Professions in Editor
            p1 = int(build.primary_prof) if build.primary_prof.isdigit() else 0
            p2 = int(build.secondary_prof) if build.secondary_prof.isdigit() else 0
            
            # Need to get skills to determine available attributes correctly (PvE)
            # We can use the build's skill list for this context
            active_skill_objs = []
            for sid in build.skill_ids:
                if sid != 0:
                    s = self.repo.get_skill(sid)
                    if s: active_skill_objs.append(s)
            
            # Update Editor State
            self.attr_editor.set_professions(p1, p2, active_skill_objs)
            
            # 2. Update Attributes
            attr_dist = {a[0]: a[1] for a in build.attributes}
            self.attr_editor.set_distribution(attr_dist)
            
            # 3. Sync Main Window State variables so Code Box updates correctly
            self.current_primary_prof = p1
            self.current_secondary_prof = p2
            # Note: We do NOT update bar_skills here to preserve the bar state as requested
            
        finally:
            self.loading_from_selection = False
            # Force code update to reflect new attributes + existing bar
            self.update_build_code()

    def on_attributes_changed(self, distribution):
        self.update_build_code()
        
        # Ensure labels are updated with external bonuses (Runes + Cons + HR)
        global_bonus = self.current_global_effects.get('all_atts', 0)
        self.attr_editor.set_external_bonuses(self.current_bonuses, global_bonus)
        
        # Update Energy Storage bonus display if applicable
        if hasattr(self, 'character_panel') and self.current_primary_prof == 6:
            eff_dist = self.get_effective_distribution()
            es_rank = eff_dist.get(12, 0)
            self.character_panel.set_attr_energy_bonus(es_rank * 3)

        # Phase 3: Refresh skill tooltips/displays
        self.refresh_skill_displays()
        
        # Phase 4: Handle "Save" button state if in Team View
        if not self.loading_from_selection and self.active_edit_build:
            # Update attributes in memory IMMEDIATELY for the active build
            new_attrs = [[k, v] for k, v in distribution.items() if v > 0]
            self.active_edit_build.attributes = new_attrs
            self.dirty_build_ids.add(self.active_edit_build)
            
            # Find the widget to update visual state
            if self.btn_team_view.isChecked():
                for i in range(self.team_view_widget.count()):
                    item = self.team_view_widget.item(i)
                    widget = self.team_view_widget.itemWidget(item)
                    if widget and widget.build == self.active_edit_build:
                        widget.set_edit_mode(True)
                        break

    def on_stats_changed(self, bonuses, globals_dict):
        self.current_bonuses = bonuses
        self.current_global_effects = globals_dict
        
        # Important: Sync build code / professions list first
        # This handles weapon attributes being added/removed from the list
        self.update_build_code()
        
        # Update Attribute Editor UI
        global_bonus = globals_dict.get('all_atts', 0)
        self.attr_editor.set_external_bonuses(bonuses, global_bonus)
        
        # Refresh Skills
        self.refresh_skill_displays()
        
    def get_effective_distribution(self):
        dist = self.attr_editor.get_distribution()
        global_bonus = self.current_global_effects.get('all_atts', 0)
        hr_bonus = self.attr_editor.get_hr_bonus()
        
        effective = {}
        for aid, rank in dist.items():
            bonus = self.current_bonuses.get(aid, 0) + global_bonus + hr_bonus
            total = rank + bonus
            if total > 20: total = 20
            effective[aid] = total
        return effective

    def refresh_skill_displays(self):
        is_pvp = self.check_pvp.isChecked()
        eff_dist = self.get_effective_distribution()
        all_bonuses = self.get_current_bonuses()
        
        glob_act = self.current_global_effects.get('activation', 0.0)
        glob_rech = self.current_global_effects.get('recharge', 0.0)
        
        # Refresh equipped skills
        for i, sid in enumerate(self.bar_skills):
            if sid is not None:
                skill_obj = self.repo.get_skill(sid, is_pvp=is_pvp)
                rank = eff_dist.get(skill_obj.attribute, 0) if skill_obj else 0
                self.slots[i].set_skill(sid, skill_obj, ghost=False, rank=rank, 
                                      bonuses=all_bonuses,
                                      global_act=glob_act, global_rech=glob_rech)
                
        # Refresh info panel
        if self.current_selected_skill_id is not None:
            skill_obj = self.repo.get_skill(self.current_selected_skill_id, is_pvp=is_pvp)
            if skill_obj:
                rank = eff_dist.get(skill_obj.attribute, 0)
                self.info_panel.update_info(skill_obj, repo=self.repo, rank=rank, 
                                          bonuses=all_bonuses,
                                          global_act=glob_act, global_rech=glob_rech)

        # Refresh suggestions (this will call display_suggestions)
        self.display_suggestions()

    def load_build_from_file(self):
        last_dir = self.settings.value("last_load_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Build Template", last_dir, "Build Templates (*.txt);;All Files (*)")
        if file_path:
            # Save the directory for next time
            directory = os.path.dirname(file_path)
            self.settings.setValue("last_load_dir", directory)
            
            try:
                with open(file_path, 'r') as f:
                    code = f.read().strip()
                self.load_code(code)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def open_prof_selection(self):
        dlg = ProfessionSelectionDialog(self.current_primary_prof, self.current_secondary_prof, self)
        if dlg.exec():
            p1, p2 = dlg.get_professions()
            self.current_primary_prof = p1
            self.current_secondary_prof = p2
            self.update_build_code()
            self.update_suggestions() # Explicit refresh

    def swap_professions(self):
        # Simply swap the stored IDs
        self.current_primary_prof, self.current_secondary_prof = self.current_secondary_prof, self.current_primary_prof
        self.update_build_code()
        self.update_suggestions() # Explicit refresh

    def update_build_code(self):
        active_bar = [s if s is not None else 0 for s in self.bar_skills]
        
        # Use stored state directly. No auto-detection.
        p1 = self.current_primary_prof
        p2 = self.current_secondary_prof

        p1_name = PROF_MAP.get(p1, "No Profession")
        p2_name = PROF_MAP.get(p2, "No Profession")
        p1_str = PROF_SHORT_MAP.get(p1_name, "X")
        p2_str = PROF_SHORT_MAP.get(p2_name, "X")
        
        if hasattr(self, 'btn_prof_select'):
            self.btn_prof_select.setText(f"Prof: {p1_str}/{p2_str}")
        
        # Check uniqueness visibility
        active_count = sum(1 for s in active_bar if s != 0)
        if hasattr(self, 'btn_check_unique'):
            self.btn_check_unique.setVisible(active_count == 8)
        
        # Collect active skill objects for PvE attribute detection
        active_skill_objs = []
        all_attr_ids = set()
        
        for sid in active_bar:
            if sid != 0:
                s = self.repo.get_skill(sid)
                if s: 
                    active_skill_objs.append(s)
                    if s.attribute != -1:
                        all_attr_ids.add(s.attribute)

        # Update Attribute Editor professions ONLY if needed to prevent recursion
        # If profs are 0, we need to track ALL attributes in the state key to update panel
        if p1 == 0 and p2 == 0:
            state_attrs = frozenset(all_attr_ids)
        else:
            # Otherwise just track PvE attributes (negative)
            state_attrs = frozenset([a for a in all_attr_ids if a < 0])

        # Track active weapon attribute to ensure it appears in the editor
        weapon_attr = None
        if hasattr(self, 'character_panel') and self.character_panel.active_weapon:
             w_data = WEAPONS.get(self.character_panel.active_weapon)
             if w_data:
                 weapon_attr = w_data['attr']

        current_state = (p1, p2, state_attrs, weapon_attr)
        
        if current_state != self._last_attr_state:
            # Update state immediately to prevent recursion loops
            self._last_attr_state = current_state
            
            # BLOCK SIGNALS to prevent loop: professions update -> attr update -> build code update -> professions update
            self.attr_editor.blockSignals(True)
            if hasattr(self, 'character_panel'):
                self.character_panel.blockSignals(True)

            try:
                extra = [weapon_attr] if weapon_attr is not None else []
                self.attr_editor.set_professions(p1, p2, active_skill_objs, extra_attrs=extra)
                
                # REFRESH BONUSES after re-creating widgets
                global_bonus = self.current_global_effects.get('all_atts', 0)
                self.attr_editor.set_external_bonuses(self.current_bonuses, global_bonus)
                
                if hasattr(self, 'character_panel'):
                    # 1. Enforce Rune restrictions
                    self.character_panel.set_primary_profession(p1)
                    
                    # 2. Update Attribute-based energy (Energy Storage)
                    # Energy Storage ID: 12. Bonus: rank * 3
                    en_bonus = 0
                    if p1 == 6: # Elementalist
                        eff_dist = self.get_effective_distribution()
                        es_rank = eff_dist.get(12, 0)
                        en_bonus = es_rank * 3
                    self.character_panel.set_attr_energy_bonus(en_bonus)
            finally:
                self.attr_editor.blockSignals(False)
                if hasattr(self, 'character_panel'):
                    self.character_panel.blockSignals(False)

        # Get actual ranks from editor for the build code
        dist = self.attr_editor.get_distribution()
        attributes = []
        for aid, rank in dist.items():
            if rank > 0:
                attributes.append([aid, rank])

        data = {
            "header": {"type": 14, "version": 0},
            "profession": {"primary": p1, "secondary": p2},
            "attributes": attributes,
            "skills": active_bar
        }
        
        try:
            live_code = GuildWarsTemplateEncoder(data).encode()
            self.edit_code.setText(live_code)
        except:
            pass
            
        # Optimization: Only refresh suggestions if professions ACTUALLY changed
        # current_state = (p1, p2, state_attrs, weapon_attr)
        # _last_attr_state was updated above if things changed.
        # We can check if p1/p2 in _last_attr_state differ from previous known state, but _last_attr_state IS the previous state until updated.
        
        # Actually, update_build_code is called by handle_skill_equipped too.
        # We DO want suggestions to update when skills change (for context), but NOT when attributes change.
        # BUT update_suggestions() is already called in handle_skill_equipped explicitly.
        
        # So we should REMOVE the call from here completely, and only call it from:
        # 1. handle_skill_equipped/removed/swapped (Already done)
        # 2. open_prof_selection (Needs explicit call)
        # 3. swap_professions (Needs explicit call)
        # 4. load_code (Already calls it)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                path = urls[0].toLocalFile()
                if os.path.isdir(path):
                    event.accept()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            folder_path = urls[0].toLocalFile()
            self.process_folder_drop(folder_path)

    def select_folder_for_team(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Team Build Folder")
        if folder_path:
            self.process_folder_drop(folder_path)

    def toggle_icon_size(self):
        checked = self.btn_max_icons.isChecked()
        new_size = 128 if checked else 64
        self.library_widget.set_icon_size(new_size)
        if hasattr(self, 'character_panel'):
            self.character_panel.set_icon_size(new_size)
        if hasattr(self, 'weapons_panel'):
            self.weapons_panel.set_icon_size(new_size)

    def toggle_character_view(self, checked):
        if checked:
            self.btn_team_view.blockSignals(True)
            self.btn_team_view.setChecked(False)
            self.btn_team_view.blockSignals(False)
            
            self.btn_manage_teams.blockSignals(True)
            self.btn_manage_teams.setChecked(False)
            self.btn_manage_teams.blockSignals(False)

            self.center_stack.setCurrentIndex(1)
            self.right_stack.setCurrentIndex(1) # Show Weapons
        else:
            if not self.btn_manage_teams.isChecked() and not self.btn_team_view.isChecked():
                self.center_stack.setCurrentIndex(0)
                self.right_stack.setCurrentIndex(0) # Show Attributes

    def toggle_team_view(self, checked):
        if checked:
            self.btn_char_view.blockSignals(True)
            self.btn_char_view.setChecked(False)
            self.btn_char_view.blockSignals(False)
            
            self.btn_manage_teams.blockSignals(True)
            self.btn_manage_teams.setChecked(False)
            self.btn_manage_teams.blockSignals(False)

            self.center_stack.setCurrentIndex(2) # Team View
            self.right_stack.setCurrentIndex(0) # Show Attributes
        else:
            if not self.btn_manage_teams.isChecked() and not self.btn_char_view.isChecked():
                self.center_stack.setCurrentIndex(0)
                self.right_stack.setCurrentIndex(0) # Show Attributes

    def process_folder_drop(self, folder_path, team_name=None):
        if team_name is None:
            team_name = os.path.basename(folder_path)
        if not team_name: return
        
        added_count = 0
        
        # Iterate files
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".txt"):
                file_path = os.path.join(folder_path, filename)
                try:
                    with open(file_path, 'r') as f:
                        code = f.readline().strip() # Read only first line for code
                        
                    # Validate Code
                    decoder = GuildWarsTemplateDecoder(code)
                    decoded = decoder.decode()
                    if decoded:
                        # ...
                        # Add to Engine
                        # Check duplicates?
                        exists = False
                        for b in self.engine.builds:
                            if b.code == code and b.team == team_name:
                                exists = True
                                break
                        
                        if not exists:
                            build_name = os.path.splitext(filename)[0]
                            new_build = Build(
                                code=code,
                                primary_prof=str(decoded['profession']['primary']),
                                secondary_prof=str(decoded['profession']['secondary']),
                                skill_ids=decoded['skills'],
                                category="User Imported",
                                team=team_name,
                                name=build_name
                            )
                            new_build.is_user_build = True
                            self.engine.builds.append(new_build)
                            added_count += 1
                            
                except Exception as e:
                    print(f"Error processing {filename}: {e}")

        if added_count > 0:
            self.engine.teams.add(team_name)
            self.engine.save_user_builds()
            self.update_team_dropdown()
            # Select the new team
            idx = self.combo_team.findText(team_name)
            if idx != -1: self.combo_team.setCurrentIndex(idx)
            QMessageBox.information(self, "Team Added", f"Added {added_count} builds to team '{team_name}'.")
        else:
            QMessageBox.warning(self, "No Builds Found", "Could not find valid build codes in the selected folder.")

    def check_build_uniqueness(self):
        active_ids = [s for s in self.bar_skills if s is not None]
        if len(active_ids) < 8: return
        
        target_set = set(active_ids)
        matches = []
        
        for b in self.engine.builds:
            b_set = set([s for s in b.skill_ids if s != 0])
            overlap = len(target_set.intersection(b_set))
            if overlap >= 4: # Show anything with decent overlap
                matches.append({'score': overlap, 'build': b})
        
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        dlg = BuildUniquenessDialog(matches, len(self.engine.builds), active_ids, self.repo, self)
        dlg.exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'tutorial_manager') and self.tutorial_manager.overlay.isVisible():
            self.tutorial_manager.overlay.resize(self.size())

    def closeEvent(self, event):
        # Stop Synergy Worker
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.requestInterruption()
            try: self.worker.results_ready.disconnect()
            except: pass
            self.worker.wait(500)

        # Stop Filter Worker
        if hasattr(self, 'filter_worker') and self.filter_worker.isRunning():
            self.filter_worker.requestInterruption()
            try: self.filter_worker.finished.disconnect()
            except: pass
            self.filter_worker.wait(500)

        event.accept()
