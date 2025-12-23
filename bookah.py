import sys
import os
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QCursor, QIcon
from PyQt6.QtCore import Qt, QTimer
from src.ui.main_window import MainWindow
from src.constants import resource_path

if __name__ == "__main__":
    # Fix Taskbar Icon on Windows
    if sys.platform == 'win32':
        import ctypes
        myappid = 'bookah.builder.gui.1.0' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # App Icon
    icon_path = resource_path("icons/bookah_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Splash Screen
    logo_path = resource_path("icons/bookah_logo.png")
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
    
    # Initialize Main Window (Load DB, etc.)
    window = MainWindow()
    
    # Function to show main window and close splash
    def show_main():
        window.show()
        splash.finish(window)
        
    # Enforce minimum 4 second splash
    QTimer.singleShot(4000, show_main)
    
    sys.exit(app.exec())