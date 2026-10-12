; Windows installer (Inno Setup 6). Built by packaging/build.py after PyInstaller:
;   iscc /DAppVersion=2.0.0 packaging\innopetrol.iss
; Installs per user by default (no administrator rights needed), adds Start menu and optional
; desktop shortcuts, and opens .ipproj projects with InnoPetrol.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1F4E2A-8B3D-4F59-9A7E-2D51C3B8E0A4}
AppName=InnoPetrol
AppVersion={#AppVersion}
AppPublisher=InnoPetrol
AppPublisherURL=https://github.com/portocent/innopetrol-dektop
DefaultDirName={autopf}\InnoPetrol
DefaultGroupName=InnoPetrol
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\COPYING.LESSER
OutputDir=..\dist
OutputBaseFilename=InnoPetrol-{#AppVersion}-windows-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
UninstallDisplayIcon={app}\InnoPetrol.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\InnoPetrol\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\InnoPetrol"; Filename: "{app}\InnoPetrol.exe"
Name: "{autodesktop}\InnoPetrol"; Filename: "{app}\InnoPetrol.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.ipproj"; ValueType: string; ValueName: ""; ValueData: "InnoPetrol.Project"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\InnoPetrol.Project"; ValueType: string; ValueName: ""; ValueData: "InnoPetrol project"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\InnoPetrol.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\InnoPetrol.exe,0"
Root: HKA; Subkey: "Software\Classes\InnoPetrol.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\InnoPetrol.exe"" ""%1"""

[Run]
Filename: "{app}\InnoPetrol.exe"; Description: "{cm:LaunchProgram,InnoPetrol}"; Flags: nowait postinstall skipifsilent
