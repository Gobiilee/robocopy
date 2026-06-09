# views/main_view.py
import os
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtWidgets import QFileDialog

class MainWindowView(QObject):
    """View controller that manages the main QML application window architecture."""
    
    def __init__(self, main_vm, network_vm):
        super().__init__()
        self.main_vm = main_vm
        self.network_vm = network_vm
        
        self.engine = QQmlApplicationEngine()
        qml_dir = Path(__file__).parent / "qml"
        if not qml_dir.exists():
            qml_dir = Path(__file__).parent
        self.engine.addImportPath(os.fspath(qml_dir))
        
        # Inject ViewModels directly into QML context environment before loading
        context = self.engine.rootContext()
        context.setContextProperty("localVM", self.main_vm)
        context.setContextProperty("networkVM", self.network_vm)
        
        # Inject this view instance itself to act as a slot listener bridge
        context.setContextProperty("localViewWrapper", self)
        context.setContextProperty("networkViewWrapper", self)
        
        # Load up the main window UI layout compiled by QML
        qml_path = Path(__file__).parent / "qml/MainWindow.qml"
        self.engine.load(os.fspath(qml_path))
        
        if not self.engine.rootObjects():
            raise RuntimeError("CRITICAL: Failed to load main_window.qml successfully.")
            
        self.root_window = self.engine.rootObjects()[0]

    # ── native OS folder picker channels exposed to QML ──

    @pyqtSlot()
    def pick_source(self):
        """Invoke native folder selector dialog for local copy source path."""
        folder = QFileDialog.getExistingDirectory(None, "Select Local Source Folder")
        if folder:
            # Update property inside ViewModel, UI auto-syncs through bindings
            self.main_vm.src_path = folder

    @pyqtSlot()
    def pick_destination(self):
        """Invoke native folder selector dialog for local copy destination path."""
        folder = QFileDialog.getExistingDirectory(None, "Select Local Destination Folder")
        if folder:
            self.main_vm.dst_path = folder

    @pyqtSlot()
    def pick_net_destination(self):
        """Invoke native folder selector dialog for network download target path."""
        folder = QFileDialog.getExistingDirectory(None, "Select SMB Download Destination")
        if folder:
            self.network_vm.download_destination = folder

    def show(self):
        """Helper to expose display handling matching old QWidget invocation api."""
        if self.root_window:
            self.root_window.show()