; Installazione di Promovo per Windows (Inno Setup). Si compila dalla cartella "promovo":
;   ISCC packaging\promovo.iss
; Installa per il solo utente (non servono permessi di amministratore), crea le icone e,
; alla fine, avvia Promovo. I dati restano nella cartella "Dati Promovo" anche se si disinstalla.

#define AppName "Promovo"
#define AppVersion "0.3 beta"

[Setup]
AppId=PromovoBeta
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Promovo
DefaultDirName={localappdata}\Programs\Promovo
DefaultGroupName=Promovo
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Promovo_Setup
SetupIconFile=promovo.ico
UninstallDisplayIcon={app}\Promovo.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "italiano"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul Desktop"; GroupDescription: "Icone:"

[Files]
Source: "..\dist\Promovo\*"; DestDir: "{app}"; Excludes: "Dati Promovo\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LEGGIMI.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "Avvia Promovo (se si chiude subito).bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\GUIDA.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Promovo"; Filename: "{app}\Promovo.exe"; WorkingDir: "{app}"
Name: "{group}\Guida di Promovo"; Filename: "{app}\LEGGIMI.txt"
Name: "{group}\Promovo (con messaggi di errore)"; Filename: "{app}\Avvia Promovo (se si chiude subito).bat"; WorkingDir: "{app}"
Name: "{group}\Disinstalla Promovo"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Promovo"; Filename: "{app}\Promovo.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Promovo.exe"; Description: "Avvia Promovo adesso"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
