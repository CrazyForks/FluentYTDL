from __future__ import annotations

from qfluentwidgets import InfoBar as _FluentInfoBar
from qfluentwidgets import isDarkTheme


class InfoBar:
    """Wrapper around qfluentwidgets InfoBar to fix ugly colors in dark mode."""

    @staticmethod
    def _apply_custom_style(widget):
        # Fix the "big chin" issue by overriding default min-height
        widget.setStyleSheet(
            widget.styleSheet()
            + """
            InfoBar, SuccessInfoBar, ErrorInfoBar, WarningInfoBar, InfoInfoBar {
                min-height: 36px !important;
            }
            """
        )
        if isDarkTheme():
            # A more professional dark mode color palette for InfoBars
            widget.setStyleSheet(
                widget.styleSheet()
                + """
                SuccessInfoBar { background-color: rgba(30, 46, 30, 0.95) !important; border: 1px solid rgba(45, 66, 45, 1) !important; }
                SuccessInfoBar QLabel { color: #d1ffd1 !important; }
                
                ErrorInfoBar { background-color: rgba(46, 30, 30, 0.95) !important; border: 1px solid rgba(66, 45, 45, 1) !important; }
                ErrorInfoBar QLabel { color: #ffd1d1 !important; }
                
                WarningInfoBar { background-color: rgba(46, 42, 30, 0.95) !important; border: 1px solid rgba(66, 60, 45, 1) !important; }
                WarningInfoBar QLabel { color: #ffeed1 !important; }
                
                InfoInfoBar { background-color: rgba(30, 30, 46, 0.95) !important; border: 1px solid rgba(45, 45, 66, 1) !important; }
                InfoInfoBar QLabel { color: #d1d1ff !important; }
            """
            )

        # Optional layout tweak for vertically centering text if there's still a chin
        try:
            from PySide6.QtCore import Qt

            if hasattr(widget, "textLayout"):
                widget.textLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        except Exception:
            pass

        return widget

    @staticmethod
    def success(*args, **kwargs):
        return InfoBar._apply_custom_style(_FluentInfoBar.success(*args, **kwargs))

    @staticmethod
    def error(*args, **kwargs):
        return InfoBar._apply_custom_style(_FluentInfoBar.error(*args, **kwargs))

    @staticmethod
    def warning(*args, **kwargs):
        return InfoBar._apply_custom_style(_FluentInfoBar.warning(*args, **kwargs))

    @staticmethod
    def info(*args, **kwargs):
        return InfoBar._apply_custom_style(_FluentInfoBar.info(*args, **kwargs))
