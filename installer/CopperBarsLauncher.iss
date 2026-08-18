#define MyAppName "CopperBars Launcher"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "pmdgaming5-code"
#define MyAppURL "https://github.com/pmdgaming5-code/CopperBarsLauncher"
#define MyAppExeName "CopperBarsLauncher.exe"

[Setup]
AppId={{9A0C9FA7-8C79-4F52-A31E-1E4C3C7D0B1C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\CopperBarsLauncher
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=CopperBarsLauncher-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName={#MyAppName}
PrivilegesRequired=admin

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Files]
Source: "..\dist\CopperBarsLauncher.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CopperBars Launcher"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\CopperBars Launcher"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "CopperBars Launcher'ı başlat"; Flags: nowait postinstall skipifsilent
