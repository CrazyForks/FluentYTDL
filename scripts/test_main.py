import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Initialize app
app = QApplication(sys.argv)

# Setup language EXACTLY as main.py does
from fluentytdl.core.i18n import TranslationManager
from qfluentwidgets import Language
TranslationManager.load_language(Language.ENGLISH_US, app)

# Load MainWindow to trigger settings page initialization
from fluentytdl.ui.main_window import MainWindow
window = MainWindow()

# We don't call app.exec() to exit immediately after initialization
print("MainWindow initialized.")
