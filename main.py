"""
main.py  –  Application entry point.

Boot sequence
─────────────
1. Show SplashScreen immediately (before any heavy imports)
2. Splash animates its progress bar (~1.5 s)
3. When bar hits 100 %, build the ViewModel + MainWindow
4. Splash fades out, main window appears
"""

# main.py
import sys
import os
import traceback
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CRITICAL FIX: Resolve missing QtQuick Controls Windows style plugin DLLs
# ─────────────────────────────────────────────────────────────────────────────
# Find the exact absolute path to your virtual environment packages
venv_base = Path(__file__).parent / "../venv_robocopy" / "Lib" / "site-packages"

# Fallback checking if you are invoking directly from within the active environment
if not venv_base.exists():
    import PyQt6
    venv_base = Path(PyQt6.__file__).parent.parent

# Inject the binary paths into windows OS search path so DLLs can resolve each other
qt_bin_path = venv_base / "PyQt6" / "Qt6" / "bin"
if qt_bin_path.exists():
    os.add_dll_directory(str(qt_bin_path))

# Force QML engine to look inside the correct site-packages plugin directory
qt_plugin_path = venv_base / "PyQt6" / "Qt6" / "plugins"
os.environ["QT_PLUGIN_PATH"] = str(qt_plugin_path)
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"

from pathlib import Path
import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui     import QIcon
# from splash          import SplashScreen, _asset
from viewmodels.splash_vm import SplashViewModel
from views.splash_view    import SplashView


# Module-level reference so the window is never garbage-collected
_main_window = None
splash_view = None

def _asset(name: str) -> str:
    """Return path to an asset, works in dev and inside a frozen .exe."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return str(base / "assets" / name)

def _launch_main():
    """Called by the splash timer when the loading bar finishes."""
    global _main_window, splash_view

    try:
        splash_view.vm.status = "Starting application…"

        from viewmodels.main_vm import MainViewModel
        from viewmodels.network_vm import NetworkViewModel
        from views.main_view import MainWindowView

        # Instantiate ViewModels containing business core logic
        local_vm = MainViewModel()
        net_vm = NetworkViewModel()

        # Build QML wrapper layout view context
        _main_window = MainWindowView(local_vm, net_vm)

        _main_window.show()
        splash_view.close()

    except Exception:
        # Show the full traceback in a dialog so it is never silently swallowed
        msg = traceback.format_exc()
        if splash_view:
            splash_view.close()
        err = QMessageBox()
        err.setWindowTitle("Startup Error")
        err.setIcon(QMessageBox.Icon.Critical)
        err.setText("pyRoboCopy failed to start.")
        err.setDetailedText(msg)
        err.exec()
        sys.exit(1)


def main():
    global splash_view
    app = QApplication(sys.argv)
    app.setApplicationName("pyRoboCopy")
    app.setWindowIcon(QIcon(_asset("icon.ico")))

    splash_vm = SplashViewModel()
    splash_view = SplashView(splash_vm)
    splash_vm.loadingFinished.connect(_launch_main)

    # 3. Kích hoạt tiến trình đếm số
    splash_vm.start_loading()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
