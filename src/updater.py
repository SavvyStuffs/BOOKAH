import os
import sys
import json
import subprocess
import requests
import tempfile
import time
from packaging import version
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from src.constants import resource_path

class UpdateCheckWorker(QThread):
    result = pyqtSignal(object) # (version, url, notes) or None
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
    update_available = pyqtSignal(str, str, str) # version, url, release_notes
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
            # Static URL as requested
            download_url = "https://bookah.savvy-stuff.dev/Bookah_Setup.exe"
            release_notes = data.get('updates', "No release notes available.")

            if remote_version and version.parse(remote_version) > version.parse(self.current_version):
                self.update_available.emit(remote_version, download_url, release_notes)
            else:
                self.no_update.emit()
        except Exception as e:
            self.error.emit(str(e))

class UpdateDownloader(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str) # path to downloaded file
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            temp_dir = tempfile.gettempdir()
            
            # Extract filename from URL (e.g., BookahSetup.exe)
            filename = self.url.split('/')[-1].split('?')[0]
            if not filename:
                filename = "BookahSetup.exe"
            
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
                            
            self.finished.emit(local_filename)
        except Exception as e:
            self.error.emit(str(e))

def install_and_restart(file_path):
    """
    Launches the external installer and exits the current application.
    This allows the installer to overwrite files that would otherwise be 'in use'.
    """
    try:
        if sys.platform == 'win32':
            # os.startfile handles UAC elevation prompts correctly for installers
            os.startfile(file_path)
        else:
            # For Linux/macOS (if applicable)
            subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', file_path])
        
        # Exit application immediately
        sys.exit(0)
    except Exception as e:
        print(f"Error launching installer: {e}")
        # We don't exit if launch failed, so the user can see the error