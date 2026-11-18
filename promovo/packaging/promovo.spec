# Ricetta di PyInstaller per costruire il programma Promovo (cartella con Promovo.exe).
# Uso, dalla cartella "promovo":  pyinstaller packaging/promovo.spec --noconfirm
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
datas += collect_data_files("promovo")              # caratteri, pagina web
datas += collect_data_files("imageio_ffmpeg")       # ffmpeg incluso (video, musica, stabilizzazione)
datas += collect_data_files("tzdata")               # fusi orari (Windows non li ha)
datas += collect_data_files("certifi")              # certificati per le connessioni sicure
datas += collect_data_files("segno")
datas += collect_data_files("rapidocr")             # lettura ottica: configurazione e modelli (scaricati prima)

hidden = []
hidden += collect_submodules("promovo")             # alcuni moduli si caricano solo quando servono
hidden += collect_submodules("uvicorn")
hidden += collect_submodules("rapidocr")
hidden += ["email_validator", "multipart", "python_multipart"]

a = Analysis(
    ["promovo_app.py"],
    pathex=[".."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Promovo",
    icon="promovo.ico",
    console=True,                 # la finestra nera: chiuderla spegne Promovo
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Promovo")
