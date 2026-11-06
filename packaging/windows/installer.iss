; Inno Setup script: builds "FileConverter-Setup-<version>.exe" from the PyInstaller output.
; Usage (from repo root): iscc /DAppVersion=0.1.0 packaging\windows\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B0E2B7C-3C1E-4C8F-9F3B-5A2D7E1F4C21}
AppName=File Converter
AppVersion={#AppVersion}
AppPublisher=SpOok548
AppPublisherURL=https://github.com/SpOok548/file-converter
DefaultDirName={autopf}\File Converter
DefaultGroupName=File Converter
DisableProgramGroupPage=yes
; Lets people without admin rights install just for themselves.
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\dist
OutputBaseFilename=FileConverter-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\File Converter.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\..\dist\File Converter\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\File Converter"; Filename: "{app}\File Converter.exe"
Name: "{group}\Uninstall File Converter"; Filename: "{uninstallexe}"
Name: "{autodesktop}\File Converter"; Filename: "{app}\File Converter.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\File Converter.exe"; Description: "Open File Converter now"; Flags: nowait postinstall skipifsilent
