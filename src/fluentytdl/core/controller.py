import os
import time
from typing import TYPE_CHECKING

from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal

if TYPE_CHECKING:
    from ..models.quick_download_params import QuickDownloadParams

from ..download.download_manager import download_manager
from ..download.workers import DownloadWorker
from ..storage.task_db import task_db
from .config_manager import config_manager


class FileDeleteWorker(QThread):
    finished_signal = Signal(int, list)  # success_count, errors

    def __init__(self, paths_to_delete: list[str]):
        super().__init__()
        self.paths = paths_to_delete

    def run(self):
        import shutil

        success_count = 0
        errors = []
        for p in self.paths:
            deleted = False
            last_error = None
            for _ in range(5):
                try:
                    if os.path.isfile(p):
                        try:
                            os.remove(p)
                        except PermissionError:
                            import stat

                            os.chmod(p, stat.S_IWRITE)
                            os.remove(p)
                        deleted = True
                        break
                    elif os.path.isdir(p):
                        import stat

                        def remove_readonly(func, path, excinfo):
                            os.chmod(path, stat.S_IWRITE)
                            func(path)

                        shutil.rmtree(p, onerror=remove_readonly)
                        if not os.path.exists(p):
                            deleted = True
                            break
                        else:
                            raise Exception("文件夹删除残留")
                    else:
                        deleted = True
                        break
                except Exception as e:
                    last_error = e
                    time.sleep(0.5)

            if deleted:
                if os.path.basename(p) not in [".", ".."]:
                    success_count += 1

            elif last_error:
                errors.append(f"{os.path.basename(p)}: {last_error}")
        self.finished_signal.emit(success_count, errors)


