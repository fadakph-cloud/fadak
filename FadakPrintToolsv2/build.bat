@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ===== 1/4: ساخت محیط پایتون =====
if not exist venv (
    python -m venv venv || (echo پایتون نصب نیست. از python.org نصب کنید و گزینه Add to PATH را بزنید. & pause & exit /b 1)
)
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt || (pause & exit /b 1)

echo ===== 2/4: ساخت برنامه =====
pyinstaller --noconfirm --clean --windowed --name FadakPrintTools --icon assets\icon.ico main.py || (pause & exit /b 1)

echo ===== 3/4: کپی فایل‌های جانبی =====
xcopy /E /I /Y assets dist\FadakPrintTools\assets >nul
if exist bin   xcopy /E /I /Y bin   dist\FadakPrintTools\bin   >nul
if exist fonts xcopy /E /I /Y fonts dist\FadakPrintTools\fonts >nul

echo ===== 4/4: ساخت فایل نصبی =====
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% installer.iss
    echo.
    echo فایل نصبی: installer_output\FadakPrintTools-Setup.exe
) else (
    echo Inno Setup نصب نیست؛ فقط نسخه پرتابل ساخته شد در: dist\FadakPrintTools
    echo برای فایل نصبی، Inno Setup را از jrsoftware.org نصب و دوباره build.bat را اجرا کنید.
)
pause
