import os
import sys
import json
import shutil
import subprocess
import requests
import zipfile
import tempfile
import time
from packaging import version
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from src.constants import resource_path

class UpdateChecker(QObject):
    update_available = pyqtSignal(str, str) # version, url
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

        try:
            response = requests.get(self.version_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            remote_version = data.get('version')
            download_url = data.get('download_url')

            if remote_version and download_url and version.parse(remote_version) > version.parse(self.current_version):
                self.update_available.emit(remote_version, download_url)
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
            local_filename = os.path.join(temp_dir, "bookah_update.zip")
            
            with requests.get(self.url, stream=True) as r:
                r.raise_for_status()
                total_length = r.headers.get('content-length')
                
                with open(local_filename, 'wb') as f:
                    if total_length is None: # no content length header
                        f.write(r.content)
                    else:
                        dl = 0
                        total_length = int(total_length)
                        for chunk in r.iter_content(chunk_size=8192):
                            dl += len(chunk)
                            f.write(chunk)
                            done = int(50 * dl / total_length)
                            self.progress.emit(done)
                            
            self.finished.emit(local_filename)
        except Exception as e:
            self.error.emit(str(e))

def install_and_restart(zip_path):
    """
    1. Extracts zip to a temp folder.
    2. Creates a bat script.
    3. Runs bat script and exits app.
    """
    # Current executable path
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        exe_name = os.path.basename(sys.executable)
    else:
        app_dir = os.getcwd()
        exe_name = "bookah.py" # Fallback for dev

    # Extract zip
    extract_path = os.path.join(tempfile.gettempdir(), "bookah_extracted")
    if os.path.exists(extract_path):
        shutil.rmtree(extract_path)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

    # If the zip contains a root folder (e.g. Bookah/), adjust path
    items = os.listdir(extract_path)
    if len(items) == 1 and os.path.isdir(os.path.join(extract_path, items[0])):
        source_dir = os.path.join(extract_path, items[0])
    else:
        source_dir = extract_path

    # Create Batch Script
    bat_path = os.path.join(tempfile.gettempdir(), "update_bookah.bat")
    
    # We use 'timeout' to give the app time to close
    # We use 'xcopy' /E /Y to overwrite all files
    # We restart the app
    bat_content = f"""
@echo off
timeout /t 2 /nobreak > NUL
echo Updating Bookah...
xcopy "{source_dir}" "{app_dir}" /E /H /Y /C
echo Cleaning up...
rmdir /s /q "{extract_path}"
del "{zip_path}"
echo Restarting...
start "" "{os.path.join(app_dir, exe_name)}"
del "%~f0"
"""
    
    with open(bat_path, 'w') as f:
        f.write(bat_content)

    # Launch batch file and exit
    subprocess.Popen([bat_path], shell=True)
    sys.exit(0)
