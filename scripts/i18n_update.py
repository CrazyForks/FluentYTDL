import os
import subprocess
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent.parent
    src_dir = root_dir / "src" / "fluentytdl"
    locales_dir = root_dir / "assets" / "locales"
    
    locales_dir.mkdir(parents=True, exist_ok=True)
    
    # 定义需要支持的目标语言，包含新增的日语和繁体中文
    TARGET_LANGUAGES = ["en_US", "zh_CN", "ja_JP", "zh_TW"]
    
    for lang in TARGET_LANGUAGES:
        ts_file = locales_dir / f"fluentytdl_{lang}.ts"
        print(f"Updating {ts_file}...")
        
        # 调用 pyside6-lupdate 扫描源代码并更新 ts 文件
        lupdate_exe = root_dir / ".venv" / "Scripts" / "pyside6-lupdate.exe"
        if not lupdate_exe.exists():
            lupdate_exe = "pyside6-lupdate"
            
        # 收集所有 .py 文件 (src 下的所有文件，加上根目录的 main.py)
        py_files = [str(p) for p in src_dir.rglob("*.py")]
        main_py = root_dir / "main.py"
        if main_py.exists():
            py_files.append(str(main_py))
        
        cmd = [
            str(lupdate_exe),
            *py_files,
            "-ts",
            str(ts_file)
        ]
        subprocess.run(cmd, check=True)
        
    print("i18n update completed.")

if __name__ == "__main__":
    main()
