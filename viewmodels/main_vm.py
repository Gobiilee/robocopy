from PyQt6.QtCore import QObject, pyqtSignal
from models.copier import RoboCopier, CopyResult
from viewmodels.copy_woker import CopyWorker

class MainViewModel(QObject):
    """
    Transforms Model data into UI-friendly signals and handles user commands.
    """
    # Signals that the View will listen to
    log_updated = pyqtSignal(str)
    copy_finished = pyqtSignal()
    ui_state_changed = pyqtSignal(bool)  # True if busy, False if idle

    def __init__(self) -> None:
        super().__init__()
        self.copier = RoboCopier()
        self._worker: CopyWorker | None = None

    def start_copy(self, src: str, dst: str, workers: int) -> None:
        """Called by the View to begin the process."""
        if not src or not dst:
            self.log_updated.emit("Error: Source and Destination must be provided.")
            return

        self.ui_state_changed.emit(True)  # Tell UI to disable 'Start' button
        self.copier.workers = workers
        
        self._worker = CopyWorker(self.copier, src, dst)
        self._worker.log_signal.connect(self.log_updated.emit)
        self._worker.progress_signal.connect(self.log_updated.emit) # Log real-time
        self._worker.finished_signal.connect(self._on_copy_finished)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def cancel_copy(self) -> None:
        """Called by the View when the user hits 'Cancel'."""
        if self._worker and self._worker.isRunning():
            self.log_updated.emit("Cancellation requested. Waiting for active files to finish...")
            self.copier.cancel()

    def _on_copy_finished(self, results: list[CopyResult]) -> None:
        """Processes the results from the background thread."""
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        
        self.log_updated.emit("=" * 30)
        if self.copier._is_cancelled:
            self.log_updated.emit("Process CANCELLED by user.")
        self.log_updated.emit(f"Process Complete. Copied: {success_count}, Failed: {fail_count}")
        
        # Log failures if any occurred
        if fail_count > 0:
            self.log_updated.emit("\nErrors encountered:")
            for r in results:
                if not r.success:
                    self.log_updated.emit(f"- {r.filepath.name}: {r.error_message}")
        
        self.ui_state_changed.emit(False)  # Tell UI to re-enable buttons
        self.copy_finished.emit()