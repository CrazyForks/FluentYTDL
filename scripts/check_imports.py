import importlib
import sys
from pathlib import Path

# Add src to sys.path
root_dir = Path("E:/YouTube/FluentYTDL/src")
sys.path.insert(0, str(root_dir))

ui_dir = root_dir / 'fluentytdl' / 'ui'
for py_file in ui_dir.rglob('*.py'):
    if py_file.name == '__init__.py':
        continue
        
    rel_path = py_file.relative_to(root_dir)
    module_name = str(rel_path).replace('\\', '.').replace('/', '.')[:-3]
    
    try:
        importlib.import_module(module_name)
    except Exception as e:
        print(f"Error importing {module_name}: {type(e).__name__} - {e}")
        # traceback.print_exc()
