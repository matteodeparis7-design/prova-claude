"""Avvio: python -m promovo [--host 0.0.0.0] [--port 8000] [--demo] [--open]"""
from __future__ import annotations

import argparse
import os
import logging
import socket
import threading
import time
import webbrowser


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


def pick_port(host: str, wanted: int) -> int:
    """La porta richiesta, oppure la prima libera subito dopo (se un altro programma la sta usando)."""
    for port in range(wanted, wanted + 20):
        if port_free(host, port):
            return port
    raise SystemExit(f"Nessuna porta libera tra {wanted} e {wanted + 19}: chiudi altri programmi e riprova.")


def say(text: str) -> None:
    """Stampa senza mai fallire, anche su console con codifiche limitate."""
    try:
        print(text, flush=True)
    except Exception:
        pass


def open_when_ready(url: str, host: str, port: int, timeout: float = 300) -> None:
    """Apre il browser solo quando Promovo risponde davvero."""
    def wait():
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=1):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            say("\n  Promovo non si e' avviato in tempo: guarda i messaggi qui sopra.\n")
            return
        say(f"\n  >>> PROMOVO E' PRONTO: {url}\n"
            "      Se il browser non si apre da solo, copia questo indirizzo nel browser.\n"
            "      Per spegnere Promovo chiudi questa finestra.\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=wait, daemon=True).start()


def main() -> None:
    for name in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"):
        key = os.environ.get(name)
        if key is not None:   # una chiave incollata da file può portarsi dietro spazi o a capo
            os.environ[name] = key.strip()
    parser = argparse.ArgumentParser(description="Avvia la piattaforma Promovo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--demo", action="store_true", help="crea un account e un negozio di prova")
    parser.add_argument("--open", action="store_true",
                        help="apre il browser quando è pronto e, se la porta è occupata, ne usa un'altra")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import uvicorn

    from .api import create_app
    from .config import get_settings
    from .db import Database

    port = pick_port(args.host, args.port) if args.open else args.port
    settings = get_settings()
    db = Database(settings.database_url)
    db.create_all()
    if args.demo:
        from .demo import DEMO_EMAIL, DEMO_PASSWORD, seed_demo
        seed_demo(db, settings)
        logging.getLogger("promovo").info("Accesso demo: %s / %s", DEMO_EMAIL, DEMO_PASSWORD)
    if args.open:
        open_when_ready(f"http://127.0.0.1:{port}", "127.0.0.1", port)
    uvicorn.run(create_app(settings, db=db), host=args.host, port=port)


if __name__ == "__main__":
    main()
