import sys
import traceback
import urllib.request
import urllib.parse
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Google Form Configuration
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSczwQqgP6s6pAPb4zd0bQfy9U8-sXzdSBvyEmST6jUS0peqQg/formResponse"
ENTRY_CRASH_LOG = "entry.1632008158"
ENTRY_USER_INPUT = "entry.58950737"

class CrashWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, crash_log, user_comment):
        super().__init__()
        self.crash_log = crash_log
        self.user_comment = user_comment

    def run(self):
        try:
            data = {
                ENTRY_CRASH_LOG: self.crash_log,
                ENTRY_USER_INPUT: self.user_comment
            }
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(FORM_URL, data=encoded_data)
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    self.finished.emit(True, "Report sent successfully.")
                else:
                    self.finished.emit(False, f"HTTP Error: {response.status}")
        except Exception as e:
            self.finished.emit(False, str(e))

class CrashReporter(QDialog):
    def __init__(self, exctype, value, tb):
        super().__init__()
        self.setWindowTitle("Crash Report")
        self.resize(500, 400)
        self.setModal(True)
        
        # Format Traceback
        self.traceback_text = "".join(traceback.format_exception(exctype, value, tb))
        
        layout = QVBoxLayout(self)
        
        lbl_title = QLabel("<b>Application Crashed</b>")
        lbl_title.setStyleSheet("font-size: 14pt; color: #FF4444;")
        layout.addWidget(lbl_title)
        
        lbl_desc = QLabel("We apologize for the inconvenience. Please send this crash report to help us fix the issue.")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)
        
        layout.addWidget(QLabel("Additional Comments (Optional):"))
        self.edit_comments = QTextEdit()
        self.edit_comments.setPlaceholderText("What were you doing when it crashed?")
        self.edit_comments.setMaximumHeight(80)
        layout.addWidget(self.edit_comments)
        
        layout.addWidget(QLabel("Crash Log:"))
        self.edit_log = QTextEdit()
        self.edit_log.setPlainText(self.traceback_text)
        self.edit_log.setReadOnly(True)
        self.edit_log.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt; background-color: #222; color: #EEE;")
        layout.addWidget(self.edit_log)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        btn_layout = QHBoxLayout()
        self.btn_send = QPushButton("Send Report")
        self.btn_send.setStyleSheet("background-color: #0078D7; color: white; font-weight: bold; padding: 6px;")
        self.btn_send.clicked.connect(self.send_report)
        btn_layout.addWidget(self.btn_send)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)

    def send_report(self):
        self.btn_send.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0) # Indeterminate
        
        self.worker = CrashWorker(self.traceback_text, self.edit_comments.toPlainText())
        self.worker.finished.connect(self.on_sent)
        self.worker.start()

    def on_sent(self, success, message):
        self.progress.setVisible(False)
        if success:
            QMessageBox.information(self, "Success", "Crash report sent. Thank you!")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to send report:\n{message}")
            self.btn_send.setEnabled(True)
