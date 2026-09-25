; Inno Setup Script for Tech 2000 Inventory Price Updater
#define MyAppName "Tech 2000 Inventory Price Updater"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Tech 2000"
#define MyAppExeName "Tech2000-InventoryUpdater.exe"

[Setup]
AppId={{D37F2C5A-5D8A-454E-9F7C-9037A2F08821}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Tech 2000\Inventory Price Updater
DefaultGroupName={#MyAppPublisher}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Tech2000-InventoryUpdater-Windows-x64-Setup
SetupIconFile=icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Tech2000-InventoryUpdater\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
