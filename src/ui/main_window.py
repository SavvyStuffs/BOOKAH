import sys
import os
import json
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QSplitter, 
    QTabWidget, QCheckBox, QPushButton, QFileDialog, QMessageBox, QFrame, QLineEdit, QApplication, QListWidgetItem, QListWidget, QSizePolicy, QGridLayout, QStyle, QProgressDialog
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from src.constants import DB_FILE, JSON_FILE, PROF_MAP, PROF_SHORT_MAP, resource_path, ICON_DIR, ICON_SIZE, PIXMAP_CACHE
from src.database import SkillRepository
from src.engine import MechanicsEngine, SynergyEngine
from src.models import Build, Skill
from src.utils import GuildWarsTemplateDecoder, GuildWarsTemplateEncoder
from src.ui.components import SkillSlot, SkillInfoPanel, SkillLibraryWidget, BuildPreviewWidget
from src.ui.attribute_editor import AttributeEditor
from src.ui.dialogs import TeamManagerDialog, LocationManagerDialog, BuildUniquenessDialog
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
                        
                    filtered_skills.append(skill)

            # Sort by profession (ascending), then by name (ascending)
            filtered_skills.sort(key=lambda x: (x.profession, x.name))

            self.finished.emit(filtered_skills)
        except Exception as e:
            print(f"FilterWorker Error: {e}")
        finally:
            if 'local_repo' in locals():
                local_repo.conn.close()

class SynergyWorker(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, engine, active_skill_ids, prof_id=0, mode="legacy", debug=False, is_pre=False, allowed_campaigns=None, is_pvp=False):
        super().__init__()
        self.engine = engine
        self.active_skill_ids = active_skill_ids
        self.prof_id = prof_id 
        self.mode = mode
        self.debug = debug
        self.is_pre = is_pre
        self.allowed_campaigns = allowed_campaigns
        self.is_pvp = is_pvp
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
                primary_prof_id=self.prof_id
            )
            
            if not self.isInterruptionRequested():
                self.results_ready.emit(results)
        except Exception as e:
            print(f"Worker Error: {e}")

    def stop(self):
        self.requestInterruption() # New standard PyQt6 way
        self.quit()
        self.wait(500)

