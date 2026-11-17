"""Avvio: python -m promovo [--host 0.0.0.0] [--port 8000]"""
from __future__ import annotations

import argparse
import logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Avvia la piattaforma Promovo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--demo", action="store_true", help="crea un account e un negozio di prova")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import uvicorn

    from .api import create_app
    from .config import get_settings
    from .db import Database

    settings = get_settings()
    db = Database(settings.database_url)
    db.create_all()
    if args.demo:
        from .demo import DEMO_EMAIL, DEMO_PASSWORD, seed_demo
        seed_demo(db, settings)
        logging.getLogger("promovo").info("Accesso demo: %s / %s", DEMO_EMAIL, DEMO_PASSWORD)
    uvicorn.run(create_app(settings, db=db), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