class AppController(QObject):
    """
    The Global UI Controller (God-class Decoupler).
    Handles business logic bridging the View (MainWindow) and the low-level backend
    (download_manager, task_db). The View emits intent signals, and the Controller responds.
    """

    # Optional signals for async background ops the UI might want to know about
    files_deleted = Signal(int, list, str)  # success_count, errors, success_title

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._delete_workers: list[FileDeleteWorker] = []
        self._quick_workers: list[QThread] = []

    def handle_add_tasks(self, tasks: list[tuple[str, str, dict, str]]) -> list[DownloadWorker]:
        """
        Process the payload from the DownloadConfigWindow and inject it into the manager and DB.
        Returns the created workers so the UI model can bind to them.
        tasks payload: [(title, url, opts, thumb), ...]
        """
        created_workers = []
        default_dir = config_manager.get("download_dir")

        for _i, (t_title, t_url, t_opts, t_thumb) in enumerate(tasks):
            logger.info(f"[Controller] Creating worker for URL: {t_url}")

            if default_dir and "paths" not in t_opts:
                outtmpl = t_opts.get("outtmpl")
                if not (isinstance(outtmpl, str) and os.path.isabs(outtmpl)):
                    t_opts["paths"] = {"home": str(default_dir)}

            worker = download_manager.create_worker(
                t_url,
                t_opts,
                cached_info={"title": t_title, "thumbnail": str(t_thumb) if t_thumb else ""},
            )
            created_workers.append((worker, t_title, t_thumb))

            # Start immediately inside the controller policy
            download_manager.start_worker(worker)

        return created_workers

    def handle_quick_add_tasks(
        self, urls: list[str], params: "QuickDownloadParams", callbacks: dict
    ) -> None:
        """
        处理快速下载添加请求，不阻塞主线程。
        callbacks 包含:
          - progress(msg: str)
          - finished(workers: list[DownloadWorker])
          - error(msg: str)
        """
        from .quick_add_worker import QuickAddWorker

        worker = QuickAddWorker(urls, params, max_playlist_items=500, controller=self)

        def on_finished_tasks(tasks: list):
            # 将 tasks 交给 handle_add_tasks 处理并启动
            created = self.handle_add_tasks(tasks)
            if "finished" in callbacks:
                callbacks["finished"](created)
            if worker in self._quick_workers:
                self._quick_workers.remove(worker)

        def on_error(msg: str):
            if "error" in callbacks:
                callbacks["error"](msg)
            if worker in self._quick_workers:
                self._quick_workers.remove(worker)

        if "progress" in callbacks:
            worker.progress.connect(callbacks["progress"])

        worker.finished_tasks.connect(on_finished_tasks)
        worker.error.connect(on_error)

        self._quick_workers.append(worker)
        worker.start()

    def delete_files_best_effort(self, paths: list[str], success_title: str = "已删除文件") -> None:
        """Asynchronously delete files to avoid blocking UI thread."""
        if not paths:
            return

        worker = FileDeleteWorker(paths)

        def on_finished(scount: int, errs: list[str]):
            self.files_deleted.emit(scount, errs, success_title)
            if worker in self._delete_workers:
                self._delete_workers.remove(worker)

        worker.finished_signal.connect(on_finished)
        self._delete_workers.append(worker)
        worker.start()

    def handle_remove_task(
        self, worker: DownloadWorker | None, force_delete_files: bool = False
    ) -> None:
        """
        Handle all logic related to removing or cancelling a task.
        """
        if not worker:
            return

        try:
            db_id = getattr(worker, "db_id", 0)
            state = getattr(worker, "_final_state", "queued")
            if worker.isRunning():
                state = "running"

            if state in ("running", "queued", "paused", "quality_guard", "downloading", "parsing"):
                try:
                    download_manager.remove_worker(worker)
                    worker.cancel()  # Auto-cleans `.part` via globs
                except Exception as e:
                    logger.error(f"Error stopping worker: {e}")

                if force_delete_files:
                    self._do_force_delete_files(worker)

                if db_id:
                    task_db.delete_task(db_id)
                return

            if force_delete_files:
                self._do_force_delete_files(worker)

            if db_id:
                task_db.delete_task(db_id)

        except Exception as e:
            logger.exception(f"Critical error in controller handle_remove_task: {e}")

    def _do_force_delete_files(self, worker: DownloadWorker) -> None:
        final_path = getattr(worker, "output_path", getattr(worker, "_final_filepath", ""))
        import os

        # 如果任务还在沙盒里（未合并），直接删沙盒
        sandbox_dir = getattr(worker, "sandbox_dir", None)
        paths_to_delete = []

        if sandbox_dir and os.path.exists(sandbox_dir):
            paths_to_delete.append(sandbox_dir)

        # 收集最终上岸的文件
        if final_path and os.path.exists(str(final_path)):
            paths_to_delete.append(str(final_path))

            # 同时顺便删除同名的附属文件(字幕,封面等)
            base_name, _ = os.path.splitext(str(final_path))
            aux_exts = [".jpg", ".jpeg", ".webp", ".png", ".vtt", ".srt", ".ass", ".lrc"]
            for ext in aux_exts:
                aux_file = base_name + ext
                if os.path.exists(aux_file):
                    paths_to_delete.append(aux_file)

        # 针对播放列表多文件兜底
        if getattr(worker, "is_single_playlist", False) and getattr(worker, "download_dir", None):
            playlist_dir = worker.download_dir
            if playlist_dir and os.path.exists(playlist_dir):
                paths_to_delete.append(playlist_dir)

        # 对于未在最终路径的 dest_paths 进行兜底
        if hasattr(worker, "dest_paths"):
            for p in worker.dest_paths:
                if p and os.path.exists(str(p)) and str(p) not in paths_to_delete:
                    paths_to_delete.append(str(p))

        # 去重
        paths_to_delete = list(dict.fromkeys(paths_to_delete))

        if paths_to_delete:
            self.delete_files_best_effort(paths_to_delete, success_title="已删除文件残留")

    def handle_pause_resume_task(self, worker: DownloadWorker | None) -> DownloadWorker | None:
        """
        Handle play/pause states. If the task is dead/errored, it recreates a new worker.
        Returns the new worker if one was created, else None.
        """
        if not worker:
            return None

        if hasattr(worker, "is_paused") and worker.is_paused:
            if worker.isFinished():
                # QThread 结束后不能重用，需要重建
                old_db_id = getattr(worker, "db_id", 0)
                cached_meta = {
                    "title": getattr(worker, "v_title", ""),
                    "thumbnail": getattr(worker, "v_thumbnail", ""),
                }
                new_worker = download_manager.create_worker(
                    worker.url, worker.opts, cached_info=cached_meta, restore_db_id=old_db_id
                )
                download_manager.start_worker(new_worker)
                return new_worker
            else:
                worker.resume()
                if not worker.isRunning():
                    download_manager.start_worker(worker)
        elif worker.isRunning():
            if hasattr(worker, "pause"):
                worker.pause()
            else:
                worker.cancel()
        elif not worker.isFinished():
            download_manager.start_worker(worker)
        else:
            # Dead/Cancel/Error state => Reconstruct worker
            old_db_id = getattr(worker, "db_id", 0)
            cached_meta = {
                "title": getattr(worker, "v_title", ""),
                "thumbnail": getattr(worker, "v_thumbnail", ""),
            }
            opts = worker.opts.copy()
            if getattr(worker, "effective_state", "") == "quality_warning":
                opts.pop("__fluentytdl_quality_intent", None)

            new_worker = download_manager.create_worker(
                worker.url, opts, cached_info=cached_meta, restore_db_id=old_db_id
            )
            download_manager.start_worker(new_worker)
            return new_worker

        return None

    def handle_batch_start(
        self, workers: list[DownloadWorker]
    ) -> list[tuple[DownloadWorker, DownloadWorker]]:
        """
        Explicitly resume or restart only the tasks that are not running or queued.
        Returns a list of tuples (old_worker, new_worker) for the ones that were recreated.
        """
        recreated = []
        for worker in workers:
            if not worker:
                continue
            state = getattr(worker, "effective_state", "")
            # Skip tasks that are already running or queued or completed
            if state in ("running", "queued", "completed"):
                continue

            # It's paused, errored, cancelled, completed, etc. We use the same resume logic
            new_worker = self.handle_pause_resume_task(worker)
            if new_worker:
                recreated.append((worker, new_worker))

        # Pump queue once after batch start
        if workers:
            download_manager.pump()

        return recreated

    def handle_batch_pause(self, workers: list[DownloadWorker]) -> None:
        """
        Explicitly pause or cancel only the tasks that are running or queued.
        """
        for worker in workers:
            if not worker:
                continue
            state = getattr(worker, "effective_state", "")
            if state in ("running", "queued"):
                if worker.isRunning():
                    if hasattr(worker, "pause"):
                        worker.pause()
                    else:
                        worker.cancel()
                else:
                    # Not running but queued (waiting in pool)
                    try:
                        download_manager.remove_worker(worker)
                        worker.cancel()
                    except Exception as e:
                        logger.error(f"Error cancelling queued worker in batch pause: {e}")

    def handle_batch_remove(
        self, workers: list[DownloadWorker], force_delete_files: bool = False
    ) -> None:
        """
        Handle removal of multiple tasks atomically.
        """
        paths_to_delete = []
        db_ids_to_delete = []

        for worker in workers:
            if not worker:
                continue

            try:
                db_id = getattr(worker, "db_id", 0)
                if db_id:
                    db_ids_to_delete.append(db_id)

                state = getattr(worker, "_final_state", "queued")
                if worker.isRunning():
                    state = "running"

                if state in ("running", "queued", "paused", "downloading", "parsing"):
                    try:
                        download_manager.remove_worker(worker)
                        worker.cancel()
                    except Exception as e:
                        logger.error(f"Error stopping worker in batch remove: {e}")

                if force_delete_files:
                    # Collect files to delete
                    final_path = getattr(
                        worker, "output_path", getattr(worker, "_final_filepath", "")
                    )
                    sandbox_dir = getattr(worker, "sandbox_dir", None)

                    if sandbox_dir and os.path.exists(sandbox_dir):
                        paths_to_delete.append(sandbox_dir)

                    if final_path and os.path.exists(str(final_path)):
                        paths_to_delete.append(str(final_path))
                        base_name, _ = os.path.splitext(str(final_path))
                        aux_exts = [
                            ".jpg",
                            ".jpeg",
                            ".webp",
                            ".png",
                            ".vtt",
                            ".srt",
                            ".ass",
                            ".lrc",
                        ]
                        for ext in aux_exts:
                            aux_file = base_name + ext
                            if os.path.exists(aux_file):
                                paths_to_delete.append(aux_file)

                    if getattr(worker, "is_single_playlist", False) and getattr(
                        worker, "download_dir", None
                    ):
                        playlist_dir = worker.download_dir
                        if playlist_dir and os.path.exists(playlist_dir):
                            paths_to_delete.append(playlist_dir)

                    if hasattr(worker, "dest_paths"):
                        for p in worker.dest_paths:
                            if p and os.path.exists(str(p)) and str(p) not in paths_to_delete:
                                paths_to_delete.append(str(p))

            except Exception as e:
                logger.error(f"Error processing worker for batch remove: {e}")

        # Batch delete DB entries
        for db_id in set(db_ids_to_delete):
            try:
                task_db.delete_task(db_id)
            except Exception as e:
                logger.error(f"Error deleting db_id {db_id}: {e}")

        # Unique paths
        paths_to_delete = list(dict.fromkeys(paths_to_delete))
        if paths_to_delete:
            self.delete_files_best_effort(
                paths_to_delete, success_title=f"已清理 {len(paths_to_delete)} 个文件残留"
            )


app_controller = AppController()
