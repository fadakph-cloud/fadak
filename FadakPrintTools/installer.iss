; اسکریپت ساخت فایل نصبی — Inno Setup 6
; برای ویزارد فارسی، فایل Farsi.isl را کنار همین فایل بگذارید (اختیاری).
#define AppName "ابزار چاپ فدک"
#define AppVer  "1.0.0"

[Setup]
AppId={{B7C3A1E2-5F4D-4E8A-9A31-FADAK0001}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=چاپ و تبلیغات فدک
AppPublisherURL=https://eitaa.com/fadakph
DefaultDirName={autopf}\FadakPrintTools
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\FadakPrintTools.exe
SetupIconFile=assets\icon.ico
OutputDir=installer_output
OutputBaseFilename=FadakPrintTools-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Languages]
#ifexist "Farsi.isl"
Name: "fa"; MessagesFile: "Farsi.isl"
#else
Name: "en"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "ساخت میان‌بر روی دسکتاپ"; GroupDescription: "میان‌بر:"

[Files]
Source: "dist\FadakPrintTools\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\FadakPrintTools.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\FadakPrintTools.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FadakPrintTools.exe"; Description: "اجرای {#AppName}"; Flags: nowait postinstall skipifsilent
