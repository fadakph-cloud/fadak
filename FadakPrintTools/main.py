# -*- coding: utf-8 -*-
"""ابزار چاپ فدک — مبدل فرمت فایل‌ها"""
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QProgressBar, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

import converters as cv

APP_NAME = "ابزار چاپ فدک"
APP_VERSION = "1.0.0"
AUTHOR = "محمدرضا جباری"
COMPANY = "چاپ و تبلیغات فدک"
EITAA_URL = "https://eitaa.com/fadakph"
EITAA_ID = "@fadakph"

STYLE = """
* { font-size: 11pt; }
QMainWindow, QDialog { background: #f4f6f8; }
QLabel#title { font-size: 20pt; font-weight: bold; color: #0f4c5c; }
QLabel#subtitle { color: #5b6770; }
QFrame#drop { background: white; border: 2px dashed #7aa5b0; border-radius: 14px; }
QFrame#drop[hover="true"] { background: #e6f4f1; border-color: #0f4c5c; }
QLabel#dropText { color: #0f4c5c; font-size: 13pt; }
QListWidget { background: white; border: 1px solid #d5dde2; border-radius: 8px; padding: 4px; }
QListWidget::item { padding: 6px; }
QPushButton { background: white; border: 1px solid #c3ced5; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { background: #eaf1f4; }
QPushButton#primary { background: #0f4c5c; color: white; border: none; font-weight: bold; padding: 10px 28px; }
QPushButton#primary:hover { background: #166a7f; }
QPushButton#primary:disabled { background: #9db5bc; }
QComboBox, QSpinBox { background: white; border: 1px solid #c3ced5; border-radius: 6px; padding: 5px 8px; min-height: 24px; }
QProgressBar { border: 1px solid #c3ced5; border-radius: 8px; background: white; text-align: center; min-height: 22px; }
QProgressBar::chunk { background: #2a9d8f; border-radius: 7px; }
QTextEdit { background: #fbfcfd; border: 1px solid #d5dde2; border-radius: 8px; }
"""


def pick_font() -> str:
    fonts_dir = cv.app_dir() / "fonts"
    if fonts_dir.is_dir():
        for f in sorted(fonts_dir.glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(f))
    families = QFontDatabase.families()
    for name in ("Vazirmatn", "Vazir", "Segoe UI", "Tahoma"):
        if name in families:
            return name
    return QApplication.font().family()


# ------------------------------------------------------------------ نخ کاری
class Worker(QThread):
    progress = Signal(int)
    log = Signal(str)
    done = Signal(int, int, list)  # موفق، ناموفق، پوشه‌های خروجی

    def __init__(self, files, key, out_dir, quality):
        super().__init__()
        self.files, self.key, self.out_dir, self.quality = files, key, out_dir, quality
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        ok = bad = 0
        outputs = []
        target = cv.TARGET_BY_KEY[self.key]
        compatible = [f for f in self.files if cv.category(f) in target[2]]
        for f in self.files:
            if f not in compatible:
                self.log.emit(f"⚠ رد شد (ناسازگار): {Path(f).name}")
                bad += 1

        if target[3]:  # تبدیل گروهی (ادغام)
            try:
                res = cv.merge_to_pdf([Path(f) for f in compatible], self.out_dir)
                outputs += res
                ok += 1
                self.log.emit(f"✔ ساخته شد: {res[0].name}")
            except Exception as e:
                bad += 1
                self.log.emit(f"✘ خطا در ادغام: {e}")
            self.progress.emit(100)
            self.done.emit(ok, bad, outputs)
            return

        total = max(len(compatible), 1)
        for i, f in enumerate(compatible, start=1):
            if self._cancel:
                self.log.emit("⏹ عملیات متوقف شد.")
                break
            self.log.emit(f"… در حال تبدیل: {Path(f).name}")
            try:
                res = cv.convert_one(f, self.key, self.out_dir, self.quality)
                outputs += res
                ok += 1
                self.log.emit(f"✔ {res[0].name}")
            except Exception as e:
                bad += 1
                self.log.emit(f"✘ {Path(f).name}: {e}")
            self.progress.emit(int(i * 100 / total))
        self.done.emit(ok, bad, outputs)


