"""
ViewModel – bridges CopyWorker (background thread) and the View.

Performance design
──────────────────
The worker emits signals into thread-safe queues.
A 100 ms QTimer on the main thread drains those queues and
updates the UI in one batch — at most 10 repaints/second
regardless of how many files complete per second.

Large-file fix
──────────────
copier.copy_file() now accepts a progress_cb that fires after every
256 KB chunk.  The worker emits a ``bytes_tick`` signal from that
callback so stats/ETA keep updating even when only one huge file is
being copied.
"""

import time
from collections import deque
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer, pyqtSlot

from models.copier import RoboCopier, CopyResult


# ── formatting helpers ────────────────────────────────────────────────────────

def fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def fmt_time(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── worker thread ─────────────────────────────────────────────────────────────

class CopyWorker(QThread):
    """
    Runs file copying on a background thread.
    All signals go to thread-safe queues; the main thread drains them
    via a QTimer — never directly updating widgets from here.
    """

    # Emitted once when scanning is done (total_files, total_bytes)
    scan_done    = pyqtSignal(int, int)
    # Emitted per completed file (name, size_bytes, success)
    file_done    = pyqtSignal(str, int, bool)
    # Emitted after every chunk inside a large file (bytes_just_written)
    bytes_tick   = pyqtSignal(int)
    # Periodic stats (copied_files, total_files, copied_bytes, total_bytes, speed_bps, eta_sec)
    stats_tick   = pyqtSignal(int, int, int, int, float, float)
    # Simple log lines
    log_message  = pyqtSignal(str)
    # Final list of results
    finished_sig = pyqtSignal(list)

    # How often (seconds) to emit a stats_tick while copying
    STATS_INTERVAL = 0.1

    def __init__(self, copier: RoboCopier, src: str, dst: str):
        super().__init__()
        self.copier = copier
        self.src = src
        self.dst = dst

    def run(self) -> None:
        self.copier._is_cancelled = False

        src_path = Path(self.src)
        dst_path = Path(self.dst) / src_path.name

        if not src_path.exists():
            self.log_message.emit(f"Error: Source '{self.src}' does not exist.")
            self.finished_sig.emit([])
            return

        # ── scan ──────────────────────────────────────────────────────────────
        self.log_message.emit("Scanning source folder…")
        files, total_bytes = self.copier.get_folder_stats(src_path)
        total_files = len(files)
        self.log_message.emit(f"Found {total_files} files · {fmt_size(total_bytes)} total")
        self.scan_done.emit(total_files, total_bytes)

        if total_files == 0:
            self.log_message.emit("Nothing to copy.")
            self.finished_sig.emit([])
            return

        # ── copy ──────────────────────────────────────────────────────────────
        # Rolling 3-second speed window
        speed_window: deque[tuple[float, int]] = deque()
        WINDOW = 3.0

        copied_files = 0
        copied_bytes = 0
        results: list[CopyResult] = []
        start_time = time.perf_counter()
        last_stats_emit = start_time

        def _emit_stats():
            """Recalculate and emit stats_tick. Called from progress_cb and after each file."""
            nonlocal last_stats_emit
            now = time.perf_counter()
            if now - last_stats_emit < self.STATS_INTERVAL:
                return
            last_stats_emit = now

            # Prune old window entries
            cutoff = now - WINDOW
            while speed_window and speed_window[0][0] < cutoff:
                speed_window.popleft()

            if speed_window:
                window_bytes = sum(b for _, b in speed_window)
                window_dur   = now - speed_window[0][0] + 0.001
                speed_bps    = window_bytes / window_dur
            else:
                speed_bps = 0.0

            remaining = max(total_bytes - copied_bytes, 0)
            eta = remaining / speed_bps if speed_bps > 0 else 0.0
            self.stats_tick.emit(
                copied_files, total_files,
                copied_bytes, total_bytes,
                speed_bps, eta,
            )

        def _make_progress_cb():
            """
            Returns a closure that the copier calls after each 256 KB chunk.
            Adds to the rolling speed window and emits a stats_tick if enough
            time has passed — this is the key fix for large-file UI freezes.
            """
            def progress_cb(chunk_bytes: int):
                nonlocal copied_bytes
                now = time.perf_counter()
                copied_bytes += chunk_bytes
                speed_window.append((now, chunk_bytes))
                # Signal raw bytes so the VM can re-emit to View
                self.bytes_tick.emit(chunk_bytes)
                _emit_stats()
            return progress_cb

        with ThreadPoolExecutor(max_workers=self.copier.workers) as pool:
            future_map = {
                pool.submit(
                    self.copier.copy_file,
                    f,
                    dst_path / f.relative_to(src_path),
                    _make_progress_cb(),
                ): f
                for f in files
                if not self.copier._is_cancelled
            }

            for future in as_completed(future_map):
                if self.copier._is_cancelled:
                    break

                result = future.result()
                if result.cancelled:
                    continue

                results.append(result)
                copied_files += 1

                # NOTE: copied_bytes already includes this file's bytes via
                # the progress_cb, so we must NOT add size_bytes here again.
                # We only nudge the speed window with a zero-byte marker so
                # _emit_stats sees the updated copied_files count.
                _emit_stats()

                # Signal the completed file (cheap: name + int + bool)
                self.file_done.emit(
                    result.filepath.name,
                    result.size_bytes,
                    result.success,
                )

        # ── summary ───────────────────────────────────────────────────────────
        elapsed   = max(time.perf_counter() - start_time, 0.001)
        avg_speed = copied_bytes / elapsed
        ok        = sum(1 for r in results if r.success)
        fail      = len(results) - ok

        self.log_message.emit("─" * 40)
        if self.copier._is_cancelled:
            self.log_message.emit("⚠  Transfer cancelled by user")
        self.log_message.emit(
            f"✓ {ok} copied   ✗ {fail} failed   "
            f"{fmt_size(copied_bytes)} in {fmt_time(elapsed)}   "
            f"avg {fmt_size(int(avg_speed))}/s"
        )
        self.log_message.emit("─" * 40)
        self.finished_sig.emit(results)


# ── view-model ────────────────────────────────────────────────────────────────

# class MainViewModel(QObject):
#     """
#     Receives raw signals from the worker, buffers them,
#     and re-emits coarse-grained UI signals on a 100 ms timer.
#     """

#     # ── outgoing signals (View listens to these) ──────────────────────────────
#     log_updated   = pyqtSignal(str)
#     # Batch of completed rows: list of (name, size_str, status_str)
#     file_batch    = pyqtSignal(list)
#     stats_update  = pyqtSignal(int, int, int, int, float, float)
#     copy_finished = pyqtSignal()
#     ui_busy       = pyqtSignal(bool)

#     # ── flush interval ────────────────────────────────────────────────────────
#     FLUSH_MS = 100   # drain queue and repaint at most 10×/s

#     def __init__(self) -> None:
#         super().__init__()
#         self.copier  = RoboCopier()
#         self._worker: CopyWorker | None = None

#         # Pending file events waiting to be flushed to the View
#         self._pending_files: list[tuple[str, str, str]] = []

#         # 100 ms flush timer (only runs while copying)
#         self._flush_timer = QTimer(self)
#         self._flush_timer.setInterval(self.FLUSH_MS)
#         self._flush_timer.timeout.connect(self._flush)

#         # Cache the last stats so we can re-emit on flush
#         self._last_stats: tuple | None = None

#     # ── public ────────────────────────────────────────────────────────────────
#     @pyqtSlot(str, str, int)
#     def start_copy(self, src: str, dst: str, workers: int) -> None:
#         if not src or not dst:
#             self.log_updated.emit("Error: Source and Destination must be set.")
#             return

#         self.copier.workers = workers
#         self._pending_files.clear()
#         self._last_stats = None
#         self.ui_busy.emit(True)

#         self._worker = CopyWorker(self.copier, src, dst)
#         self._worker.log_message.connect(self.log_updated)
#         self._worker.file_done.connect(self._on_file_done)
#         self._worker.stats_tick.connect(self._on_stats_tick)
#         # bytes_tick is emitted at chunk granularity; we intentionally do NOT
#         # connect it to anything heavy — _on_stats_tick already batches updates.
#         self._worker.finished_sig.connect(self._on_finished)
#         self._worker.finished.connect(self._worker.deleteLater)
#         self._worker.start()

#         self._flush_timer.start()

#     @pyqtSlot()
#     def cancel_copy(self) -> None:
#         if self._worker and self._worker.isRunning():
#             self.log_updated.emit("Cancellation requested…")
#             self.copier.cancel()

#     # ── worker signal receivers (can be called from any thread via Qt queued) ─

#     def _on_file_done(self, name: str, size_bytes: int, success: bool) -> None:
#         status = "done" if success else "failed"
#         self._pending_files.append((name, fmt_size(size_bytes), status))

#     def _on_stats_tick(self, cf, tf, cb, tb, speed, eta) -> None:
#         # Just cache; _flush will emit to the View
#         self._last_stats = (cf, tf, cb, tb, speed, eta)

#     def _on_finished(self, results: list) -> None:
#         self._flush_timer.stop()
#         self._flush()          # drain anything still pending
#         self.ui_busy.emit(False)
#         self.copy_finished.emit()

#     # ── flush (main thread, called by timer) ──────────────────────────────────

#     def _flush(self) -> None:
#         if self._pending_files:
#             self.file_batch.emit(list(self._pending_files))
#             self._pending_files.clear()

#         if self._last_stats:
#             self.stats_update.emit(*self._last_stats)
#             self._last_stats = None


# viewmodels/main_vm.py
import time
from collections import deque
from pathlib import Path
from queue import Queue, Empty

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer, pyqtProperty, pyqtSlot

from models.copier import RoboCopier, CopyResult
# from viewmodels.worker import CopyWorker # Make sure to import your original worker class here


class MainViewModel(QObject):
    # ── MANDATORY NOTIFY SIGNALS FOR QML BINDINGS ────────────────────────────
    srcPathChanged = pyqtSignal(str)
    dstPathChanged = pyqtSignal(str)
    isBusyChanged = pyqtSignal(bool)
    speedTextChanged = pyqtSignal(str)
    etaTextChanged = pyqtSignal(str)
    progressPctChanged = pyqtSignal(int)
    filesLogChanged = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        # Internal private memory storage
        self._src_path = ""
        self._dst_path = ""
        self._is_busy = False
        self._speed_text = "— B/s"
        self._eta_text = "—"
        self._progress_pct = 0
        self._files_html_log = ""  # Accumulated HTML log string rendered by QML TextArea

        # Threading worker references
        self.worker = None

        # ── BATCH TIMER (Drains logging queue 10 times per second) ────────────
        self.ui_timer = QTimer()
        self.ui_timer.setInterval(100)  # 100 ms batch interval
        self.ui_timer.timeout.connect(self._on_ui_timer_tick)

        # Batch caching structures
        self.log_accumulator = []

    # ── PROPERTY BRIDGE HOOKS (Enables QML read/write access) ────────────────
    @pyqtProperty(str, notify=srcPathChanged)
    def src_path(self): return self._src_path

    @src_path.setter
    def src_path(self, value):
        if self._src_path != value:
            self._src_path = value
            self.srcPathChanged.emit(value)

    @pyqtProperty(str, notify=dstPathChanged)
    def dst_path(self): return self._dst_path

    @dst_path.setter
    def dst_path(self, value):
        if self._dst_path != value:
            self._dst_path = value
            self.dstPathChanged.emit(value)

    @pyqtProperty(bool, notify=isBusyChanged)
    def is_busy(self): return self._is_busy

    @pyqtProperty(str, notify=speedTextChanged)
    def speed_text(self): return self._speed_text

    @pyqtProperty(str, notify=etaTextChanged)
    def eta_text(self): return self._eta_text

    @pyqtProperty(int, notify=progressPctChanged)
    def progress_pct(self): return self._progress_pct

    @pyqtProperty(str, notify=filesLogChanged)
    def files_html_log(self): return self._files_html_log

    # ── EXPOSED QML SLOTS (Action Controllers) ────────────────────────────────

    @pyqtSlot(str, str, int)
    def start_copy(self, src: str, dst: str, threads: int):
        """Triggered directly by QML 'Start Transfer' button onClicked channel."""
        if self._is_busy:
            return

        # Synchronize back input parameters in case textfields mutated
        self._src_path = src
        self._dst_path = dst

        # Clear out historical logs from previous executions
        self._files_html_log = ""
        self.filesLogChanged.emit(self._files_html_log)
        self.log_accumulator.clear()

        # Update engine states
        self._is_busy = True
        self.isBusyChanged.emit(True)

        # ── INITIALIZE BACKEND THREAD WORKER ──────────────────────────────────
        # Build your original CopyWorker using your existing core business parameters
        copier = RoboCopier(workers=threads)
        self.worker = CopyWorker(copier, src, dst)

        # Wire up safety signal channels from background worker to ViewModel slots
        self.worker.stats_tick.connect(self._on_worker_stats_tick)
        self.worker.file_done.connect(self._on_worker_file_done)
        self.worker.finished_sig.connect(self._on_worker_finished)

        # Launch background worker execution & fire the batch timer loop
        self.ui_timer.start()
        self.worker.start()

    @pyqtSlot()
    def cancel_copy(self):
        """Triggered directly by QML 'Cancel' button onClicked channel."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel() # Trigger original abort flag inside copier engine

    # ── WORKER SIGNAL SLOTS (Thread-safe communications) ─────────────────────

    def _on_worker_stats(self, speed_str: str, eta_str: str, pct: int):
        """Update reactive components targeting the top statistics bar panel."""
        self._speed_text = speed_str
        self._eta_text = eta_str
        self._progress_pct = pct
        
        # Fire events to notify QML layouts to realign visuals
        self.speedTextChanged.emit(speed_str)
        self.etaTextChanged.emit(eta_str)
        self.progressPctChanged.emit(pct)

    def _on_worker_file_completed(self, name: str, size: str, status: str):
        """Queue raw string logs into an isolated cache instead of instantly printing."""
        # Convert completion states into colored HTML objects matching old look
        color_map = {"OK": "#34a853", "FAIL": "#ea4335", "SKIP": "#fbbc05"}
        color = color_map.get(status, "#888888")
        icon = "✔" if status == "OK" else "✖" if status == "FAIL" else "ℹ"
        
        html_segment = (
            f'<span style="color:{color}">{icon}</span>'
            f'&nbsp;{name}'
            f'<span style="color:#555555\"> &nbsp;{size}</span>'
        )
        self.log_accumulator.append(html_segment)

    def _on_ui_timer_tick(self):
        """Flushes the queued cached HTML lines straight up into QML memory space."""
        if not self.log_accumulator:
            return

        # Merge new tokens into main log string using QML compatible line break tags
        new_entries_block = "<br>".join(self.log_accumulator)
        if self._files_html_log:
            self._files_html_log += "<br>" + new_entries_block
        else:
            self._files_html_log = new_entries_block

        self.log_accumulator.clear()
        
        # CRITICAL EMIT: Tells QML ScrollView to grab the updated rich text log layout
        self.filesLogChanged.emit(self._files_html_log)

    def _on_worker_finished(self):
        """Teardown loops and close timers when background processes complete."""
        self.ui_timer.stop()
        
        # Flush any residual trailing logs remaining inside accumulator storage
        self._on_ui_timer_tick()

        self._is_busy = False
        self.isBusyChanged.emit(False)
        
        self._speed_text = "— B/s"
        self._eta_text = "Finished"
        self.speedTextChanged.emit(self._speed_text)
        self.etaTextChanged.emit(self._eta_text)

    def _on_worker_stats_tick(self, copied_files, total_files, copied_bytes, total_bytes, speed_bps, eta_sec):
        """Processes periodic statistics ticks generated by the worker thread."""
        # Calculate dynamic percentage safely
        pct = int((copied_bytes / total_bytes * 100)) if total_bytes > 0 else 0
        self._progress_pct = pct
        self.progressPctChanged.emit(pct)

        # Format speed into human readable string (using your fmt_size helper if available)
        # Hoặc dùng định dạng tạm thời:
        if speed_bps > 1024 * 1024:
            speed_str = f"{speed_bps / (1024*1024):.1f} MB/s"
        elif speed_bps > 1024:
            speed_str = f"{speed_bps / 1024:.1f} KB/s"
        else:
            speed_str = f"{speed_bps:.0f} B/s"
            
        self._speed_text = speed_str
        self.speedTextChanged.emit(speed_str)

        # Format ETA text safely
        if eta_sec < 0:
            eta_str = "—"
        elif eta_sec == 0:
            eta_str = "Done"
        else:
            m, s = divmod(int(eta_sec), 60)
            h, m = divmod(m, 60)
            eta_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            
        self._eta_text = eta_str
        self.etaTextChanged.emit(eta_str)


    def _on_worker_file_done(self, name: str, size_bytes: int, success: bool):
        """Queue raw completed file definitions into the batch layout accumulator."""
        status = "OK" if success else "FAIL"
        color = "#34a853" if success else "#ea4335"
        icon = "✔" if success else "✖"
        
        # Format human size
        if size_bytes > 1024 * 1024 * 1024:
            size_str = f"{size_bytes / (1024*1024*1024):.1f} GB"
        elif size_bytes > 1024 * 1024:
            size_str = f"{size_bytes / (1024*1024):.1f} MB"
        else:
            size_str = f"{size_bytes / 1024:.1f} KB"

        # Escape HTML entities inside path definitions to avoid layout breaks
        safe_name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        html_segment = (
            f'<span style="color:{color}">{icon}</span>'
            f'&nbsp;{safe_name}'
            f'<span style="color:#555555\"> &nbsp;({size_str})</span>'
        )
        self.log_accumulator.append(html_segment)


    def _on_worker_finished(self, results_list=None):
        """Teardown loops and close timers when background processes complete."""
        self.ui_timer.stop()
        self._on_ui_timer_tick() # Flush any remaining lines to QML

        self._is_busy = False
        self.isBusyChanged.emit(False)
        
        # self._speed_text = "— B/s"
        # self._eta_text = "Finished"
        # self.speedTextChanged.emit(self._speed_text)
        # self.etaTextChanged.emit(self._eta_text)