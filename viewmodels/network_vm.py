"""
network_vm.py  –  ViewModel for the Network (SMB) tab.

Runs SMB operations on QThread workers to keep the UI responsive.
"""

from __future__ import annotations
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer

from models.smb_browser import SMBBrowser, SMBEntry, _fmt_size


# ── connect worker ────────────────────────────────────────────────────────────

class ConnectWorker(QThread):
    success = pyqtSignal(list)   # list[SMBEntry]
    error   = pyqtSignal(str)

    def __init__(self, server, username, password, share):
        super().__init__()
        self._server   = server
        self._username = username
        self._password = password
        self._share    = share
        self._browser  = SMBBrowser()

    def run(self):
        try:
            entries = self._browser.connect(
                self._server, self._username, self._password, self._share
            )
            self.success.emit(entries)
        except Exception as exc:
            self.error.emit(str(exc))


# ── expand-dir worker ─────────────────────────────────────────────────────────

class ExpandWorker(QThread):
    success = pyqtSignal(str, list)   # (unc_path, list[SMBEntry])
    error   = pyqtSignal(str, str)    # (unc_path, error_message)

    def __init__(self, browser: SMBBrowser, unc_path: str):
        super().__init__()
        self._browser  = browser
        self._unc_path = unc_path

    def run(self):
        try:
            entries = self._browser.expand_dir(self._unc_path)
            self.success.emit(self._unc_path, entries)
        except Exception as exc:
            self.error.emit(self._unc_path, str(exc))


# ── download worker ───────────────────────────────────────────────────────────

class DownloadWorker(QThread):
    log_message  = pyqtSignal(str)
    file_done    = pyqtSignal(str, int, bool)    # name, bytes, success
    stats_tick   = pyqtSignal(int, int, int, int, float, float)
    finished_sig = pyqtSignal(int, int)          # ok_count, fail_count

    def __init__(self, browser: SMBBrowser, selected: list[str], destination: str):
        super().__init__()
        self._browser     = browser
        self._selected    = selected
        self._destination = destination

    def run(self):
        self._browser.download_selected(
            self._selected,
            self._destination,
            on_log       = self.log_message.emit,
            on_file_done = self.file_done.emit,
            on_stats     = self.stats_tick.emit,
            on_finished  = self.finished_sig.emit,
        )


# ── view-model ────────────────────────────────────────────────────────────────

class NetworkViewModel(QObject):

    # ── signals to the view ───────────────────────────────────────────────────
    connect_ok      = pyqtSignal(list)   # list[SMBEntry] — top-level listing
    connect_err     = pyqtSignal(str)
    expand_ok       = pyqtSignal(str, list)   # unc_path, children
    expand_err      = pyqtSignal(str, str)

    log_updated     = pyqtSignal(str)
    file_batch      = pyqtSignal(list)   # list of (name, size_str, status)
    stats_update    = pyqtSignal(int, int, int, int, float, float)
    ui_busy         = pyqtSignal(bool)   # True=downloading

    FLUSH_MS = 100

    def __init__(self) -> None:
        super().__init__()
        self._browser: SMBBrowser | None = None
        self._server  = ""
        self._share   = ""

        self._connect_worker:  ConnectWorker  | None = None
        self._expand_worker:   ExpandWorker   | None = None
        self._download_worker: DownloadWorker | None = None

        self._pending_files: list[tuple[str, str, str]] = []
        self._last_stats: tuple | None = None

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(self.FLUSH_MS)
        self._flush_timer.timeout.connect(self._flush)

    # ── public ────────────────────────────────────────────────────────────────

    def connect_share(self, server: str, username: str, password: str, share: str) -> None:
        self._browser = SMBBrowser()
        self._server  = server
        self._share   = share

        self._connect_worker = ConnectWorker(server, username, password, share)
        self._connect_worker.success.connect(self.connect_ok)
        self._connect_worker.error.connect(self.connect_err)
        self._connect_worker.finished.connect(self._connect_worker.deleteLater)
        self._connect_worker.start()

    def expand_dir(self, unc_path: str) -> None:
        if not self._browser:
            return
        self._expand_worker = ExpandWorker(self._browser, unc_path)
        self._expand_worker.success.connect(self.expand_ok)
        self._expand_worker.error.connect(self.expand_err)
        self._expand_worker.finished.connect(self._expand_worker.deleteLater)
        self._expand_worker.start()

    def start_download(self, selected_paths: list[str], destination: str) -> None:
        if not self._browser:
            return
        self._pending_files.clear()
        self._last_stats = None
        self.ui_busy.emit(True)

        self._download_worker = DownloadWorker(self._browser, selected_paths, destination)
        self._download_worker.log_message.connect(self.log_updated)
        self._download_worker.file_done.connect(self._on_file_done)
        self._download_worker.stats_tick.connect(self._on_stats_tick)
        self._download_worker.finished_sig.connect(self._on_finished)
        self._download_worker.finished.connect(self._download_worker.deleteLater)
        self._download_worker.start()
        self._flush_timer.start()

    def cancel_download(self) -> None:
        if self._browser:
            self._browser.cancel()

    # ── private ───────────────────────────────────────────────────────────────

    def _on_file_done(self, name: str, size: int, ok: bool):
        status = "done" if ok else "failed"
        self._pending_files.append((name, _fmt_size(size), status))

    def _on_stats_tick(self, cf, tf, cb, tb, speed, eta):
        self._last_stats = (cf, tf, cb, tb, speed, eta)

    def _on_finished(self, ok: int, fail: int):
        self._flush_timer.stop()
        self._flush()
        self.ui_busy.emit(False)

    def _flush(self):
        if self._pending_files:
            self.file_batch.emit(list(self._pending_files))
            self._pending_files.clear()
        if self._last_stats:
            self.stats_update.emit(*self._last_stats)
            self._last_stats = None
