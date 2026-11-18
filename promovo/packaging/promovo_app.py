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


def main() -> None:
    base = base_dir()
    env = prepare_environment(base)
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
    from promovo.__main__ import main as run
    sys.argv = [sys.argv[0], "--demo", "--open", *sys.argv[1:]]
    run()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        print("\n  Si e' verificato un errore. Fai una foto di questa finestra e mandala in chat.")
        try:
            input("  Premi Invio per chiudere...")
        except Exception:
            pass
        sys.exit(1)
