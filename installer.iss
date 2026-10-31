; JARVIS — Inno Setup kurucu betiği (Windows tek .exe kurucu)
; Derleme: ISCC installer.iss   (Inno Setup kurulu olmalı: jrsoftware.org)
; Ön koşul: pyinstaller jarvis.spec ile dist\JARVIS\ hazır olmalı.
; NOT: .env (API anahtarları) KASTEN dahil edilmez — kullanıcı EXE yanına koyar.

#define MyAppName "JARVIS"
#define MyAppVersion "11.0.0"
#define MyAppPublisher "JARVIS Project"
#define MyAppExeName "JARVIS.exe"

[Setup]
AppId={{7A3E1B52-6C41-4D9A-9E5F-2B8C0D1A6F41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=JARVIS-Setup-{#MyAppVersion}
SetupIconFile=JARVIS.ico
WizardImageFile=installer_wizard.bmp
WizardSmallImageFile=installer_small.bmp
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; kullanıcı düzeyinde kurulum (admin gerekmez)
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek görevler:"

[Files]
Source: "dist\JARVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; .env bilerek KURULMAZ — bkz. BUILD.md (anahtar sızıntısını önlemek için)

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent
