import sys
import os
import platform
if platform.system() == 'Linux':
    print("[Linux] Detecting environment...")

    os.environ["QT_QPA_PLATFORM"] = "xcb"
    
    # 2. DISABLE GPU ACCELERATION
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
    
    # 3. DISABLE SANDBOX 
    os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
    
    print("[Linux] Applied stability patches: XCB backend forced, GPU disabled.")
from PyQt6.QtWidgets import QApplication, QSplashScreen, QProxyStyle, QStyle
from PyQt6.QtGui import QPixmap, QCursor, QIcon
from PyQt6.QtCore import Qt, QTimer
from src.ui.main_window import MainWindow
from src.constants import resource_path, JSON_FILE, DB_FILE
from src.engine import SynergyEngine 

class TooltipProxyStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return 350
        return super().styleHint(hint, option, widget, returnData)

if __name__ == "__main__":
    # Fix Taskbar Icon on Windows
    if sys.platform == 'win32':
        import ctypes
        myappid = 'bookah.builder.gui.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyle(TooltipProxyStyle(app.style()))
    
    # --- Crash Handler ---
    def crash_handler(exctype, value, tb):
        # Ignore KeyboardInterrupt
        if issubclass(exctype, KeyboardInterrupt):
            sys.__excepthook__(exctype, value, tb)
            return

        from src.crash_reporter import CrashReporter
        print("Crash detected! Launching reporter...")
        # Ensure stderr still gets it
        sys.__excepthook__(exctype, value, tb)
        
        reporter = CrashReporter(exctype, value, tb)
        reporter.exec()
        sys.exit(1)

    sys.excepthook = crash_handler
    # ---------------------
    
    # App Icon
    icon_path = resource_path(os.path.join("icons", "bookah_icon.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Splash Screen
    logo_path = resource_path(os.path.join("icons", "bookah_logo.png"))
    pixmap = QPixmap(logo_path)
    
    if not pixmap.isNull():
        pixmap = pixmap.scaled(
            600, 
            600, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
    
    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    
    # Center on current screen (where mouse is)
    screen = app.screenAt(QCursor.pos())
    if screen:
        geo = screen.geometry()
        x = geo.x() + (geo.width() - pixmap.width()) // 2
        y = geo.y() + (geo.height() - pixmap.height()) // 2
        splash.move(x, y)
    
    splash.show()
    app.processEvents()
    
    # Load Engine
    print("Loading Synergy Engine...")
    synergy_engine = SynergyEngine(JSON_FILE, DB_FILE)
    
    # Initialize Main Window
    window = MainWindow(engine=synergy_engine)
    
    def show_main():
        window.show()
        splash.finish(window)
        
    # Splash screen display timing
    QTimer.singleShot(2000, show_main)
    
    sys.exit(app.exec())
