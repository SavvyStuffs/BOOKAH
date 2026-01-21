import os
import json
import random
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from src.constants import resource_path

SHARE_CODES_FILE = "sharecodes.json"
CLOUDFLARE_URL = "https://sharecodes-api.savvystuff682.workers.dev"

class ShareCodeManager:
    def __init__(self, root_path="."):
        self.root_path = root_path
        self.prefixes = []
        self.suffixes = []
        self.load_codes()

    def load_codes(self):
        # Use resource_path to find the file in the bundle
        path = resource_path(SHARE_CODES_FILE)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.prefixes = data.get("prefixes", [])
                    self.suffixes = data.get("suffixes", [])
            except Exception as e:
                print(f"Error loading share codes: {e}")

    def generate_candidate(self, attempt=0):
        # Fallback to Prefix + Suffix
        if self.prefixes and self.suffixes:
            p = random.choice(self.prefixes)
            s = random.choice(self.suffixes)
            return f"{p}{s}"
            
        # Fallback if empty
        return f"Build{random.randint(1000,9999)}"

    def is_valid_code(self, code):
        """Checks if the code is composed of a valid prefix and suffix."""
        if not code or not self.prefixes or not self.suffixes:
            return False
            
        # Check against all prefixes
        for p in self.prefixes:
            if code.startswith(p):
                # If prefix matches, check if the remainder is a valid suffix
                remainder = code[len(p):]
                if remainder in self.suffixes:
                    return True
        return False

class ShareWorker(QThread):
    # Signals
    code_generated = pyqtSignal(str) # Emits a unique code found
    upload_success = pyqtSignal(str) # Emits the code on success
    download_success = pyqtSignal(dict) # Emits the team data
    error = pyqtSignal(str)

    def __init__(self, manager, operation, **kwargs):
        super().__init__()
        self.manager = manager
        self.operation = operation # "generate", "upload", "download"
        self.kwargs = kwargs

    def run(self):
        if self.operation == "generate":
            self._find_unique_code()
        elif self.operation == "upload":
            self._upload_team()
        elif self.operation == "download":
            self._download_team()

    def _find_unique_code(self):
        max_retries = 10
        for i in range(max_retries):
            candidate = self.manager.generate_candidate(i)
            if self._check_availability(candidate):
                self.code_generated.emit(candidate)
                return
        self.error.emit("Could not find a unique code after multiple attempts.")

    def _check_availability(self, code):
        try:
            # The worker endpoint likely expects a GET to check or we try to get it and see if 404
            # Usually: GET /<code> returns 200 (Found) or 404 (Not Found)
            # If 404, it is available for taking.
            resp = requests.get(f"{CLOUDFLARE_URL}/{code}", timeout=5)
            if resp.status_code == 404:
                return True # Available
            return False # Taken or Error
        except Exception:
            return False # Assume unavailable on error to be safe

    def _upload_team(self):
        code = self.kwargs.get('code')
        team_data = self.kwargs.get('data')
        
        if not code or not team_data:
            self.error.emit("Missing data for upload.")
            return

        try:
            # POST to root with {"code": code, "data": data} structure
            # Matching Worker logic: const { code, data } = await request.json();
            payload = {
                "code": code,
                "data": team_data
            }
            headers = {"Content-Type": "application/json"}
            resp = requests.post(CLOUDFLARE_URL, json=payload, headers=headers, timeout=10)
            
            if resp.status_code in [200, 201]:
                self.upload_success.emit(code)
            elif resp.status_code == 429:
                self.error.emit("Too many requests! Cant keep up!")
            else:
                self.error.emit(f"Server returned {resp.status_code}: {resp.text}")
        except Exception as e:
            self.error.emit(str(e))

    def _download_team(self):
        code = self.kwargs.get('code')
        if not code:
            self.error.emit("No code provided.")
            return

        try:
            resp = requests.get(f"{CLOUDFLARE_URL}/{code}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.download_success.emit(data)
            elif resp.status_code == 404:
                self.error.emit("Code not found.")
            elif resp.status_code == 429:
                self.error.emit("Too many requests! Cant keep up!")
            else:
                self.error.emit(f"Error {resp.status_code}")
        except Exception as e:
            self.error.emit(str(e))
