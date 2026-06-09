"""
main.py  –  Application entry point.

Boot sequence
─────────────
1. Show SplashScreen immediately (before any heavy imports)
2. Splash animates its progress bar (~1.5 s)
3. When bar hits 100 %, build the ViewModel + MainWindow
4. Splash fades out, main window appears
"""

import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui     import QIcon
from splash          import SplashScreen, _asset


# Module-level reference so the window is never garbage-collected
_main_window = None


def _launch_main(splash: SplashScreen):
    """Called by the splash timer when the loading bar finishes."""
    global _main_window

    try:
        splash.set_status("Starting application…")

        from viewmodels.main_vm import MainViewModel
        from views.main_window  import MainWindow

        vm           = MainViewModel()
        _main_window = MainWindow(vm)
        _main_window.setWindowIcon(QIcon(_asset("icon.ico")))

        splash.finish(_main_window)

    except Exception:
        # Show the full traceback in a dialog so it is never silently swallowed
        msg = traceback.format_exc()
        splash.close()
        err = QMessageBox()
        err.setWindowTitle("Startup Error")
        err.setIcon(QMessageBox.Icon.Critical)
        err.setText("pyRoboCopy failed to start.")
        err.setDetailedText(msg)
        err.exec()
        sys.exit(1)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("pyRoboCopy")
    app.setWindowIcon(QIcon(_asset("icon.ico")))

    splash = SplashScreen()
    splash.show()
    app.processEvents()

    splash.start(done_callback=lambda: _launch_main(splash))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
