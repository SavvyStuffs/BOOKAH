import sys
import os
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QCursor, QIcon
from PyQt6.QtCore import Qt, QTimer
from src.ui.main_window import MainWindow
from src.constants import resource_path, JSON_FILE, DB_FILE
from src.engine import SynergyEngine 

if __name__ == "__main__":
    # Fix Taskbar Icon on Windows
    if sys.platform == 'win32':
        import ctypes
        myappid = 'bookah.builder.gui.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
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
    
    # --- LOAD ENGINE WHILE SPLASH IS SHOWING ---
    print("Loading Synergy Engine...")
    # This trains the neural net if needed
    synergy_engine = SynergyEngine(JSON_FILE, DB_FILE)
    
    # Initialize Main Window with the loaded engine
    window = MainWindow(engine=synergy_engine)
    
    def show_main():
        window.show()
        splash.finish(window)
        
    # Enforce minimum 2 second splash (or until loaded)
    # Since loading happens synchronously above, the timer starts AFTER load.
    # So 100ms is fine just to yield UI loop, but user wanted "splash screen visible".
    # We can use 2000ms to be safe/nice.
    QTimer.singleShot(2000, show_main)
    
    sys.exit(app.exec())
