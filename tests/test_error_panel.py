import sys
import os
from unittest.mock import patch

# 确保能找到 src 目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from fluentytdl.models.errors import YtDlpExecutionError
from fluentytdl.download.executor import DownloadExecutor

original_execute = DownloadExecutor.execute

def fake_execute(self, url, *args, **kwargs):
    # yt-dlp 解析阶段会自动清理 URL 参数，所以我们直接匹配特定的视频 ID (Me at the zoo)
    if "jNQXAC9IVRw" in url:
        print(f"!!! MOCKING ERROR FOR URL: {url} !!!")
        fake_json = {"error": {"_type": "FakeError", "message": "Mocked download failure for testing repair panel"}}
        raise YtDlpExecutionError(1, "ERROR: Unable to download video data (Mocked)", fake_json)
        
    return original_execute(self, url, *args, **kwargs)

if __name__ == "__main__":
    print("=" * 60)
    print("启动测试环境 (已挂载 mock).")
    print("请在应用中添加这个特殊的测试链接以触发强制下载失败：")
    print("https://www.youtube.com/watch?v=jNQXAC9IVRw")
    print("=" * 60)
    
    with patch("fluentytdl.download.workers.DownloadExecutor.execute", new=fake_execute):
        import runpy
        main_py_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        runpy.run_path(main_py_path, run_name="__main__")