# ------------------------------------------------------------------ ناحیهٔ رها کردن فایل
class DropZone(QFrame):
    files_dropped = Signal(list)
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(110)
        lay = QVBoxLayout(self)
        lbl = QLabel("فایل‌ها را اینجا بکشید و رها کنید\nیا برای انتخاب فایل کلیک کنید")
        lbl.setObjectName("dropText")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)

    def _hover(self, on):
        self.setProperty("hover", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._hover(True)

    def dragLeaveEvent(self, e):
        self._hover(False)

    def dropEvent(self, e):
        self._hover(False)
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        self.files_dropped.emit(paths)

    def mouseReleaseEvent(self, e):
        self.clicked.emit()


# ------------------------------------------------------------------ درباره ما
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"درباره ما — {APP_NAME}")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        t = QLabel(APP_NAME)
        t.setObjectName("title")
        t.setAlignment(Qt.AlignCenter)
        v = QLabel(f"نسخهٔ {APP_VERSION}")
        v.setObjectName("subtitle")
        v.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        lay.addWidget(v)

        info = QLabel(
            f"<p align='center'>مبدل فرمت تصویر، PDF، صوت، ویدیو و اسناد<br>"
            f"<b>سازنده:</b> {AUTHOR}<br>"
            f"<b>{COMPANY}</b></p>"
            f"<p align='center'>کانال ایتا: "
            f"<a href='{EITAA_URL}'>{EITAA_ID}</a></p>"
        )
        info.setTextFormat(Qt.RichText)
        info.setOpenExternalLinks(True)
        info.setAlignment(Qt.AlignCenter)
        lay.addWidget(info)

        note = QLabel("این برنامه از کتابخانه‌های آزاد Pillow، PyMuPDF، FFmpeg و Qt استفاده می‌کند.")
        note.setObjectName("subtitle")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        lay.addWidget(note)

        btn = QPushButton("بستن")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)


