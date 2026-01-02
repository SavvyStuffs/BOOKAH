import os
import sys
import json
import subprocess
import requests
import tempfile
import time
import platform # Added for better OS detection
from packaging import version
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from src.constants import resource_path

class UpdateCheckWorker(QThread):
    result = pyqtSignal(object) 
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            # Add cache-busting timestamp
            url_with_ts = f"{self.url}?t={int(time.time())}"
            response = requests.get(url_with_ts, timeout=10)
            response.raise_for_status()
            self.result.emit(response.json())
        except Exception as e:
            self.error.emit(str(e))

class UpdateChecker(QObject):
    update_available = pyqtSignal(str, str, str)
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.current_version = "0.0.0"
        self.version_url = ""
        self._load_version_info()

    def _load_version_info(self):
        try:
            version_path = resource_path('version.json')
            with open(version_path, 'r') as f:
                data = json.load(f)
                self.current_version = data.get('version', "0.0.0")
                self.version_url = data.get('version_url', "")
        except Exception as e:
            print(f"Error loading version info: {e}")

    def check(self):
        if not self.version_url:
            self.error.emit("No version URL found.")
            return

        self.worker = UpdateCheckWorker(self.version_url)
        self.worker.result.connect(self._on_result)
        self.worker.error.connect(self.error)
        self.worker.start()

    def _on_result(self, data):
        try:
            remote_version = data.get('version')
            
            # --- FIX 1: OS-Dependent Download Link ---
            base_url = "https://bookah.savvy-stuff.dev"
            if sys.platform == 'win32':
                download_url = f"{base_url}/Bookah_Setup.exe"
            else:
                # Assuming you will name your zip this. 
                # If you use version numbers in filenames, update logic here.
                download_url = f"{base_url}/Bookah_Linux.zip"
            # -----------------------------------------

            release_notes = data.get('updates', "No release notes available.")

            if remote_version and version.parse(remote_version) > version.parse(self.current_version):
                self.update_available.emit(remote_version, download_url, release_notes)
            else:
                self.no_update.emit()
        except Exception as e:
            self.error.emit(str(e))

class UpdateDownloader(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            temp_dir = tempfile.gettempdir()
            
            filename = self.url.split('/')[-1].split('?')[0]
            if not filename:
                # Fallback names based on platform
                filename = "Bookah_Setup.exe" if sys.platform == 'win32' else "Bookah_Linux.zip"
            
            local_filename = os.path.join(temp_dir, filename)
            
            with requests.get(self.url, stream=True) as r:
                r.raise_for_status()
                total_length = r.headers.get('content-length')
                
                with open(local_filename, 'wb') as f:
                    if total_length is None:
                        f.write(r.content)
                    else:
                        dl = 0
                        total_length = int(total_length)
                        for chunk in r.iter_content(chunk_size=8192):
                            dl += len(chunk)
                            f.write(chunk)
                            done = int(100 * dl / total_length)
                            self.progress.emit(done)

            # --- FIX 2: Grant Execute Permissions (Linux) ---
            # Even if it's a zip, good practice. If it were an AppImage, this is mandatory.
            if sys.platform != 'win32':
                try:
                    st = os.stat(local_filename)
                    os.chmod(local_filename, st.st_mode | 0o111)
                except:
                    pass # Ignore permission errors in temp
            # ------------------------------------------------
                            
            self.finished.emit(local_filename)
        except Exception as e:
            self.error.emit(str(e))

def install_and_restart(file_path):
    """
    Windows: Launches installer and exits.
    Linux: Opens the file location (Zip) and keeps app open for manual instructions.
    """
    try:
        if sys.platform == 'win32':
            os.startfile(file_path)
            sys.exit(0) # Only exit on Windows where the installer takes over
        else:
            # --- FIX 3: Linux "Manual Assist" Mode ---
            # We open the folder containing the zip so the user can see it.
            # We do NOT exit, because the user hasn't installed it yet.
            if sys.platform == 'darwin':
                subprocess.Popen(['open', '--reveal', file_path])
            else:
                # Linux: Try to highlight file, otherwise just open folder
                folder_path = os.path.dirname(file_path)
                subprocess.Popen(['xdg-open', folder_path])
            
            # Optional: You could emit a signal here to show a popup saying:
            # "Update downloaded! Please extract the zip to upgrade."
            
    except Exception as e:
        print(f"Error launching installer: {e}")