"""
main_window.py  –  Two-tab RoboCopy UI: Local and Network (SMB).

Local tab  : identical to the original copy-folder workflow.
Network tab: SMB credential entry → connect → tree with checkboxes
             → destination picker → Download button.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QProgressBar,
    QTextEdit, QSpinBox, QLineEdit, QFrame,
    QTabWidget, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QSizePolicy, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui  import QTextCursor, QIcon, QColor, QFont

from viewmodels.main_vm     import MainViewModel
from viewmodels.network_vm  import NetworkViewModel
from models.smb_browser     import SMBEntry


# ── helpers ───────────────────────────────────────────────────────────────────

def _label(text: str, *, bold=False, size=9, color="#cccccc") -> QLabel:
    lbl = QLabel(text)
    f = lbl.font()
    f.setPointSize(size)
    f.setBold(bold)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color: {color};")
    return lbl


def _line_edit(placeholder: str, *, password=False) -> QLineEdit:
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    if password:
        w.setEchoMode(QLineEdit.EchoMode.Password)
    w.setStyleSheet("""
        QLineEdit {
            background: #1e1e1e;
            border: 1px solid #3a3a3a;
            border-radius: 4px;
            color: #e0e0e0;
            padding: 5px 8px;
            font-size: 9pt;
        }
        QLineEdit:focus { border-color: #1a73e8; }
    """)
    return w


def _btn(text: str, color="#2d2d2d", hover="#383838") -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(32)
    b.setStyleSheet(f"""
        QPushButton {{
            background: {color}; border: 1px solid #4a4a4a;
            border-radius: 5px; color: #cccccc;
            padding: 0 14px; font-size: 9pt;
        }}
        QPushButton:hover   {{ background: {hover}; }}
        QPushButton:pressed {{ background: #252525; }}
        QPushButton:disabled{{ color: #555; background: #222; border-color: #333; }}
    """)
    return b


# ── global dark stylesheet ────────────────────────────────────────────────────

DARK = """
QMainWindow, QWidget { background: #1a1a1a; color: #e0e0e0; }
QTabWidget::pane     { border: 1px solid #333; border-radius: 6px;
                        background: #1a1a1a; }
QTabBar::tab {
    background: #242424; color: #888; border: 1px solid #333;
    border-bottom: none; padding: 6px 20px; border-radius: 4px 4px 0 0;
    margin-right: 2px; font-size: 9pt;
}
QTabBar::tab:selected { background: #1a73e8; color: #fff; border-color: #1a73e8; }
QTabBar::tab:hover:!selected { background: #2d2d2d; color: #ccc; }

QScrollBar:vertical   { background: #1a1a1a; width: 8px; margin: 0; }
QScrollBar::handle:vertical {
    background: #3a3a3a; border-radius: 4px; min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QTreeWidget {
    background: #1e1e1e; border: 1px solid #333; border-radius: 6px;
    color: #ddd; font-size: 9pt; outline: none;
}
QTreeWidget::item         { padding: 3px 2px; }
QTreeWidget::item:selected { background: #1a3a5c; color: #fff; }
QTreeWidget::item:hover   { background: #252525; }
QTreeWidget::branch:closed:has-children { image: none; }
QTreeWidget::branch:open:has-children   { image: none; }
"""

FILE_COLOR = {"done": "#4caf50", "failed": "#f44336", "copying": "#f0c040"}
FILE_ICON  = {"done": "✓",       "failed": "✗",        "copying": "⟳"}


# ── PathCard (reused in both tabs) ────────────────────────────────────────────

class PathCard(QFrame):
    """Labeled folder-picker card. Uses QFrame so background paints on Windows."""

    def __init__(self, title: str, placeholder: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            PathCard, QFrame#PathCard {
                background: #252525;
                border: 1px solid #333333;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(5)

        layout.addWidget(_label(title, bold=True, size=8, color="#777777"))

        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)

        icon_lbl = QLabel("📁")
        icon_lbl.setFixedWidth(20)
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        row.addWidget(icon_lbl)

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText(placeholder)
        self.path_input.setReadOnly(True)
        self.path_input.setFixedHeight(28)
        self.path_input.setStyleSheet("""
            QLineEdit {
                background: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                color: #e0e0e0;
                padding: 2px 8px;
                font-size: 9pt;
            }
        """)
        row.addWidget(self.path_input, 1)

        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setFixedSize(72, 28)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background: #2d2d2d; border: 1px solid #4a4a4a;
                border-radius: 4px; color: #cccccc;
                font-size: 9pt;
            }
            QPushButton:hover    { background: #383838; }
            QPushButton:pressed  { background: #252525; }
            QPushButton:disabled { color: #555; background: #222; border-color: #333; }
        """)
        row.addWidget(self.browse_btn)
        layout.addLayout(row)

    def text(self):             return self.path_input.text()
    def set_enabled(self, v):   self.browse_btn.setEnabled(v)


# ── StatsBar ──────────────────────────────────────────────────────────────────

class StatsBar(QFrame):
    """Speed · ETA · file count · progress — lives inside a styled QFrame."""

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            StatsBar, QFrame#StatsBar {
                background: #252525;
                border: 1px solid #333333;
                border-radius: 6px;
            }
        """)

        main = QVBoxLayout(self)
        main.setContentsMargins(14, 8, 14, 8)
        main.setSpacing(6)

        nums = QHBoxLayout()
        nums.setSpacing(0)
        nums.setContentsMargins(0, 0, 0, 0)

        self.speed_lbl = self._make_stat("Speed",    "— B/s")
        self.eta_lbl   = self._make_stat("ETA",      "—")
        self.files_lbl = self._make_stat("Files",    "0 / 0")
        self.pct_lbl   = self._make_stat("Progress", "0 %")

        for w in (self.speed_lbl, self.eta_lbl, self.files_lbl, self.pct_lbl):
            nums.addWidget(w)
        nums.addStretch()
        main.addLayout(nums)

        self.bar = QProgressBar()
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setStyleSheet("""
            QProgressBar {
                background: #2a2a2a; border-radius: 3px; border: none;
            }
            QProgressBar::chunk {
                border-radius: 3px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1a73e8, stop:1 #34a853);
            }
        """)
        main.addWidget(self.bar)

    @staticmethod
    def _make_stat(label: str, value: str) -> QWidget:
        # Use a plain QWidget with no border/background of its own
        w = QWidget()
        w.setStyleSheet("QWidget { border: none; background: transparent; }")
        w.setFixedWidth(110)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)

        lbl = QLabel(label)
        lbl.setStyleSheet("color: #666666; font-size: 7pt; border: none; background: transparent;")
        v.addWidget(lbl)

        val = QLabel(value)
        val.setObjectName("val")
        val.setStyleSheet("color: #e0e0e0; font-size: 10pt; font-weight: bold; border: none; background: transparent;")
        v.addWidget(val)
        return w

    def _val(self, w: QWidget) -> QLabel:
        return w.findChild(QLabel, "val")

    def update_stats(self, cf, tf, cb, tb, speed, eta):
        from viewmodels.main_vm import fmt_size, fmt_time
        pct = int(cb / tb * 100) if tb else 0
        self._val(self.speed_lbl).setText(f"{fmt_size(int(speed))}/s")
        self._val(self.eta_lbl).setText(fmt_time(eta))
        self._val(self.files_lbl).setText(f"{cf} / {tf}")
        self._val(self.pct_lbl).setText(f"{pct} %")
        self.bar.setValue(pct)

    def reset(self):
        self._val(self.speed_lbl).setText("— B/s")
        self._val(self.eta_lbl).setText("—")
        self._val(self.files_lbl).setText("0 / 0")
        self._val(self.pct_lbl).setText("0 %")
        self.bar.setValue(0)


# ── LOCAL TAB ────────────────────────────────────────────────────────────────

class LocalTab(QWidget):
    def __init__(self, vm: MainViewModel):
        super().__init__()
        self.vm = vm
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # ── Source → Destination row ──────────────────────────────────────────
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_row.setContentsMargins(0, 0, 0, 0)

        self.src_card = PathCard("SOURCE", "Choose source folder…")
        self.src_card.browse_btn.clicked.connect(
            lambda: self._pick(self.src_card.path_input))

        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(24)
        arrow.setStyleSheet("color: #444; font-size: 16pt; font-weight: bold; border: none; background: transparent;")

        self.dst_card = PathCard("DESTINATION", "Choose destination folder…")
        self.dst_card.browse_btn.clicked.connect(
            lambda: self._pick(self.dst_card.path_input))

        path_row.addWidget(self.src_card, 1)
        path_row.addWidget(arrow)
        path_row.addWidget(self.dst_card, 1)
        layout.addLayout(path_row)

        # ── Stats bar ─────────────────────────────────────────────────────────
        self.stats_bar = StatsBar()
        layout.addWidget(self.stats_bar)

        # ── File list ─────────────────────────────────────────────────────────
        layout.addWidget(_label("FILES", bold=True, size=8, color="#555555"))
        self.file_log = QTextEdit()
        self.file_log.setReadOnly(True)
        self.file_log.setStyleSheet("""
            QTextEdit { background:#1e1e1e; border:1px solid #333;
                        border-radius:6px; color:#ddd;
                        font-family:'Consolas','Courier New',monospace;
                        font-size:8.5pt; padding:4px; }
        """)
        layout.addWidget(self.file_log, 1)   # stretch — fills available space

        # ── Log ───────────────────────────────────────────────────────────────
        layout.addWidget(_label("LOG", bold=True, size=8, color="#555555"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(80)
        self.log_area.setStyleSheet("""
            QTextEdit { background:#1e1e1e; border:1px solid #333;
                        border-radius:6px; color:#aaa;
                        font-family:'Consolas','Courier New',monospace;
                        font-size:8pt; padding:4px; }
        """)
        layout.addWidget(self.log_area)

        # ── Bottom row: threads + start/cancel ────────────────────────────────
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        bottom.setContentsMargins(0, 2, 0, 0)
        bottom.addWidget(_label("Threads:", color="#888888", size=9))

        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 64)
        self.thread_spin.setValue(16)
        self.thread_spin.setFixedSize(68, 30)
        self.thread_spin.setStyleSheet("""
            QSpinBox { background:#2a2a2a; border:1px solid #3a3a3a;
                       border-radius:4px; color:#e0e0e0;
                       padding:2px 6px; font-size:10pt; }
            QSpinBox::up-button, QSpinBox::down-button
                { width:16px; background:#333; border:none; }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover
                { background:#444; }
        """)
        bottom.addWidget(self.thread_spin)
        bottom.addStretch()

        self.action_btn = QPushButton("▶  Start Transfer")
        self.action_btn.setFixedHeight(36)
        self.action_btn.setMinimumWidth(160)
        self._style_start()
        self.action_btn.clicked.connect(self._on_action)
        bottom.addWidget(self.action_btn)
        layout.addLayout(bottom)

        # Connect VM
        self.vm.log_updated.connect(self._append_log)
        self.vm.file_batch.connect(self._on_file_batch)
        self.vm.stats_update.connect(self.stats_bar.update_stats)
        self.vm.ui_busy.connect(self._set_busy)

    def _pick(self, line_edit):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            line_edit.setText(folder)

    def _append_log(self, msg):
        self.log_area.append(msg)
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_file_batch(self, rows):
        if not rows:
            return
        parts = []
        for name, size, status in rows:
            icon  = FILE_ICON.get(status, "·")
            color = FILE_COLOR.get(status, "#888888")
            safe  = name.replace("&", "&amp;").replace("<", "&lt;")
            parts.append(
                f'<span style="color:{color}">{icon}</span>'
                f'&nbsp;{safe}'
                f'<span style="color:#555555"> &nbsp;{size}</span>'
            )
        cursor = self.file_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.file_log.setTextCursor(cursor)
        self.file_log.insertHtml("<br>".join(parts) + "<br>")
        sb = self.file_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_action(self):
        if self.action_btn.text().startswith("▶"):
            self.log_area.clear()
            self.file_log.clear()
            self.stats_bar.reset()
            self.vm.start_copy(
                src=self.src_card.text(),
                dst=self.dst_card.text(),
                workers=self.thread_spin.value(),
            )
        else:
            self.action_btn.setEnabled(False)
            self.vm.cancel_copy()

    def _set_busy(self, busy: bool):
        self.action_btn.setEnabled(True)
        self.src_card.set_enabled(not busy)
        self.dst_card.set_enabled(not busy)
        self.thread_spin.setEnabled(not busy)
        self._style_cancel() if busy else self._style_start()

    def _style_start(self):
        self.action_btn.setText("▶  Start Transfer")
        self.action_btn.setStyleSheet("""
            QPushButton { background:#1a73e8; border:none; border-radius:6px;
                          color:white; font-size:10pt; font-weight:bold; padding:0 18px; }
            QPushButton:hover    { background:#1565c0; }
            QPushButton:pressed  { background:#0d47a1; }
            QPushButton:disabled { background:#333; color:#555; }
        """)

    def _style_cancel(self):
        self.action_btn.setText("■  Cancel")
        self.action_btn.setStyleSheet("""
            QPushButton { background:#c62828; border:none; border-radius:6px;
                          color:white; font-size:10pt; font-weight:bold; padding:0 18px; }
            QPushButton:hover    { background:#b71c1c; }
            QPushButton:pressed  { background:#7f0000; }
            QPushButton:disabled { background:#333; color:#555; }
        """)


# ── SMB TREE WIDGET ───────────────────────────────────────────────────────────

class SMBTreeWidget(QTreeWidget):
    """
    Lazy-loading tree. Each folder item stores its UNC path in
    Qt.UserRole data and starts collapsed. On first expand the VM
    fetches children and populates them.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setCheckStateTracking(True)

    def setCheckStateTracking(self, _):
        """PyQt6 doesn't have this natively — we handle via itemChanged."""
        pass

    def add_entries(self, entries: list[SMBEntry], parent_item=None):
        target = parent_item if parent_item else self.invisibleRootItem()
        for e in entries:
            item = QTreeWidgetItem(target)
            icon = "📁 " if e.is_dir else "📄 "
            item.setText(0, icon + e.name)
            item.setData(0, Qt.ItemDataRole.UserRole, (e.path, e.is_dir))
            item.setCheckState(0, Qt.CheckState.Unchecked)
            if e.is_dir:
                # Placeholder child so the expand arrow appears
                placeholder = QTreeWidgetItem(item)
                placeholder.setText(0, "  Loading…")
                placeholder.setData(0, Qt.ItemDataRole.UserRole, None)
                placeholder.setFlags(Qt.ItemFlag.NoItemFlags)

    def populate_dir(self, unc_path: str, entries: list[SMBEntry]):
        """Replace the placeholder child of the matching item with real entries."""
        item = self._find_item(unc_path)
        if item is None:
            return
        # Remove placeholder
        while item.childCount():
            item.removeChild(item.child(0))
        self.add_entries(entries, item)

    def _find_item(self, unc_path: str):
        return self._search(self.invisibleRootItem(), unc_path)

    def _search(self, parent, unc_path: str):
        for i in range(parent.childCount()):
            child = parent.child(i)
            data = child.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == unc_path:
                return child
            found = self._search(child, unc_path)
            if found:
                return found
        return None

    def get_checked_paths(self) -> list[str]:
        result = []
        self._collect_checked(self.invisibleRootItem(), result)
        return result

    def _collect_checked(self, parent, result: list):
        for i in range(parent.childCount()):
            child = parent.child(i)
            data  = child.data(0, Qt.ItemDataRole.UserRole)
            if child.checkState(0) == Qt.CheckState.Checked and data:
                result.append(data[0])
            else:
                self._collect_checked(child, result)

    def propagate_check(self, item, state):
        """Check/uncheck all children when a parent is toggled."""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                child.setCheckState(0, state)
                self.propagate_check(child, state)


# ── NETWORK TAB ───────────────────────────────────────────────────────────────

class NetworkTab(QWidget):
    def __init__(self, vm: NetworkViewModel):
        super().__init__()
        self.vm = vm
        self._expanding: set[str] = set()   # UNC paths currently being fetched
        self._block_check_signal = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # ── credential panel ──────────────────────────────────────────────────
        cred_frame = QFrame()
        cred_frame.setStyleSheet("""
            QFrame { background:#252525; border:1px solid #333;
                     border-radius:6px; }
        """)
        cred_layout = QVBoxLayout(cred_frame)
        cred_layout.setContentsMargins(12, 10, 12, 10)
        cred_layout.setSpacing(8)
        cred_layout.addWidget(_label("SMB / NETWORK SHARE", bold=True,
                                     size=8, color="#888888"))

        grid = QHBoxLayout()
        grid.setSpacing(8)

        self.server_input    = _line_edit("Server IP or hostname")
        self.share_input     = _line_edit("Share name  (e.g. shared)")
        self.username_input  = _line_edit("Username")
        self.password_input  = _line_edit("Password", password=True)

        for w in (self.server_input, self.share_input,
                  self.username_input, self.password_input):
            grid.addWidget(w)

        self.connect_btn = QPushButton("⚡  Connect")
        self.connect_btn.setFixedHeight(34)
        self.connect_btn.setMinimumWidth(110)
        self.connect_btn.setStyleSheet("""
            QPushButton { background:#1a73e8; border:none; border-radius:5px;
                          color:white; font-size:9pt; font-weight:bold; }
            QPushButton:hover    { background:#1565c0; }
            QPushButton:pressed  { background:#0d47a1; }
            QPushButton:disabled { background:#333; color:#555; }
        """)
        self.connect_btn.clicked.connect(self._on_connect)
        grid.addWidget(self.connect_btn)

        cred_layout.addLayout(grid)

        # Status label
        self.conn_status = _label("Not connected", size=8, color="#666666")
        cred_layout.addWidget(self.conn_status)
        layout.addWidget(cred_frame)

        # ── tree ──────────────────────────────────────────────────────────────
        tree_header_row = QHBoxLayout()
        tree_header_row.addWidget(
            _label("REMOTE FILES", bold=True, size=8, color="#555555"))
        tree_header_row.addStretch()

        self.sel_all_btn   = _btn("✓ All")
        self.sel_none_btn  = _btn("✗ None")
        self.sel_all_btn.setFixedWidth(72)
        self.sel_none_btn.setFixedWidth(72)
        self.sel_all_btn.clicked.connect(self._select_all)
        self.sel_none_btn.clicked.connect(self._select_none)
        tree_header_row.addWidget(self.sel_all_btn)
        tree_header_row.addWidget(self.sel_none_btn)
        layout.addLayout(tree_header_row)

        self.tree = SMBTreeWidget()
        self.tree.setMinimumHeight(200)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, 1)

        # ── destination + stats ───────────────────────────────────────────────
        self.dst_card = PathCard("DOWNLOAD DESTINATION", "Choose destination folder…")
        self.dst_card.browse_btn.clicked.connect(
            lambda: self._pick_dst())
        layout.addWidget(self.dst_card)

        self.stats_bar = StatsBar()
        layout.addWidget(self.stats_bar)

        # File list
        layout.addWidget(_label("FILES", bold=True, size=8, color="#555555"))
        self.file_log = QTextEdit()
        self.file_log.setReadOnly(True)
        self.file_log.setFixedHeight(130)
        self.file_log.setStyleSheet("""
            QTextEdit { background:#1e1e1e; border:1px solid #333;
                        border-radius:6px; color:#ddd;
                        font-family:'Consolas','Courier New',monospace;
                        font-size:8.5pt; padding:4px; }
        """)
        layout.addWidget(self.file_log)

        # Log
        layout.addWidget(_label("LOG", bold=True, size=8, color="#555555"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(70)
        self.log_area.setStyleSheet("""
            QTextEdit { background:#1e1e1e; border:1px solid #333;
                        border-radius:6px; color:#aaa;
                        font-family:'Consolas','Courier New',monospace;
                        font-size:8pt; padding:4px; }
        """)
        layout.addWidget(self.log_area)

        # Download button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.download_btn = QPushButton("⬇  Download Selected")
        self.download_btn.setFixedHeight(38)
        self.download_btn.setMinimumWidth(190)
        self.download_btn.setEnabled(False)
        self._style_download()
        self.download_btn.clicked.connect(self._on_download_action)
        btn_row.addWidget(self.download_btn)
        layout.addLayout(btn_row)

        # Connect VM signals
        self.vm.connect_ok.connect(self._on_connect_ok)
        self.vm.connect_err.connect(self._on_connect_err)
        self.vm.expand_ok.connect(self._on_expand_ok)
        self.vm.expand_err.connect(self._on_expand_err)
        self.vm.log_updated.connect(self._append_log)
        self.vm.file_batch.connect(self._on_file_batch)
        self.vm.stats_update.connect(self.stats_bar.update_stats)
        self.vm.ui_busy.connect(self._set_busy)

    # ── credential / connect ──────────────────────────────────────────────────

    def _on_connect(self):
        server   = self.server_input.text().strip()
        share    = self.share_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not server or not share:
            self.conn_status.setText("⚠  Please fill in Server IP and Share name.")
            self.conn_status.setStyleSheet("color:#f0c040; font-size:8pt;")
            return

        self.connect_btn.setEnabled(False)
        self.conn_status.setText(f"Connecting to \\\\{server}\\{share} …")
        self.conn_status.setStyleSheet("color:#888; font-size:8pt;")
        self.tree.clear()

        self.vm.connect_share(server, username, password, share)

    def _on_connect_ok(self, entries: list):
        self.connect_btn.setEnabled(True)
        server = self.server_input.text().strip()
        share  = self.share_input.text().strip()
        self.conn_status.setText(f"✓  Connected to \\\\{server}\\{share}")
        self.conn_status.setStyleSheet("color:#4caf50; font-size:8pt;")
        self.tree.clear()
        self.tree.add_entries(entries)
        self.download_btn.setEnabled(True)

    def _on_connect_err(self, msg: str):
        self.connect_btn.setEnabled(True)
        self.conn_status.setText(f"✗  {msg}")
        self.conn_status.setStyleSheet("color:#f44336; font-size:8pt;")

    # ── tree expansion (lazy loading) ─────────────────────────────────────────

    def _on_item_expanded(self, item: QTreeWidgetItem):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        unc_path, is_dir = data
        if not is_dir:
            return
        # Check if still has only the placeholder child
        if item.childCount() == 1:
            child_data = item.child(0).data(0, Qt.ItemDataRole.UserRole)
            if child_data is None and unc_path not in self._expanding:
                self._expanding.add(unc_path)
                self.vm.expand_dir(unc_path)

    def _on_expand_ok(self, unc_path: str, entries: list):
        self._expanding.discard(unc_path)
        self._block_check_signal = True
        self.tree.populate_dir(unc_path, entries)
        self._block_check_signal = False

    def _on_expand_err(self, unc_path: str, msg: str):
        self._expanding.discard(unc_path)
        self._append_log(f"⚠ Could not expand '{unc_path}': {msg}")

    # ── check-state propagation ───────────────────────────────────────────────

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        if self._block_check_signal or column != 0:
            return
        self._block_check_signal = True
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data[1]:  # is_dir
            self.tree.propagate_check(item, item.checkState(0))
        self._block_check_signal = False

    def _select_all(self):
        self._block_check_signal = True
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            child = root.child(i)
            child.setCheckState(0, Qt.CheckState.Checked)
            self.tree.propagate_check(child, Qt.CheckState.Checked)
        self._block_check_signal = False

    def _select_none(self):
        self._block_check_signal = True
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            child = root.child(i)
            child.setCheckState(0, Qt.CheckState.Unchecked)
            self.tree.propagate_check(child, Qt.CheckState.Unchecked)
        self._block_check_signal = False

    # ── destination ───────────────────────────────────────────────────────────

    def _pick_dst(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.dst_card.path_input.setText(folder)

    # ── download ──────────────────────────────────────────────────────────────

    def _on_download_action(self):
        if self.download_btn.text().startswith("⬇"):
            self._start_download()
        else:
            self.download_btn.setEnabled(False)
            self.vm.cancel_download()

    def _start_download(self):
        dst = self.dst_card.text()
        if not dst:
            QMessageBox.warning(self, "No Destination",
                                "Please select a destination folder first.")
            return
        checked = self.tree.get_checked_paths()
        if not checked:
            QMessageBox.warning(self, "Nothing Selected",
                                "Please tick at least one file or folder.")
            return
        self.log_area.clear()
        self.file_log.clear()
        self.stats_bar.reset()
        self.vm.start_download(checked, dst)

    def _set_busy(self, busy: bool):
        self.download_btn.setEnabled(True)
        self.connect_btn.setEnabled(not busy)
        self.dst_card.set_enabled(not busy)
        if busy:
            self._style_cancel_download()
        else:
            self._style_download()

    def _style_download(self):
        self.download_btn.setText("⬇  Download Selected")
        self.download_btn.setStyleSheet("""
            QPushButton { background:#1a73e8; border:none; border-radius:6px;
                          color:white; font-size:10pt; font-weight:bold; padding:0 18px; }
            QPushButton:hover    { background:#1565c0; }
            QPushButton:pressed  { background:#0d47a1; }
            QPushButton:disabled { background:#333; color:#555; }
        """)

    def _style_cancel_download(self):
        self.download_btn.setText("■  Cancel")
        self.download_btn.setStyleSheet("""
            QPushButton { background:#c62828; border:none; border-radius:6px;
                          color:white; font-size:10pt; font-weight:bold; padding:0 18px; }
            QPushButton:hover    { background:#b71c1c; }
            QPushButton:pressed  { background:#7f0000; }
            QPushButton:disabled { background:#333; color:#555; }
        """)

    # ── shared log helpers ────────────────────────────────────────────────────

    def _append_log(self, msg):
        self.log_area.append(msg)
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_file_batch(self, rows):
        if not rows:
            return
        parts = []
        for name, size, status in rows:
            icon  = FILE_ICON.get(status, "·")
            color = FILE_COLOR.get(status, "#888888")
            safe  = name.replace("&", "&amp;").replace("<", "&lt;")
            parts.append(
                f'<span style="color:{color}">{icon}</span>'
                f'&nbsp;{safe}'
                f'<span style="color:#555555"> &nbsp;{size}</span>'
            )
        cursor = self.file_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.file_log.setTextCursor(cursor)
        self.file_log.insertHtml("<br>".join(parts) + "<br>")
        sb = self.file_log.verticalScrollBar()
        sb.setValue(sb.maximum())


# ── MAIN WINDOW ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, vm: MainViewModel) -> None:
        super().__init__()
        self.vm      = vm
        self.net_vm  = NetworkViewModel()

        self.setWindowTitle("RoboCopy")
        self.resize(780, 720)
        self.setStyleSheet(DARK)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.local_tab   = LocalTab(self.vm)
        self.network_tab = NetworkTab(self.net_vm)

        self.tabs.addTab(self.local_tab,   "💻  Local")
        self.tabs.addTab(self.network_tab, "🌐  Network")

        layout.addWidget(self.tabs)
