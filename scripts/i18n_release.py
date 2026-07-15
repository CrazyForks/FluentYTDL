import os
import subprocess
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent.parent
    locales_dir = root_dir / "assets" / "locales"
    
    if not locales_dir.exists():
        print("No locales directory found.")
        return
        
    for ts_file in locales_dir.glob("*.ts"):
        qm_file = ts_file.with_suffix(".qm")
        print(f"Releasing {qm_file}...")
        
        # 调用 pyside6-lrelease 将 ts 编译为 qm 二进制文件
        lrelease_exe = root_dir / ".venv" / "Scripts" / "pyside6-lrelease.exe"
        if not lrelease_exe.exists():
            lrelease_exe = "pyside6-lrelease"
        cmd = [
            str(lrelease_exe),
            str(ts_file),
            "-qm",
            str(qm_file)
        ]
        subprocess.run(cmd, check=True)
        
    print("i18n release completed.")

if __name__ == "__main__":
    main()
