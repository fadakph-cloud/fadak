# -*- coding: utf-8 -*-
"""ابزار چاپ فدک — مبدل فرمت فایل‌ها با ظاهر مدرن"""
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QProgressBar, QPushButton, QSpinBox,
    QTextEdit, QVBoxLayout, QWidget,
)

import converters as cv

APP_NAME = "ابزار چاپ فدک"
APP_VERSION = "2.0.0"
AUTHOR = "محمدرضا جباری"
COMPANY = "چاپ و تبلیغات فدک"
EITAA_URL = "https://eitaa.com/fadakph"
EITAA_ID = "@fadakph"

# پالت رنگی الهام‌گرفته از iOS
BG = "#F2F2F7"
CARD = "#FFFFFF"
TEXT = "#1C1C1E"
SUB = "#8E8E93"
BLUE = "#007AFF"
BLUE_HOVER = "#0A84FF"
SEP = "#E5E5EA"

STYLE = f"""
QWidget {{ color: {TEXT}; }}
QWidget#root {{ background: {BG}; }}
QLabel#h1 {{ font-size: 24pt; font-weight: 800; }}
QLabel#sub {{ color: {SUB}; font-size: 11pt; }}
QLabel#section {{ color: {SUB}; font-size: 10pt; font-weight: 600; }}
QLabel#dropIcon {{
    background: {BLUE}; color: white; border-radius: 30px;
    font-size: 26pt; font-weight: 700; min-width: 60px; max-width: 60px;
    min-height: 60px; max-height: 60px;
}}
QLabel#dropTitle {{ font-size: 14pt; font-weight: 700; }}
QLabel#dropSub {{ color: {SUB}; font-size: 10pt; }}

QFrame#card {{ background: {CARD}; border-radius: 20px; }}
QFrame#drop {{
    background: #F7F9FF; border: 2px dashed #B9D4FF; border-radius: 18px;
}}
QFrame#drop[hover="true"] {{ background: #E5F0FF; border-color: {BLUE}; }}

QListWidget {{
    background: {BG}; border: none; border-radius: 14px; padding: 6px; outline: 0;
}}
QListWidget::item {{ background: {CARD}; border-radius: 10px; padding: 10px 12px; margin: 3px; }}
QListWidget::item:selected {{ background: #E5F0FF; color: {TEXT}; }}

QPushButton {{
    background: #EEF0F5; border: none; border-radius: 12px; padding: 9px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background: #E2E5EC; }}
QPushButton:disabled {{ color: #B0B3BA; }}
QPushButton#primary {{
    background: {BLUE}; color: white; font-size: 13pt; font-weight: 700;
    padding: 14px 40px; border-radius: 16px;
}}
QPushButton#primary:hover {{ background: {BLUE_HOVER}; }}
QPushButton#primary:disabled {{ background: #A8CFFF; color: white; }}
QPushButton#danger {{ color: #FF3B30; background: #FFEDEC; }}
QPushButton#danger:hover {{ background: #FFDCD9; }}
QPushButton#pill {{ background: #EEF0F5; border-radius: 16px; padding: 7px 16px; }}

QPushButton#seg {{
    background: #EEF0F5; border-radius: 10px; padding: 8px 14px; font-weight: 500;
}}
QPushButton#seg:checked {{ background: {CARD}; color: {BLUE}; font-weight: 700; }}

QComboBox, QSpinBox {{
    background: #F2F2F7; border: 1px solid transparent; border-radius: 12px;
    padding: 8px 12px; min-height: 22px; min-width: 200px;
}}
QComboBox:focus, QSpinBox:focus {{ border: 1px solid {BLUE}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border-radius: 10px; selection-background-color: #E5F0FF;
    selection-color: {TEXT}; padding: 4px; outline: 0;
}}

QCheckBox {{ spacing: 10px; font-weight: 500; }}
QCheckBox::indicator {{
    width: 22px; height: 22px; border-radius: 11px; border: 2px solid #C7C7CC; background: white;
}}
QCheckBox::indicator:checked {{ background: {BLUE}; border: 2px solid {BLUE}; }}

QProgressBar {{
    background: #EEF0F5; border: none; border-radius: 7px; min-height: 14px; max-height: 14px;
    text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {BLUE}; border-radius: 7px; }}

QTextEdit {{
    background: #F9F9FB; border: none; border-radius: 14px; padding: 10px;
    font-size: 10pt; color: #3A3A3C;
}}
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


def fmt_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return str(n)


def card(layout) -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    f.setLayout(layout)
    shadow = QGraphicsDropShadowEffect(f)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(0, 0, 0, 30))
    f.setGraphicsEffect(shadow)
    return f


# ------------------------------------------------------------------ نخ کاری
class Worker(QThread):
    progress = Signal(int)
    log = Signal(str)
    done = Signal(int, int, list)

    def __init__(self, files, key, out_dir, quality, opts):
        super().__init__()
        self.files, self.key, self.out_dir = files, key, out_dir
        self.quality, self.opts = quality, opts
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        ok = bad = 0
        outputs = []
        target = cv.TARGET_BY_KEY[self.key]
        compatible = []
        for f in self.files:
            if cv.category(f) in target[2]:
                compatible.append(f)
            else:
                self.log.emit(f"⚠ رد شد (ناسازگار): {Path(f).name}")
                bad += 1

        if target[3]:  # ادغام
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
                res = cv.convert_one(f, self.key, self.out_dir, self.quality, opts=self.opts)
                outputs += res
                ok += 1
                msg = f"✔ {res[0].name}"
                if self.key == "compress" and res[0].is_file():
                    before = Path(f).stat().st_size
                    after = res[0].stat().st_size
                    saved = (1 - after / before) * 100 if before else 0
                    msg += f"   {fmt_size(before)} ← {fmt_size(after)}  (کاهش {saved:.0f}٪)"
                self.log.emit(msg)
            except Exception as e:
                bad += 1
                self.log.emit(f"✘ {Path(f).name}: {e}")
            self.progress.emit(int(i * 100 / total))
        self.done.emit(ok, bad, outputs)


# ------------------------------------------------------------------ ناحیهٔ رها کردن
class DropZone(QFrame):
    files_dropped = Signal(list)
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(130)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(18)
        icon = QLabel("+")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignCenter)
        txt = QVBoxLayout()
        t = QLabel("فایل‌ها را اینجا بکشید")
        t.setObjectName("dropTitle")
        s = QLabel("یا کلیک کنید تا انتخاب کنید • تصویر، PSD، PDF، صوت، ویدیو و اسناد")
        s.setObjectName("dropSub")
        s.setWordWrap(True)
        txt.addWidget(t)
        txt.addWidget(s)
        lay.addWidget(icon)
        lay.addLayout(txt, 1)

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
        self.files_dropped.emit([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def mouseReleaseEvent(self, e):
        self.clicked.emit()


# ------------------------------------------------------------------ درباره ما
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("درباره ما")
        self.setMinimumWidth(400)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 30, 30, 24)
        lay.setSpacing(10)
        icon = QLabel("+")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(72, 72)
        lay.addWidget(icon, alignment=Qt.AlignCenter)
        t = QLabel(APP_NAME)
        t.setObjectName("h1")
        t.setAlignment(Qt.AlignCenter)
        v = QLabel(f"نسخهٔ {APP_VERSION}")
        v.setObjectName("sub")
        v.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        lay.addWidget(v)
        info = QLabel(
            f"<p align='center' style='line-height:170%'>"
            f"مبدل فرمت تصویر، PSD، PDF، صوت، ویدیو و اسناد<br>"
            f"<b>سازنده:</b> {AUTHOR}<br><b>{COMPANY}</b><br>"
            f"کانال ایتا: <a href='{EITAA_URL}'>{EITAA_ID}</a></p>"
        )
        info.setTextFormat(Qt.RichText)
        info.setOpenExternalLinks(True)
        info.setAlignment(Qt.AlignCenter)
        lay.addWidget(info)
        btn = QPushButton("بستن")
        btn.setObjectName("primary")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn, alignment=Qt.AlignCenter)


# ------------------------------------------------------------------ پنجرهٔ اصلی
class MainWindow(QMainWindow):
    QUALITY_PRESETS = [("متعادل", 26), ("کم‌حجم", 30), ("خیلی کم‌حجم", 34)]
    RESOLUTIONS = [("اندازهٔ اصلی", 0), ("۱۰۸۰p", 1080), ("۷۲۰p", 720), ("۴۸۰p", 480)]
    CODECS = [("H.264 (سازگار با همه)", False), ("H.265 (حجم کمتر، کندتر)", True)]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(820, 940)
        self.setMinimumSize(720, 800)
        ico = cv.app_dir() / "assets" / "icon.ico"
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))
        self.worker = None
        self.out_folder = None
        self.last_outputs = []

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(16)

        # ---- سربرگ
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        t = QLabel(APP_NAME)
        t.setObjectName("h1")
        s = QLabel("تبدیل فایل‌ها، کاملاً آفلاین و بدون آپلود")
        s.setObjectName("sub")
        titles.addWidget(t)
        titles.addWidget(s)
        head.addLayout(titles, 1)
        about = QPushButton("درباره ما")
        about.setObjectName("pill")
        about.setCursor(Qt.PointingHandCursor)
        about.clicked.connect(lambda: AboutDialog(self).exec())
        head.addWidget(about, alignment=Qt.AlignTop)
        outer.addLayout(head)

        # ---- کارت ورودی
        self.drop = DropZone()
        self.drop.files_dropped.connect(self.add_paths)
        self.drop.clicked.connect(self.browse_files)

        self.listw = QListWidget()
        self.listw.setSelectionMode(QListWidget.ExtendedSelection)
        self.listw.setMinimumHeight(170)

        actions = QHBoxLayout()
        self.count_lbl = QLabel("هیچ فایلی انتخاب نشده")
        self.count_lbl.setObjectName("sub")
        actions.addWidget(self.count_lbl, 1)
        for text, slot, obj in (
            ("افزودن پوشه", self.browse_folder, None),
            ("حذف انتخاب‌شده", self.remove_selected, None),
            ("پاک کردن همه", self.clear_all, "danger"),
        ):
            b = QPushButton(text)
            if obj:
                b.setObjectName(obj)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            actions.addWidget(b)

        inp = QVBoxLayout()
        inp.setSpacing(14)
        inp.setContentsMargins(20, 20, 20, 18)
        inp.addWidget(self.drop)
        inp.addWidget(self.listw)
        inp.addLayout(actions)
        outer.addWidget(card(inp))

        # ---- کارت تنظیمات
        setlay = QVBoxLayout()
        setlay.setContentsMargins(20, 18, 20, 18)
        setlay.setSpacing(14)

        row = QHBoxLayout()
        lbl = QLabel("تبدیل به")
        lbl.setObjectName("section")
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self.on_target_changed)
        row.addWidget(lbl)
        row.addWidget(self.combo, 1)
        row.addSpacing(18)
        self.qlbl = QLabel("کیفیت تصویر")
        self.qlbl.setObjectName("section")
        self.quality = QSpinBox()
        self.quality.setRange(10, 100)
        self.quality.setValue(90)
        self.quality.setMinimumWidth(90)
        row.addWidget(self.qlbl)
        row.addWidget(self.quality)
        setlay.addLayout(row)

        # پنل کاهش حجم ویدیو
        self.compress_box = QWidget()
        cb = QVBoxLayout(self.compress_box)
        cb.setContentsMargins(0, 4, 0, 0)
        cb.setSpacing(12)
        seg_title = QLabel("میزان فشرده‌سازی")
        seg_title.setObjectName("section")
        cb.addWidget(seg_title)
        seg_row = QHBoxLayout()
        seg_row.setSpacing(8)
        self.seg_group = QButtonGroup(self)
        self.seg_group.setExclusive(True)
        for i, (name, _) in enumerate(self.QUALITY_PRESETS):
            b = QPushButton(name)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            if i == 0:
                b.setChecked(True)
            self.seg_group.addButton(b, i)
            seg_row.addWidget(b)
        seg_row.addStretch()
        cb.addLayout(seg_row)

        opt_row = QHBoxLayout()
        self.res_combo = QComboBox()
        for name, val in self.RESOLUTIONS:
            self.res_combo.addItem(name, val)
        self.res_combo.setCurrentIndex(2)  # ۷۲۰p پیش‌فرض
        self.codec_combo = QComboBox()
        for name, val in self.CODECS:
            self.codec_combo.addItem(name, val)
        r_lbl = QLabel("اندازه تصویر")
        r_lbl.setObjectName("section")
        c_lbl = QLabel("فرمت فشرده")
        c_lbl.setObjectName("section")
        opt_row.addWidget(r_lbl)
        opt_row.addWidget(self.res_combo, 1)
        opt_row.addSpacing(16)
        opt_row.addWidget(c_lbl)
        opt_row.addWidget(self.codec_combo, 1)
        cb.addLayout(opt_row)
        setlay.addWidget(self.compress_box)

        out_row = QHBoxLayout()
        self.chk_other = QCheckBox("ذخیره در پوشهٔ دیگر")
        self.chk_other.toggled.connect(self.on_out_toggle)
        self.btn_out = QPushButton("انتخاب پوشه")
        self.btn_out.setEnabled(False)
        self.btn_out.setCursor(Qt.PointingHandCursor)
        self.btn_out.clicked.connect(self.choose_out)
        self.out_lbl = QLabel("نتیجه کنار فایل اصلی ذخیره می‌شود")
        self.out_lbl.setObjectName("sub")
        self.out_lbl.setWordWrap(True)
        out_row.addWidget(self.chk_other)
        out_row.addWidget(self.btn_out)
        out_row.addWidget(self.out_lbl, 1)
        setlay.addLayout(out_row)
        outer.addWidget(card(setlay))

        # ---- کارت اجرا
        runlay = QVBoxLayout()
        runlay.setContentsMargins(20, 18, 20, 18)
        runlay.setSpacing(14)
        btns = QHBoxLayout()
        self.btn_start = QPushButton("شروع تبدیل")
        self.btn_start.setObjectName("primary")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self.start)
        self.btn_cancel = QPushButton("توقف")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_open = QPushButton("باز کردن پوشهٔ نتیجه")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_result)
        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_cancel)
        btns.addStretch()
        btns.addWidget(self.btn_open)
        runlay.addLayout(btns)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        runlay.addWidget(self.bar)
        self.logw = QTextEdit()
        self.logw.setReadOnly(True)
        self.logw.setMinimumHeight(120)
        runlay.addWidget(self.logw)
        outer.addWidget(card(runlay), 1)

        self.refresh_targets()

    # ---- فهرست فایل‌ها
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
            cat = cv.category(p)
            if cat is None:
                skipped += 1
                continue
            sp = str(p)
            if sp in existing:
                continue
            existing.add(sp)
            item = QListWidgetItem(f"{p.name}\n{cv.CATEGORY_NAMES[cat]}  •  {fmt_size(p.stat().st_size)}")
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
        self.combo.blockSignals(True)
        self.combo.clear()
        for key, label, tcats, _ in cv.TARGETS:
            if tcats & cats:
                self.combo.addItem(label, key)
        self.combo.blockSignals(False)
        n = len(files)
        self.count_lbl.setText(f"{n} فایل انتخاب شده" if n else "هیچ فایلی انتخاب نشده")
        self.on_target_changed()

    def on_target_changed(self):
        key = self.combo.currentData()
        is_compress = key == "compress"
        is_image_out = key in ("jpg", "webp")
        self.compress_box.setVisible(is_compress)
        self.qlbl.setVisible(is_image_out)
        self.quality.setVisible(is_image_out)
        self.btn_start.setEnabled(bool(self.current_files()) and self.combo.count() > 0 and self.worker is None)

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
    def current_opts(self):
        if self.combo.currentData() != "compress":
            return {}
        crf = self.QUALITY_PRESETS[self.seg_group.checkedId()][1]
        return {
            "crf": crf,
            "max_h": self.res_combo.currentData(),
            "hevc": self.codec_combo.currentData(),
        }

    def start(self):
        key = self.combo.currentData()
        if not key:
            return
        self.bar.setValue(0)
        self.logw.clear()
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_open.setEnabled(False)
        self.worker = Worker(self.current_files(), key, self.out_folder, self.quality.value(), self.current_opts())
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
        self.logw.append(f"\nپایان کار — موفق: {ok}   ناموفق: {bad}")
        self.on_target_changed()

    def open_result(self):
        if not self.last_outputs:
            return
        p = Path(self.last_outputs[0])
        folder = p if p.is_dir() else p.parent
        if os.name == "nt":
            os.startfile(str(folder))  # noqa
        else:
            subprocess.Popen(["xdg-open", str(folder)])


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setFont(QFont(pick_font(), 10))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
