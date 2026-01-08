from PyQt6.QtGui import QColor, QPalette, QGuiApplication
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# --- COLOR DEFINITIONS ---
DARK_PALETTE = {
    "bg_primary": "#111111",
    "bg_secondary": "#222222",
    "bg_tertiary": "#1a1a1a",
    "bg_hover": "#333333",
    "bg_selected": "#2a2a2a",
    
    "border": "#444444",
    "border_light": "#666666",
    "border_accent": "#00AAFF",
    "border_focus": "#00AAFF",
    
    "text_primary": "#FFFFFF",
    "text_secondary": "#CCCCCC",
    "text_tertiary": "#AAAAAA",
    "text_accent": "#00AAFF",
    "text_warning": "#FFD700",
    "text_link": "#00AAFF",
    
    "slot_border": "#555555",
    "slot_border_hover": "#666666",
    "slot_bg": "#1a1a1a",
    "slot_bg_equipped": "#2a2a2a",
    "slot_bg_drag": "#222222",
    
    "btn_bg": "#444444",
    "btn_bg_hover": "#555555",
    "btn_text": "#FFFFFF",
    
    "input_bg": "#222222",
    "input_text": "#00AAFF",
    
    "tooltip_bg": "#222222",
    "tooltip_text": "#FFFFFF"
}

LIGHT_PALETTE = {
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F0F0F0",
    "bg_tertiary": "#E0E0E0",
    "bg_hover": "#D0D0D0",
    "bg_selected": "#D0E8FF",
    
    "border": "#CCCCCC",
    "border_light": "#AAAAAA",
    "border_accent": "#0066CC",
    "border_focus": "#0066CC",
    
    "text_primary": "#000000",
    "text_secondary": "#333333",
    "text_tertiary": "#555555",
    "text_accent": "#0066CC",
    "text_warning": "#CC8800",
    "text_link": "#0066CC",
    
    "slot_border": "#AAAAAA",
    "slot_border_hover": "#888888",
    "slot_bg": "#F5F5F5",
    "slot_bg_equipped": "#E0E0E0",
    "slot_bg_drag": "#EEEEEE",
    
    "btn_bg": "#E0E0E0",
    "btn_bg_hover": "#D0D0D0",
    "btn_text": "#000000",
    
    "input_bg": "#FFFFFF",
    "input_text": "#0066CC",

    "tooltip_bg": "#D0D0D0",
    "tooltip_text": "#000000"
}

# Current Active Theme (Starts with Dark as default match)
CURRENT_THEME = DARK_PALETTE.copy()

def get_color(key):
    return CURRENT_THEME.get(key, "#FF00FF") # Magenta fallback

def update_theme(mode):
    """
    Updates CURRENT_THEME and returns a QPalette for the application.
    mode: 'Dark', 'Light', or 'Auto'
    """
    global CURRENT_THEME
    
    is_dark = True
    if mode == "Light":
        is_dark = False
    elif mode == "Auto":
        # Check system setting via styleHints (Qt 6.5+)
        # This is more reliable than checking the palette we might have already overridden
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Light:
                is_dark = False
        except:
            # Fallback for older Qt versions or if detection fails
            # Default to Dark as it's the "native" look of this app
            is_dark = True
    
    if is_dark:
        CURRENT_THEME.clear()
        CURRENT_THEME.update(DARK_PALETTE)
        return _get_dark_qpalette()
    else:
        CURRENT_THEME.clear()
        CURRENT_THEME.update(LIGHT_PALETTE)
        return _get_light_qpalette()

def _get_dark_qpalette():
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(CURRENT_THEME["bg_secondary"]))
    p.setColor(QPalette.ColorRole.WindowText, QColor(CURRENT_THEME["text_primary"]))
    p.setColor(QPalette.ColorRole.Base, QColor(CURRENT_THEME["bg_primary"]))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(CURRENT_THEME["bg_tertiary"]))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(CURRENT_THEME["tooltip_bg"]))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(CURRENT_THEME["tooltip_text"]))
    p.setColor(QPalette.ColorRole.Text, QColor(CURRENT_THEME["text_primary"]))
    p.setColor(QPalette.ColorRole.Button, QColor(CURRENT_THEME["btn_bg"]))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(CURRENT_THEME["btn_text"]))
    p.setColor(QPalette.ColorRole.BrightText, QColor(CURRENT_THEME["text_warning"]))
    p.setColor(QPalette.ColorRole.Link, QColor(CURRENT_THEME["text_link"]))
    p.setColor(QPalette.ColorRole.Highlight, QColor(CURRENT_THEME["border_accent"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
    return p

def _get_light_qpalette():
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(CURRENT_THEME["bg_secondary"]))
    p.setColor(QPalette.ColorRole.WindowText, QColor(CURRENT_THEME["text_primary"]))
    p.setColor(QPalette.ColorRole.Base, QColor(CURRENT_THEME["bg_primary"]))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(CURRENT_THEME["bg_tertiary"]))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(CURRENT_THEME["tooltip_bg"]))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(CURRENT_THEME["tooltip_text"]))
    p.setColor(QPalette.ColorRole.Text, QColor(CURRENT_THEME["text_primary"]))
    p.setColor(QPalette.ColorRole.Button, QColor(CURRENT_THEME["btn_bg"]))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(CURRENT_THEME["btn_text"]))
    p.setColor(QPalette.ColorRole.BrightText, QColor(CURRENT_THEME["text_warning"]))
    p.setColor(QPalette.ColorRole.Link, QColor(CURRENT_THEME["text_link"]))
    p.setColor(QPalette.ColorRole.Highlight, QColor(CURRENT_THEME["border_accent"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    return p
