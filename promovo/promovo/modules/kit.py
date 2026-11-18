"""Il "pacchetto della settimana": tutti i materiali di un volantino creati in un colpo solo,
e lo ZIP da scaricare con video, immagini e testi pronti da pubblicare."""
from __future__ import annotations

import re
import zipfile
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..llm import LLM
from ..models import ContentPiece, Flyer, Store
from ..money import format_eur
from .content.service import generate_content, save_content, validity_text
from .graphics.service import render_flyer_images
from .video.service import render_flyer_video

ITEMS = {
    "texts": "Testi per i social",
    "images": "Immagini per i post",
    "video_portrait": "Reel 9:16",
    "video_square": "Video post 1:1",
    "video_landscape": "Video per lo schermo 16:9",
}
DEFAULT_ITEMS = ["texts", "images", "video_portrait", "video_landscape"]


def run_kit(session: Session, store: Store, flyer: Flyer, settings: Settings, llm: LLM | None,
            items: list[str], progress: Callable[[str, int, int], None] | None = None) -> dict:
    """Crea i materiali richiesti, uno dopo l'altro. Un errore su uno non ferma gli altri."""
    todo = [i for i in ITEMS if i in items]
    done, errors, warnings = [], [], []
    for n, item in enumerate(todo):
        if progress:
            progress(item, n, len(todo))
        try:
            if item == "texts":
                from .weather.service import weekly_weather
                weather = weekly_weather(store, flyer, enabled=settings.weather)
                pack = generate_content(store, flyer, llm, weather=weather)
                save_content(session, store, flyer, pack)
                warnings.extend(pack.warnings)
            elif item == "images":
                render_flyer_images(session, store, flyer, settings)
            elif item.startswith("video_"):
                render_flyer_video(session, store, flyer, settings, item.split("_", 1)[1])
            session.commit()
            done.append(item)
        except Exception as exc:          # si annota e si prosegue con il resto
            session.rollback()
            errors.append(f"{ITEMS[item]}: {exc}")
    if progress:
        progress("", len(todo), len(todo))
    return {"done": done, "errors": errors, "warnings": warnings}


def _safe(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")
    return s[:60] or "file"


TEXT_FILES = {"instagram": "Instagram.txt", "facebook": "Facebook.txt", "plan": "Piano_della_settimana.txt"}


def build_zip(session: Session, store: Store, flyer: Flyer, out_path: Path, approved_only: bool = False) -> Path:
    pieces = session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id)
                             .order_by(ContentPiece.id)).all()
    if approved_only:
        pieces = [p for p in pieces if p.approved or p.kind == "plan"]   # il piano non si approva
    root = _safe(f"{store.name}_{flyer.valid_from or flyer.id}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        summary = [f"{store.name} - materiali del volantino",
                   f"Validità: {validity_text(flyer) or 'non indicata'}", "",
                   "Offerte:"]
        for o in flyer.offers:
            line = f"- {o.brand + ' ' if o.brand else ''}{o.name} {o.description}".rstrip()
            line += f": {format_eur(o.price_cents)}"
            if o.old_price_cents:
                line += f" (invece di {format_eur(o.old_price_cents)})"
            summary.append(line)
        summary += ["", "Contenuto della cartella:", "- Video: pronti per Instagram, TikTok, Facebook e schermi in negozio",
                    "- Immagini: post e storie", "- Testi: da copiare insieme alle immagini o ai video",
                    "- Piano_della_settimana.txt: cosa pubblicare, dove e in che giorno",
                    "", "Ricorda: pubblica solo i contenuti che hai controllato."]
        z.writestr(f"{root}/LEGGIMI.txt", "\n".join(summary))
        for p in pieces:
            if p.kind in TEXT_FILES:
                body = p.body
                tags = (p.meta or {}).get("hashtags") or []
                if tags:
                    body += "\n\n" + " ".join("#" + t for t in tags)
                name = TEXT_FILES[p.kind]
                z.writestr(f"{root}/{name}" if p.kind == "plan" else f"{root}/Testi/{name}", body)
            elif p.file_path and Path(p.file_path).exists():
                folder = "Video" if p.kind == "video" else "Immagini"
                ext = Path(p.file_path).suffix
                z.write(p.file_path, f"{root}/{folder}/{_safe(p.title)}{ext}")
    return out_path