class MainWindow(QMainWindow):
    def __init__(self, engine=None):
        super().__init__()
        self.setWindowTitle("B.O.O.K.A.H. (Build Optimization & Organization for Knowledge-Agnostic Hominids)")
        self.resize(1200, 800)
        
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
        self._last_attr_state = None
        
        self.pending_update = None # Store update info if window is not visible

        self.setAcceptDrops(True) # Enable Drag & Drop
        # Debounce timer for search/filter inputs
        self.filter_debounce_timer = QTimer()
        self.filter_debounce_timer.setSingleShot(True)
        self.filter_debounce_timer.timeout.connect(self._run_filter)
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
        if self.isVisible():
            self._show_update_dialog(new_version, download_url, release_notes)
        else:
            self.pending_update = (new_version, download_url, release_notes)

    def showEvent(self, event):
        super().showEvent(event)
        
        # Trigger update check once when window is shown
        if not self._update_check_triggered:
            self._update_check_triggered = True
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

        if hasattr(self, 'lbl_prof_display'):
            self.lbl_prof_display.setStyleSheet(f"color: {get_color('text_tertiary')}; font-weight: bold;")

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

    def init_builder_ui(self, parent_widget):
        main_layout = QVBoxLayout(parent_widget)

        # --- Top Filter Grid ---
        top_grid = QGridLayout()
        # top_grid.setSpacing(10) # Optional, default is usually fine
        
        # Col 0: Prof Label
        top_grid.addWidget(QLabel("Profession:"), 0, 0)
        
        # Col 1: Prof Combo
        self.combo_prof = QComboBox()
        self.combo_prof.addItem("All")
        for pid in sorted(PROF_MAP.keys()):
            self.combo_prof.addItem(f"{pid} - {PROF_MAP[pid]}")
        self.combo_prof.currentTextChanged.connect(self.apply_filters)
        top_grid.addWidget(self.combo_prof, 0, 1)
        
        # Col 2: Cat Label
        top_grid.addWidget(QLabel("Category:"), 0, 2)
        
        # Col 3: Cat Combo
        self.combo_cat = QComboBox()
        self.combo_cat.addItem("All")
        self.combo_cat.addItems(sorted(list(self.engine.categories)))
        self.combo_cat.currentTextChanged.connect(self.update_team_dropdown)
        top_grid.addWidget(self.combo_cat, 0, 3)
        
        # Col 4: Team Label
        top_grid.addWidget(QLabel("Team:"), 0, 4)
        
        # Col 5: Team Combo
        self.combo_team = QComboBox()
        self.combo_team.addItem("All")
        # Priority sort: Solo first
        all_teams = self.engine.teams
        if "Solo" in all_teams:
            self.combo_team.addItem("Solo")
            others = sorted([t for t in all_teams if t != "Solo"])
        else:
            others = sorted(list(all_teams))
        self.combo_team.addItems(others)
        self.combo_team.currentTextChanged.connect(self.apply_filters)
        self.combo_team.setCurrentIndex(0) 
        top_grid.addWidget(self.combo_team, 0, 5)
        
        # Col 6: Manage Teams
        self.btn_manage_teams = QPushButton("Manage Teams")
        self.btn_manage_teams.clicked.connect(self.open_team_manager)
        top_grid.addWidget(self.btn_manage_teams, 0, 6)
        
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

        # Group 1: PvP
        vbox_pvp = QVBoxLayout()
        vbox_pvp.addWidget(self.check_pvp)
        vbox_pvp.addWidget(self.check_pve_only)
        cb_hbox.addLayout(vbox_pvp)

        # Move Pre 5px to the left (Gap 5->0 before, 15->20 after)
        cb_hbox.addSpacing(0) 
        
        # Group Pre: Adjust vertical offset by 11px
        vbox_pre = QVBoxLayout()
        vbox_pre.addSpacing(11)
        vbox_pre.addWidget(self.check_pre)
        vbox_pre.addStretch()
        cb_hbox.addLayout(vbox_pre)
        
        cb_hbox.addSpacing(20) 

        # Group 2: Elites
        vbox_elites = QVBoxLayout()
        vbox_elites.addWidget(self.check_elites_only)
        vbox_elites.addWidget(self.check_no_elites)
        cb_hbox.addLayout(vbox_elites)

        top_grid.addLayout(cb_hbox, 0, 7, 2, 3)

        # Col 10: Search Label (Moved Up)
        search_label_vbox = QVBoxLayout()
        search_label_vbox.setContentsMargins(0, 0, 0, 0)
        search_label_vbox.addWidget(QLabel("Search:"))
        search_label_vbox.addSpacing(15)
        top_grid.addLayout(search_label_vbox, 0, 10)
        
        # Col 11: Search Edit + Description Checkbox (Moved Down)
        search_vbox = QVBoxLayout()
        search_vbox.setSpacing(2)
        search_vbox.setContentsMargins(0, 0, 0, 0)
        search_vbox.addSpacing(10)
        
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Search skills...")
        self.edit_search.textChanged.connect(self.apply_filters)
        search_vbox.addWidget(self.edit_search)
        
        self.check_search_desc = QCheckBox("Description")
        self.check_search_desc.setStyleSheet("font-size: 10px; color: #aaa;")
        self.check_search_desc.toggled.connect(self.apply_filters)
        search_vbox.addWidget(self.check_search_desc)
        
        top_grid.addLayout(search_vbox, 0, 11)
        
        # --- Row 1: Export Controls + Maximize Button ---
        
        # Maximize Icons Button: Col 0 (Below Profession)
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
        top_grid.addWidget(self.btn_max_icons, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)

        # Add grid to main layout
        main_layout.addLayout(top_grid)
        
        # --- 2. Center Splitter ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # UPDATED: Pass engine to Library Widget
        self.library_widget = SkillLibraryWidget(parent=None, repo=self.repo, engine=self.engine)
        self.library_widget.skill_clicked.connect(self.handle_skill_id_clicked)
        self.library_widget.skill_double_clicked.connect(lambda sid: self.handle_skill_equipped_auto(sid))
        self.library_widget.builds_reordered.connect(self.handle_builds_reordered)
        self.splitter.addWidget(self.library_widget)
        
        self.info_panel = SkillInfoPanel()
        self.splitter.addWidget(self.info_panel)
        
        # Attribute Editor (Phase 2 & UI Polish)
        self.attr_editor = AttributeEditor()
        self.attr_editor.setMinimumWidth(100)
        self.attr_editor.attributes_changed.connect(self.on_attributes_changed)
        self.splitter.addWidget(self.attr_editor)
        
        # Set resize mode for splitter to make center/right panels stick but resizable
        # Index 0: Scroll Area (Stretch)
        # Index 1: Info Panel
        # Index 2: Attribute Editor
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 0)
        
        # Set initial sizes: [Flexible, Info: 255, Attr: 145]
        self.splitter.setSizes([800, 255, 145])
        
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
        bar_area_widget = QWidget()
        bar_area_layout = QVBoxLayout(bar_area_widget)
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
        container_layout.addWidget(bar_area_widget)
        container_layout.addSpacing(20) 
        
        # --- Control Layout (Right Side) ---
        control_layout = QVBoxLayout()
        
        self.check_show_others = QCheckBox("Show Other\nProfessions")
        self.check_show_others.toggled.connect(self.update_suggestions)
        control_layout.addWidget(self.check_show_others)

        self.check_lock_suggestions = QCheckBox("Lock")
        self.check_lock_suggestions.toggled.connect(self.update_suggestions)
        control_layout.addWidget(self.check_lock_suggestions)
        
        self.check_smart_mode = QCheckBox("Smart Mode\n(experimental)")
        self.check_smart_mode.setStyleSheet("color: #FFD700; font-weight: bold;")
        self.check_smart_mode.toggled.connect(self.on_smart_mode_toggled)
        control_layout.addWidget(self.check_smart_mode)

        container_layout.addLayout(control_layout)
        container_layout.addStretch(1)

        # --- Build Code Box (Rightmost) ---
        code_box = QFrame()
        code_box.setFixedWidth(250)
        code_layout = QVBoxLayout(code_box)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Build Code:"))
        
        self.lbl_prof_display = QLabel("X/X")
        self.lbl_prof_display.setStyleSheet("color: #888; font-weight: bold;")
        header_layout.addWidget(self.lbl_prof_display)
        
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
        container_layout.addWidget(code_box)
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
        dlg = TeamManagerDialog(self, self.engine)
        # Change button text to indicate synergy mode
        dlg.btn_load.setText("Load Team")
        dlg.btn_load.setToolTip("Load all skills from this team to use as synergy context")
        
        # Hide export button for smart mode context
        dlg.btn_export.setVisible(False)
        
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

    def open_team_manager(self):
        dlg = TeamManagerDialog(self, self.engine)
        dlg.exec()
        # Refresh team dropdown after dialog closes
        current_team = self.combo_team.currentText()
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
        
        idx = self.combo_team.findText(current_team)
        if idx != -1: self.combo_team.setCurrentIndex(idx)
        else: self.combo_team.setCurrentIndex(0)
        self.combo_team.blockSignals(False)

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
                
            self.engine = SynergyEngine(JSON_FILE)
            self.apply_filters()
            self.update_team_dropdown() 
            
            QMessageBox.information(self, "Success", "Build successfully imported into the synergy database!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save build: {e}")

    def reset_build(self):
        self.bar_skills = [None] * 8
        self.suggestion_offset = 0
        self.is_swapped = False
        
        self.reset_zone_mode()
        self.reset_team_mode()
        
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
        
        # Only auto-switch profession filter if we are NOT in a specific Team/Category view
        # This prevents the list from suddenly filtering out other members of the team
        current_team = self.combo_team.currentText()
        current_cat = self.combo_cat.currentText()
        should_switch_prof = (current_team == "All" and current_cat == "All")

        if primary_prof_id != 0 and should_switch_prof:
            for i in range(self.combo_prof.count()):
                text = self.combo_prof.itemText(i)
                if text.startswith(f"{primary_prof_id} -"):
                    self.combo_prof.setCurrentIndex(i)
                    break
        
        skills = build_data.get("skills", [])
        if len(skills) < 8:
            skills.extend([0] * (8 - len(skills)))
        skills = skills[:8]
        
        is_pvp = self.check_pvp.isChecked()
        
        for i, skill_id in enumerate(skills):
            if skill_id == 0:
                self.bar_skills[i] = None
                self.slots[i].clear_slot(silent=True)
            else:
                self.bar_skills[i] = skill_id
                skill_obj = self.repo.get_skill(skill_id, is_pvp=is_pvp)
                self.slots[i].set_skill(skill_id, skill_obj, ghost=False)

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

        prof_str = self.combo_prof.currentText()
        if prof_str == "All": prof = "All"
        else: prof = prof_str.split(' ')[0]

        cat = self.combo_cat.currentText()
        team = self.combo_team.currentText()
        search_text = self.edit_search.text().lower()

        # --- Mode Logic ---
        # 1. If NOT searching and Team/Cat selected -> Show Builds
        if not search_text:
            if team != "All":
                self.show_team_builds(team)
                return
            if cat != "All":
                self.show_category_builds(cat)
                return

        # 2. If Searching -> Search Global Skill DB (ignore Team/Cat restriction)
        #    Otherwise (All/All) -> Show Global Skill DB
        
        # Override context filters if searching
        target_team = "All" if search_text else team
        target_cat = "All" if search_text else cat

        # Gather filters
        filters = {
            'prof': prof,
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
        prof_str = self.combo_prof.currentText()
        if prof_str == "All":
            return builds
        
        target_prof_id = prof_str.split(' ')[0] # e.g. "1"
        
        filtered = []
        for b in builds:
            # Include if matches target OR if it is "X" (0) which indicates Any/Universal
            if b.primary_prof == target_prof_id or b.primary_prof == "0":
                filtered.append(b)
        return filtered

    def show_team_builds(self, team_name):
        self.library_widget.clear()
        self.library_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.library_widget.setSpacing(0)
        self.library_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        
        # Filter builds
        cat = self.combo_cat.currentText()
        matching_builds = [b for b in self.engine.builds if b.team == team_name]
        if cat != "All":
            matching_builds = [b for b in matching_builds if b.category == cat]
            
        matching_builds = self._apply_profession_filter(matching_builds)
            
        self._populate_build_list(matching_builds)

    def show_category_builds(self, category_name):
        self.library_widget.clear()
        self.library_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.library_widget.setSpacing(0)
        self.library_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        
        # Filter builds by category (team is "All")
        matching_builds = [b for b in self.engine.builds if b.category == category_name]
        
        # Filter by profession if needed
        matching_builds = self._apply_profession_filter(matching_builds)

        self._populate_build_list(matching_builds)

    def _populate_build_list(self, matching_builds):
        is_pvp = self.check_pvp.isChecked()
        for b in matching_builds:
            item = QListWidgetItem()
            # Match the new widget height: 130
            item.setSizeHint(QSize(500, 130)) 
            item.setData(Qt.ItemDataRole.UserRole, b)
            self.library_widget.addItem(item)
            
            widget = BuildPreviewWidget(b, self.repo, is_pvp=is_pvp)
            widget.clicked.connect(self.load_code)
            widget.skill_clicked.connect(self.handle_skill_clicked)
            widget.rename_clicked.connect(self.handle_build_rename) # NEW
            self.library_widget.setItemWidget(item, widget)

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
        
        # [REMOVED] self.lbl_loading.hide() <- This was causing your specific crash
        
        # Turn off updates briefly for insertion speed
        self.library_widget.setUpdatesEnabled(False)
        
        for skill in filtered_skills:
            item = QListWidgetItem(skill.name)
            item.setData(Qt.ItemDataRole.UserRole, skill.id)
            item.setData(Qt.ItemDataRole.DisplayRole, skill.name) # Explicitly set display role for delegate
            
            # Icon Loading
            cache_key = skill.icon_filename
            pix = None
            
            if cache_key in PIXMAP_CACHE:
                pix = PIXMAP_CACHE[cache_key]
            else:
                path = os.path.join(ICON_DIR, skill.icon_filename)
                if os.path.exists(path):
                    pix = QPixmap(path)
                    # Cache standard size
                    pix = pix.scaled(ICON_SIZE, ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
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

    def handle_skill_id_clicked(self, data):
        if isinstance(data, dict):
            self.info_panel.update_monster_info(data)
            return

        skill_id = data
        self.current_selected_skill_id = skill_id
        is_pvp = self.check_pvp.isChecked()
        skill = self.repo.get_skill(skill_id, is_pvp=is_pvp)
        if skill:
            dist = self.attr_editor.get_distribution()
            rank = dist.get(skill.attribute, 0)
            self.info_panel.update_info(skill, repo=self.repo, rank=rank)

    def handle_skill_equipped(self, index, skill_id):
        self.bar_skills[index] = skill_id
        self.suggestion_offset = 0 
        
        is_pvp = self.check_pvp.isChecked()
        skill_obj = self.repo.get_skill(skill_id, is_pvp=is_pvp)
        
        dist = self.attr_editor.get_distribution()
        rank = dist.get(skill_obj.attribute, 0) if skill_obj else 0
        
        self.slots[index].set_skill(skill_id, skill_obj, ghost=False, rank=rank)
        
        self.update_suggestions()

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
        dist = self.attr_editor.get_distribution()
        for i, sid in enumerate(self.bar_skills):
            if sid is not None:
                skill_obj = self.repo.get_skill(sid, is_pvp=is_pvp)
                rank = dist.get(skill_obj.attribute, 0) if skill_obj else 0
                self.slots[i].set_skill(sid, skill_obj, ghost=False, rank=rank)
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
        
        active_ids = [sid for sid in self.bar_skills if sid is not None]
        profs_in_bar = set()
        
        # 1. Add Primary Profession from Dropdown
        prof_text = self.combo_prof.currentText()
        if prof_text != "All":
            try:
                pid = int(prof_text.split(' ')[0])
                if pid != 0:
                    profs_in_bar.add(pid)
            except:
                pass

        # 2. Add Professions from Skills on Bar
        for sid in active_ids:
            if sid != 0:
                s = self.repo.get_skill(sid, is_pvp=is_pvp)
                if s and s.profession != 0:
                    profs_in_bar.add(s.profession)
        
        allowed_profs = set()
        enforce_prof_limit = False
        
        # Rule: Only enforce limit if we have 2+ professions determined AND user hasn't asked to show others.
        if not show_others:
            if len(profs_in_bar) >= 2:
                enforce_prof_limit = True
                allowed_profs.update(profs_in_bar)
                allowed_profs.add(0) # Always allow Common

        # Prepare team spirit set for fast lookup
        team_spirit_ids = set()
        if hasattr(self, 'check_smart_mode') and self.check_smart_mode.isChecked():
            # Find which IDs in team synergy context are spirits
            # We can do this once per batch or just check in the loop
            pass

        print(f"[UI] Suggestions received: {len(suggestions)}")
        filtered_count = 0

        for item in suggestions:
            if len(item) == 3:
                sid, conf, reason = item
            else:
                sid, conf = item
                reason = None

            if sid == 0: continue

            skill = self.repo.get_skill(sid, is_pvp=is_pvp)
            if not skill: continue
            
            if is_pvp and skill.is_pve_only: continue
            
            if enforce_prof_limit:
                if skill.profession not in allowed_profs:
                    filtered_count += 1
                    continue
            
            # --- SPIRIT REDUNDANCY EXCEPTION ---
            # If in Smart Mode with a team context, don't suggest spirits already in that context
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
            
        # Clean up existing thread if running
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            
        active_ids = [sid for sid in self.bar_skills if sid is not None]
        
        # Always include the loaded team context if available (Active Team Mode)
        bar_set = set(active_ids)
        for sid in self.team_synergy_skills:
            if sid not in bar_set:
                active_ids.append(sid)

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

        # ALWAYS use self.engine (Neural/Hybrid)
        self.worker = SynergyWorker(self.engine, active_ids, pid, mode, debug=is_debug, is_pre=is_pre, allowed_campaigns=allowed_campaigns, is_pvp=is_pvp)
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
        dist = self.attr_editor.get_distribution()
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
                rank = dist.get(skill_obj.attribute, 0) if skill_obj else 0
                slot.set_skill(s_id, skill_obj, ghost=True, confidence=display_val, rank=rank)
                s_idx += 1
            else:
                # Ran out of suggestions? Clear the slot.
                slot.clear_slot(silent=True)
                
        self.update_build_code()

    def on_attributes_changed(self, distribution):
        self.update_build_code()
        # Phase 3: Refresh skill tooltips/displays
        self.refresh_skill_displays()

    def refresh_skill_displays(self):
        is_pvp = self.check_pvp.isChecked()
        dist = self.attr_editor.get_distribution()
        
        # Refresh equipped skills
        for i, sid in enumerate(self.bar_skills):
            if sid is not None:
                skill_obj = self.repo.get_skill(sid, is_pvp=is_pvp)
                rank = dist.get(skill_obj.attribute, 0) if skill_obj else 0
                self.slots[i].set_skill(sid, skill_obj, ghost=False, rank=rank)
                
        # Refresh info panel
        if self.current_selected_skill_id is not None:
            skill_obj = self.repo.get_skill(self.current_selected_skill_id, is_pvp=is_pvp)
            if skill_obj:
                rank = dist.get(skill_obj.attribute, 0)
                self.info_panel.update_info(skill_obj, repo=self.repo, rank=rank)

        # Refresh suggestions (this will call display_suggestions)
        self.display_suggestions()

    def swap_professions(self):
        self.is_swapped = not self.is_swapped
        self.update_build_code()

    def update_build_code(self):
        active_bar = [s if s is not None else 0 for s in self.bar_skills]
        
        profs_in_bar = set()
        for sid in active_bar:
            if sid != 0:
                s = self.repo.get_skill(sid)
                if s and s.profession != 0:
                    profs_in_bar.add(s.profession)
        
        primary_id = 0
        secondary_id = 0
        
        try: 
            combo_val = int(self.combo_prof.currentText().split(' ')[0])
            if combo_val != 0:
                primary_id = combo_val
        except:
            pass
        
        profs_sorted = sorted(list(profs_in_bar))
        
        if primary_id == 0:
            if len(profs_sorted) >= 1: primary_id = profs_sorted[0]
        
        for pid in profs_sorted:
            if pid != primary_id:
                secondary_id = pid
                break
        
        if self.is_swapped:
            primary_id, secondary_id = secondary_id, primary_id
            
        p1_name = PROF_MAP.get(primary_id, "No Profession")
        p2_name = PROF_MAP.get(secondary_id, "No Profession")
        p1_str = PROF_SHORT_MAP.get(p1_name, "X")
        p2_str = PROF_SHORT_MAP.get(p2_name, "X")
        
        self.lbl_prof_display.setText(f"{p1_str}/{p2_str}")
        
        # Check uniqueness visibility
        active_count = sum(1 for s in active_bar if s != 0)
        if hasattr(self, 'btn_check_unique'):
            self.btn_check_unique.setVisible(active_count == 8)
        
        # Collect active skill objects for PvE attribute detection
        active_skill_objs = []
        pve_attr_ids = set()
        for sid in active_bar:
            if sid != 0:
                s = self.repo.get_skill(sid)
                if s: 
                    active_skill_objs.append(s)
                    if s.attribute < 0 and s.attribute != -1:
                        pve_attr_ids.add(s.attribute)

        # Update Attribute Editor professions ONLY if needed to prevent recursion
        current_state = (primary_id, secondary_id, frozenset(pve_attr_ids))
        
        if current_state != self._last_attr_state:
            self.attr_editor.set_professions(primary_id, secondary_id, active_skill_objs)
            self._last_attr_state = current_state

        # Get actual ranks from editor for the build code
        dist = self.attr_editor.get_distribution()
        attributes = []
        for aid, rank in dist.items():
            if rank > 0:
                attributes.append([aid, rank])

        data = {
            "header": {"type": 14, "version": 0},
            "profession": {"primary": primary_id, "secondary": secondary_id},
            "attributes": attributes,
            "skills": active_bar
        }
        
        try:
            live_code = GuildWarsTemplateEncoder(data).encode()
            self.edit_code.setText(live_code)
        except:
            pass

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
        
        dlg = BuildUniquenessDialog(matches, len(self.engine.builds), self)
        dlg.exec()

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
