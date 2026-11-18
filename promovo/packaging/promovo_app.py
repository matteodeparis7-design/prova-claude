"""Avvio di Promovo come programma (Promovo.exe): doppio clic e si apre il browser.

- I dati (negozi, volantini, video) restano nella cartella "Dati Promovo", accanto al programma:
  si può spostare tutta la cartella o copiarla per fare un backup.
- Le chiavi facoltative si mettono accanto al programma, in file di testo:
  CHIAVE_IA.txt (intelligenza artificiale) e CHIAVE_VOCE.txt (voce generata, ElevenLabs).
- Se qualcosa va storto la finestra resta aperta con il messaggio, da fotografare.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def base_dir() -> Path:
    if getattr(sys, "frozen", False):            # programma impacchettato
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def read_key(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
    except (OSError, IndexError, UnicodeDecodeError):
        return ""


def prepare_environment(base: Path) -> dict[str, str]:
    data = base / "Dati Promovo"
    data.mkdir(parents=True, exist_ok=True)
    env = {
        "PROMOVO_DATA_DIR": str(data),
        "PROMOVO_DATABASE_URL": "sqlite:///" + (data / "promovo.db").as_posix(),
    }
    ai = os.environ.get("ANTHROPIC_API_KEY") or read_key(base / "CHIAVE_IA.txt")
    voice = os.environ.get("ELEVENLABS_API_KEY") or read_key(base / "CHIAVE_VOCE.txt")
    if ai:
        env["ANTHROPIC_API_KEY"] = ai
    else:
        env["PROMOVO_AI"] = "off"
    if voice:
        env["ELEVENLABS_API_KEY"] = voice
    for k, v in env.items():
        os.environ.setdefault(k, v)
    return env


def say(text: str = "") -> None:
    """Stampa senza mai fallire (console di Windows con codifiche limitate)."""
    try:
        print(text, flush=True)
    except Exception:
        try:
            print(text.encode("ascii", "replace").decode("ascii"), flush=True)
        except Exception:
            pass


def pause(message: str) -> None:
    """Tiene aperta la finestra: senza, un errore la farebbe sparire prima di poterlo leggere."""
    say("\n  " + message)
    try:
        input("  Premi Invio per chiudere questa finestra...")
    except Exception:
        try:
            import time
            time.sleep(600)
        except Exception:
            pass


def setup_log(base: Path) -> Path | None:
    """Registro su file (Dati Promovo/registro.txt) oltre che sullo schermo, per capire eventuali problemi."""
    import logging
    try:
        path = base / "Dati Promovo" / "registro.txt"
        handlers = [logging.StreamHandler(), logging.FileHandler(path, encoding="utf-8")]
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                            handlers=handlers)
        return path
    except Exception:
        return None


def main() -> None:
    base = base_dir()
    if getattr(sys, "frozen", False) and not (base / "_internal").exists():
        pause("Promovo e' stato aperto da dentro il file zip. Prima estrai la cartella "
              "(tasto destro sullo zip > Estrai tutto), poi apri Promovo.exe dalla cartella estratta.")
        sys.exit(1)
    env = prepare_environment(base)
    log = setup_log(base)
    say("\n  =============================================")
    say("   PROMOVO")
    say("  =============================================\n")
    say(f"  Dati salvati in: {env['PROMOVO_DATA_DIR']}")
    say("  Intelligenza artificiale: " + ("ACCESA" if "ANTHROPIC_API_KEY" in env
                                         else "spenta (manca il file CHIAVE_IA.txt)"))
    say("  Voce generata: " + ("disponibile" if "ELEVENLABS_API_KEY" in env
                             else "non attiva (facoltativa: file CHIAVE_VOCE.txt)"))
    say("\n  Accesso di prova:  demo@promovo.it  /  promovo2026")
    say("  NON chiudere questa finestra mentre usi Promovo. Per spegnerlo, chiudila.\n")
    if log:
        say(f"  Registro: {log}\n")
    from promovo.__main__ import main as run
    sys.argv = [sys.argv[0], "--demo", "--open", *sys.argv[1:]]
    run()
    # Se si arriva qui il server si e' fermato da solo (non chiudendo la finestra): meglio dirlo.
    pause("Promovo si e' fermato. Se non l'hai chiuso tu, fai una foto di questa finestra e mandala.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except SystemExit as exc:
        if exc.code not in (0, None):
            if isinstance(exc.code, str):
                say("\n  " + exc.code)
            pause("Promovo non e' partito. Fai una foto di questa finestra e mandala in chat.")
        raise
    except BaseException:
        try:
            traceback.print_exc()
            base = base_dir()
            (base / "Dati Promovo").mkdir(parents=True, exist_ok=True)
            with open(base / "Dati Promovo" / "errore.txt", "w", encoding="utf-8") as fh:
                traceback.print_exc(file=fh)
        except Exception:
            pass
        pause("Si e' verificato un errore. Fai una foto di questa finestra e mandala in chat.")
        sys.exit(1)
