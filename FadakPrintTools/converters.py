# -*- coding: utf-8 -*-
"""موتور تبدیل — بدون وابستگی به رابط کاربری.
همهٔ مسیرها به‌صورت یونیکد پردازش می‌شوند و برای موتورهای بیرونی
(ffmpeg / LibreOffice) فایل در صورت نیاز با نام انگلیسی موقت کپی می‌شود،
بنابراین مسیرهای فارسی مشکلی ایجاد نمی‌کنند.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------- مسیر برنامه
def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# ---------------------------------------------------------------- دسته‌بندی فایل‌ها
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".ico", ".jfif"}
PDF_EXT = {".pdf"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".3gp", ".ts", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus", ".aiff"}
OFFICE_EXT = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf", ".txt"}

CATEGORY_NAMES = {
    "image": "تصویر", "pdf": "PDF", "video": "ویدیو",
    "audio": "صوت", "office": "سند آفیس",
}


def category(path) -> str | None:
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in PDF_EXT:
        return "pdf"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in OFFICE_EXT:
        return "office"
    return None


# ---------------------------------------------------------------- فهرست تبدیل‌ها
# (کلید، عنوان فارسی، دسته‌های ورودی، گروهی؟)
TARGETS = [
    ("png",       "تصویر PNG",                         {"image"}, False),
    ("jpg",       "تصویر JPG",                         {"image"}, False),
    ("webp",      "تصویر WEBP",                        {"image"}, False),
    ("bmp",       "تصویر BMP",                         {"image"}, False),
    ("tiff",      "تصویر TIFF",                        {"image"}, False),
    ("gif",       "تصویر GIF",                         {"image"}, False),
    ("ico",       "آیکون ICO",                         {"image"}, False),
    ("img2pdf",   "PDF (از هر تصویر یک فایل)",         {"image"}, False),
    ("merge_pdf", "ادغام همه در یک فایل PDF",          {"image", "pdf"}, True),
    ("pdf2png",   "PDF ← تصاویر PNG (هر صفحه)",        {"pdf"}, False),
    ("pdf2jpg",   "PDF ← تصاویر JPG (هر صفحه)",        {"pdf"}, False),
    ("pdf2txt",   "PDF ← متن TXT",                     {"pdf"}, False),
    ("split",     "جدا کردن صفحات PDF",                {"pdf"}, False),
    ("office2pdf", "تبدیل به PDF",                     {"office"}, False),
    ("mp4",       "ویدیو MP4",                         {"video"}, False),
    ("mkv",       "ویدیو MKV",                         {"video"}, False),
    ("webm",      "ویدیو WEBM",                        {"video"}, False),
    ("gif_v",     "ویدیو ← GIF متحرک",                 {"video"}, False),
    ("mp3",       "صوت MP3",                           {"video", "audio"}, False),
    ("m4a",       "صوت M4A",                           {"video", "audio"}, False),
    ("wav",       "صوت WAV",                           {"video", "audio"}, False),
    ("flac",      "صوت FLAC",                          {"video", "audio"}, False),
    ("ogg",       "صوت OGG",                           {"video", "audio"}, False),
]
TARGET_BY_KEY = {t[0]: t for t in TARGETS}

FFMPEG_ARGS = {
    "mp4":  (".mp4",  ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]),
    "mkv":  (".mkv",  ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "160k"]),
    "webm": (".webm", ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus"]),
    "gif_v": (".gif", ["-vf", "fps=12,scale=480:-1:flags=lanczos", "-an"]),
    "mp3":  (".mp3",  ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]),
    "m4a":  (".m4a",  ["-vn", "-c:a", "aac", "-b:a", "192k"]),
    "wav":  (".wav",  ["-vn"]),
    "flac": (".flac", ["-vn", "-c:a", "flac"]),
    "ogg":  (".ogg",  ["-vn", "-c:a", "libvorbis", "-q:a", "5"]),
}


class ConvertError(Exception):
    pass


# ---------------------------------------------------------------- ابزارهای کمکی
def unique_path(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        return path
    n = 1
    while True:
        cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not cand.exists():
            return cand
        n += 1


def out_dir_for(src: Path, out_dir: Path | None) -> Path:
    d = Path(out_dir) if out_dir else src.parent
    d.mkdir(parents=True, exist_ok=True)
    return d


def _no_window():
    return 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW


def find_ffmpeg() -> str | None:
    local = app_dir() / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if local.exists():
        return str(local)
    return shutil.which("ffmpeg")


def find_soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("soffice.exe")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            p = Path(base) / "LibreOffice" / "program" / "soffice.exe"
            if p.exists():
                return str(p)
    return None


def _run(cmd, timeout=None):
    return subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL, creationflags=_no_window(), timeout=timeout,
    )


def _pymupdf():
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            raise ConvertError("کتابخانهٔ PyMuPDF نصب نیست.")
    return fitz


def _open_pdf(path: Path):
    """باز کردن PDF از روی بایت‌ها تا مسیر یونیکد مشکلی ایجاد نکند."""
    fitz = _pymupdf()
    doc = fitz.open(stream=Path(path).read_bytes(), filetype="pdf")
    if doc.needs_pass:
        raise ConvertError("فایل PDF رمزدار است.")
    return doc


# ---------------------------------------------------------------- تصویر
def _open_image(path: Path):
    from PIL import Image
    return Image.open(io.BytesIO(Path(path).read_bytes()))


def convert_image(src: Path, key: str, out_dir, quality: int = 90) -> list[Path]:
    from PIL import Image
    ext = {"jpg": ".jpg", "png": ".png", "webp": ".webp", "bmp": ".bmp",
           "tiff": ".tiff", "gif": ".gif", "ico": ".ico", "img2pdf": ".pdf"}[key]
    dst = unique_path(out_dir_for(src, out_dir) / (src.stem + ext))
    im = _open_image(src)
    animated = getattr(im, "is_animated", False)

    if key in ("gif", "webp") and animated:
        frames = []
        from PIL import ImageSequence
        for fr in ImageSequence.Iterator(im):
            frames.append(fr.convert("RGBA"))
        dur = im.info.get("duration", 80)
        frames[0].save(dst, save_all=True, append_images=frames[1:], loop=0,
                       duration=dur, quality=quality)
        return [dst]

    if key in ("jpg", "bmp", "img2pdf"):
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")

    if key == "jpg":
        im.save(dst, "JPEG", quality=quality, optimize=True)
    elif key == "webp":
        im.save(dst, "WEBP", quality=quality)
    elif key == "png":
        im.save(dst, "PNG", optimize=True)
    elif key == "ico":
        side = min(256, max(im.size))
        sizes = [(s, s) for s in (16, 32, 48, 64, 128, 256) if s <= side] or [(16, 16)]
        im.convert("RGBA").save(dst, "ICO", sizes=sizes)
    elif key == "img2pdf":
        im.save(dst, "PDF", resolution=150.0)
    else:
        im.save(dst)
    return [dst]


# ---------------------------------------------------------------- PDF
def merge_to_pdf(files: list[Path], out_dir) -> list[Path]:
    fitz = _pymupdf()
    from PIL import Image
    out = fitz.open()
    for f in files:
        cat = category(f)
        if cat == "pdf":
            out.insert_pdf(_open_pdf(f))
        elif cat == "image":
            im = _open_image(f).convert("RGB")
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=95)
            img_doc = fitz.open(stream=buf.getvalue(), filetype="jpeg")
            out.insert_pdf(fitz.open("pdf", img_doc.convert_to_pdf()))
    if out.page_count == 0:
        raise ConvertError("هیچ صفحه‌ای برای ادغام وجود ندارد.")
    first = Path(files[0])
    dst = unique_path(out_dir_for(first, out_dir) / "ادغام‌شده.pdf")
    dst.write_bytes(out.tobytes(garbage=3, deflate=True))
    return [dst]


def pdf_to_images(src: Path, key: str, out_dir, dpi: int = 150) -> list[Path]:
    doc = _open_pdf(src)
    fmt, ext = ("png", ".png") if key == "pdf2png" else ("jpg", ".jpg")
    folder = out_dir_for(src, out_dir) / f"{src.stem}_تصاویر"
    folder = Path(unique_path(folder))
    folder.mkdir(parents=True)
    results = []
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=dpi)
        data = pix.tobytes(fmt)
        p = folder / f"صفحه-{i:03d}{ext}"
        p.write_bytes(data)
        results.append(p)
    return [folder]


def pdf_to_text(src: Path, out_dir) -> list[Path]:
    doc = _open_pdf(src)
    text = "\n\n".join(page.get_text() for page in doc)
    dst = unique_path(out_dir_for(src, out_dir) / (src.stem + ".txt"))
    dst.write_text(text, encoding="utf-8")
    return [dst]


def split_pdf(src: Path, out_dir) -> list[Path]:
    fitz = _pymupdf()
    doc = _open_pdf(src)
    folder = unique_path(out_dir_for(src, out_dir) / f"{src.stem}_صفحات")
    folder.mkdir(parents=True)
    for i in range(doc.page_count):
        part = fitz.open()
        part.insert_pdf(doc, from_page=i, to_page=i)
        (folder / f"صفحه-{i + 1:03d}.pdf").write_bytes(part.tobytes(deflate=True))
    return [folder]


# ---------------------------------------------------------------- ffmpeg
def convert_media(src: Path, key: str, out_dir, cancel=lambda: False) -> list[Path]:
    ff = find_ffmpeg()
    if not ff:
        raise ConvertError("ffmpeg پیدا نشد. فایل ffmpeg.exe را در پوشهٔ bin کنار برنامه قرار دهید.")
    ext, args = FFMPEG_ARGS[key]
    dst = unique_path(out_dir_for(src, out_dir) / (src.stem + ext))
    with tempfile.TemporaryDirectory(prefix="fadak_") as tmp:
        tmp_in = Path(tmp) / ("in" + src.suffix.lower())
        tmp_out = Path(tmp) / ("out" + ext)
        shutil.copyfile(src, tmp_in)  # نام انگلیسی برای موتور بیرونی
        cmd = [ff, "-nostdin", "-y", "-i", str(tmp_in), *args, str(tmp_out)]
        r = _run(cmd)
        if r.returncode != 0 or not tmp_out.exists():
            msg = r.stderr.decode("utf-8", "ignore").strip().splitlines()
            if "-vn" in args and category(src) == "video":
                raise ConvertError("این ویدیو ردیف صوتی ندارد یا قابل تبدیل نیست.")
            raise ConvertError("خطای ffmpeg: " + (msg[-1] if msg else "نامشخص"))
        shutil.move(str(tmp_out), str(dst))
    return [dst]


# ---------------------------------------------------------------- آفیس → PDF
def convert_office(src: Path, out_dir) -> list[Path]:
    so = find_soffice()
    if not so:
        raise ConvertError("برای تبدیل اسناد آفیس به PDF، برنامهٔ LibreOffice باید نصب باشد.")
    dst = unique_path(out_dir_for(src, out_dir) / (src.stem + ".pdf"))
    with tempfile.TemporaryDirectory(prefix="fadak_") as tmp:
        tmp_in = Path(tmp) / ("in" + src.suffix.lower())
        outd = Path(tmp) / "out"
        outd.mkdir()
        profile = Path(tmp) / "profile"
        shutil.copyfile(src, tmp_in)
        cmd = [so, f"-env:UserInstallation={profile.as_uri()}", "--headless",
               "--convert-to", "pdf", "--outdir", str(outd), str(tmp_in)]
        r = _run(cmd, timeout=300)
        produced = outd / "in.pdf"
        if not produced.exists():
            raise ConvertError("LibreOffice نتوانست فایل را تبدیل کند.")
        shutil.move(str(produced), str(dst))
    return [dst]


# ---------------------------------------------------------------- نقطهٔ ورود
def convert_one(src, key: str, out_dir=None, quality: int = 90, cancel=lambda: False) -> list[Path]:
    src = Path(src)
    cat = category(src)
    t = TARGET_BY_KEY[key]
    if cat not in t[2]:
        raise ConvertError("این تبدیل برای نوع این فایل پشتیبانی نمی‌شود.")
    if cat == "image" and key in ("png", "jpg", "webp", "bmp", "tiff", "gif", "ico", "img2pdf"):
        return convert_image(src, key, out_dir, quality)
    if key in ("pdf2png", "pdf2jpg"):
        return pdf_to_images(src, key, out_dir)
    if key == "pdf2txt":
        return pdf_to_text(src, out_dir)
    if key == "split":
        return split_pdf(src, out_dir)
    if key == "office2pdf":
        return convert_office(src, out_dir)
    if key in FFMPEG_ARGS:
        return convert_media(src, key, out_dir, cancel)
    raise ConvertError("تبدیل ناشناخته.")
