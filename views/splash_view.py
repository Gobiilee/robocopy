# views/splash_view.py
import os
from pathlib import Path
import sys
from PyQt6.QtQml import QQmlApplicationEngine
from viewmodels.splash_vm import SplashViewModel


class SplashView:
    """View class quản lý engine QML cho Splash Screen."""
    def __init__(self, vm: SplashViewModel):
        self.vm = vm
        self.engine = QQmlApplicationEngine()

        # Tìm đường dẫn tuyệt đối đến file QML
        qml_path = Path(__file__).parent / "qml/Splash.qml"
        
        if not qml_path.exists():
            raise FileNotFoundError(f"QML not found: {qml_path}")

        # THAY ĐỔI Ở ĐÂY: Sử dụng setContextProperty TRƯỚC khi load file
        # Việc này đảm bảo khi QML vừa thức dậy là đã thấy 'vm' nằm sẵn trong bộ nhớ
        self.engine.rootContext().setContextProperty("vm", self.vm)

        # Tiến hành load file QML
        self.engine.load(os.fspath(qml_path))
        
        if not self.engine.rootObjects():
            raise RuntimeError("QML Engine can't load file 'splash.qml'.")

        self.root_window = self.engine.rootObjects()[0]

    def close(self):
        if self.root_window:
            self.root_window.close()