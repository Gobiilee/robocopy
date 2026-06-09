# viewmodels/splash_vm.py
from PyQt6.QtCore import QObject, pyqtSignal, pyqtProperty, QTimer

class SplashViewModel(QObject):
    # Định nghĩa các Signal thông báo khi dữ liệu thay đổi để QML cập nhật
    progressChanged = pyqtSignal(int)
    statusChanged = pyqtSignal(str)
    loadingFinished = pyqtSignal()  # Bắn ra khi đạt 100%

    STEP_MS = 30
    STEP_PCT = 2

    def __init__(self):
        super().__init__()
        self._progress = 0
        self._status = "Loading…"
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start_loading(self):
        """Bắt đầu chạy thanh loading thanh thoát"""
        self._timer.start(self.STEP_MS)

    def _tick(self):
        self.progress = min(self._progress + self.STEP_PCT, 100)
        if self._progress >= 100:
            self._timer.stop()
            self.loadingFinished.emit()

    # ── Các Python Property đóng vai trò làm cầu nối dữ liệu ──
    @pyqtProperty(int, notify=progressChanged)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        if self._progress != value:
            self._progress = value
            self.progressChanged.emit(value)

    @pyqtProperty(str, notify=statusChanged)
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if self._status != value:
            self._status = value
            self.statusChanged.emit(value)