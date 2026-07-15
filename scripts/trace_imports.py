import os
import sys
import importlib
import traceback
from pathlib import Path

root_dir = Path("E:/YouTube/FluentYTDL/src")
sys.path.insert(0, str(root_dir))

modules = [
    "fluentytdl.ui.reimagined_main_window",
    "fluentytdl.ui.settings_page",
    "fluentytdl.ui.components.download_config_window",
    "fluentytdl.ui.components.rate_limit",
    "fluentytdl.ui.components.settings_cards",
    "fluentytdl.ui.components.smart_setting_card",
    "fluentytdl.ui.dialogs.playlist_subtitle_dialog"
]

for mod in modules:
    try:
        importlib.import_module(mod)
        print(f"Successfully imported {mod}")
    except Exception as e:
        print(f"\n--- {mod} ---")
        traceback.print_exc()
