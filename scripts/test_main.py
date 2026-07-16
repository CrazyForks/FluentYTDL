import sys

from PySide6.QtWidgets import QApplication

# Initialize app
app = QApplication(sys.argv)

# Setup language EXACTLY as main.py does
from qfluentwidgets import Language  # noqa: E402

from fluentytdl.core.i18n import TranslationManager  # noqa: E402

TranslationManager.load_language(Language.ENGLISH_US, app)

# Load MainWindow to trigger settings page initialization
from fluentytdl.ui.main_window import MainWindow  # noqa: E402

window = MainWindow()

# We don't call app.exec() to exit immediately after initialization
print("MainWindow initialized.")