# ------------------------------------------------------------------ پنجرهٔ اصلی
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(760, 780)
        ico = cv.app_dir() / "assets" / "icon.ico"
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))
        self.worker = None
        self.out_folder = None
        self.last_outputs = []

        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        # سربرگ
        head = QHBoxLayout()
        titles = QVBoxLayout()
        t = QLabel(APP_NAME)
        t.setObjectName("title")
        s = QLabel("تبدیل سریع فرمت فایل‌ها — کاملاً آفلاین")
        s.setObjectName("subtitle")
        titles.addWidget(t)
        titles.addWidget(s)
        head.addLayout(titles)
        head.addStretch()
        about = QPushButton("درباره ما")
        about.clicked.connect(lambda: AboutDialog(self).exec())
        head.addWidget(about, alignment=Qt.AlignTop)
        lay.addLayout(head)

        # ناحیهٔ رها کردن
        self.drop = DropZone()
        self.drop.files_dropped.connect(self.add_paths)
        self.drop.clicked.connect(self.browse_files)
        lay.addWidget(self.drop)

        # فهرست
        self.listw = QListWidget()
        self.listw.setSelectionMode(QListWidget.ExtendedSelection)
        lay.addWidget(self.listw, 1)

        row = QHBoxLayout()
        b_add = QPushButton("افزودن فایل")
        b_add.clicked.connect(self.browse_files)
        b_dir = QPushButton("افزودن پوشه")
        b_dir.clicked.connect(self.browse_folder)
        b_del = QPushButton("حذف انتخاب‌شده‌ها")
        b_del.clicked.connect(self.remove_selected)
        b_clr = QPushButton("پاک کردن همه")
        b_clr.clicked.connect(self.clear_all)
        for b in (b_add, b_dir, b_del, b_clr):
            row.addWidget(b)
        row.addStretch()
        self.count_lbl = QLabel("۰ فایل")
        self.count_lbl.setObjectName("subtitle")
        row.addWidget(self.count_lbl)
        lay.addLayout(row)

        # گزینه‌ها
        opt = QHBoxLayout()
        opt.addWidget(QLabel("تبدیل به:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(260)
        opt.addWidget(self.combo)
        opt.addSpacing(16)
        opt.addWidget(QLabel("کیفیت تصویر:"))
        self.quality = QSpinBox()
        self.quality.setRange(10, 100)
        self.quality.setValue(90)
        opt.addWidget(self.quality)
        opt.addStretch()
        lay.addLayout(opt)

        outrow = QHBoxLayout()
        self.chk_other = QCheckBox("ذخیره در پوشهٔ دیگر")
        self.chk_other.toggled.connect(self.on_out_toggle)
        self.btn_out = QPushButton("انتخاب پوشه…")
        self.btn_out.setEnabled(False)
        self.btn_out.clicked.connect(self.choose_out)
        self.out_lbl = QLabel("نتیجه کنار فایل اصلی ذخیره می‌شود")
        self.out_lbl.setObjectName("subtitle")
        outrow.addWidget(self.chk_other)
        outrow.addWidget(self.btn_out)
        outrow.addWidget(self.out_lbl, 1)
        lay.addLayout(outrow)

        # اجرا
        run = QHBoxLayout()
        self.btn_start = QPushButton("شروع تبدیل")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self.start)
        self.btn_cancel = QPushButton("توقف")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_open = QPushButton("باز کردن پوشهٔ نتیجه")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_result)
        run.addWidget(self.btn_start)
        run.addWidget(self.btn_cancel)
        run.addStretch()
        run.addWidget(self.btn_open)
        lay.addLayout(run)

        self.bar = QProgressBar()
        lay.addWidget(self.bar)
        self.logw = QTextEdit()
        self.logw.setReadOnly(True)
        self.logw.setMaximumHeight(130)
        lay.addWidget(self.logw)

        self.refresh_targets()

    # ---- مدیریت فهرست
    def current_files(self):
        return [self.listw.item(i).data(Qt.UserRole) for i in range(self.listw.count())]

    def add_paths(self, paths):
        existing = set(self.current_files())
        skipped = 0
        stack = list(paths)
        while stack:
            p = Path(stack.pop(0))
            if p.is_dir():
                stack = sorted(str(x) for x in p.rglob("*") if x.is_file()) + stack
                continue
            if cv.category(p) is None:
                skipped += 1
                continue
            sp = str(p)
            if sp in existing:
                continue
            existing.add(sp)
            item = QListWidgetItem(f"{p.name}   [{cv.CATEGORY_NAMES[cv.category(p)]}]")
            item.setToolTip(sp)
            item.setData(Qt.UserRole, sp)
            self.listw.addItem(item)
        if skipped:
            self.logw.append(f"⚠ {skipped} فایل با فرمت پشتیبانی‌نشده نادیده گرفته شد.")
        self.refresh_targets()

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "انتخاب فایل‌ها")
        if files:
            self.add_paths(files)

    def browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "انتخاب پوشه")
        if d:
            self.add_paths([d])

    def remove_selected(self):
        for it in self.listw.selectedItems():
            self.listw.takeItem(self.listw.row(it))
        self.refresh_targets()

    def clear_all(self):
        self.listw.clear()
        self.refresh_targets()

    def refresh_targets(self):
        files = self.current_files()
        cats = {cv.category(f) for f in files}
        self.combo.clear()
        for key, label, tcats, _ in cv.TARGETS:
            if tcats & cats:
                self.combo.addItem(label, key)
        n = len(files)
        self.count_lbl.setText(f"{n} فایل")
        self.btn_start.setEnabled(n > 0 and self.combo.count() > 0 and self.worker is None)

    # ---- خروجی
    def on_out_toggle(self, on):
        self.btn_out.setEnabled(on)
        if not on:
            self.out_folder = None
            self.out_lbl.setText("نتیجه کنار فایل اصلی ذخیره می‌شود")

    def choose_out(self):
        d = QFileDialog.getExistingDirectory(self, "پوشهٔ خروجی")
        if d:
            self.out_folder = Path(d)
            self.out_lbl.setText(d)
        elif not self.out_folder:
            self.chk_other.setChecked(False)

    # ---- اجرا
    def start(self):
        key = self.combo.currentData()
        if not key:
            return
        self.bar.setValue(0)
        self.logw.clear()
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_open.setEnabled(False)
        self.worker = Worker(self.current_files(), key, self.out_folder, self.quality.value())
        self.worker.progress.connect(self.bar.setValue)
        self.worker.log.connect(self.logw.append)
        self.worker.done.connect(self.finished)
        self.worker.start()

    def cancel(self):
        if self.worker:
            self.worker.cancel()

    def finished(self, ok, bad, outputs):
        self.worker = None
        self.btn_cancel.setEnabled(False)
        self.last_outputs = outputs
        self.btn_open.setEnabled(bool(outputs))
        self.logw.append(f"\nپایان کار — موفق: {ok} | ناموفق: {bad}")
        self.refresh_targets()

    def open_result(self):
        if not self.last_outputs:
            return
        p = Path(self.last_outputs[0])
        folder = p if p.is_dir() else p.parent
        if os.name == "nt":
            os.startfile(str(folder))  # noqa
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(folder)])


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setFont(QFont(pick_font(), 10))
    app.setStyleSheet(STYLE)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
