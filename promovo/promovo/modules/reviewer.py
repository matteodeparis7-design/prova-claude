"""Revisore finale: ricontrolla da solo i materiali della settimana prima della consegna.

Non rifà niente e non cambia niente: guarda il lavoro degli altri agenti come farebbe un capo redattore e
dice cosa va bene e cosa no, in parole semplici.

- Grafiche: il file c'è, ha la misura giusta, non è vuoto.
- Tutti i materiali: sono stati fatti con i prezzi di adesso? Se un prezzo è stato corretto dopo, lo dice.
- Video: il file c'è, la durata e la risoluzione sono quelle del formato, l'audio c'è se è prevista la musica.
- Testi: prezzi citati che esistono davvero, lunghezze adatte a Instagram e Facebook, hashtag non troppi,
  niente segni strani rimasti (graffe, «None», spazi doppi).
- Offerte: prezzi ancora da controllare, prezzi barrati da rivedere (agente Omnibus).
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ContentPiece, Flyer, Store
from .catalog import price_snapshot
from ..money import find_prices, format_eur

SIZES = {"cover": (1080, 1350), "story": (1080, 1920), "offer": (1080, 1080), "idea": (1080, 1350)}
VIDEO_SIZES = {"portrait": (1080, 1920), "square": (1080, 1080), "landscape": (1920, 1080), "clip": (1080, 1920)}
IG_LIMIT, IG_TAGS = 2200, 30


@dataclass
class Check:
    area: str            # "grafiche" | "video" | "testi" | "offerte"
    item: str
    status: str          # "ok" | "warn" | "err"
    message: str

    def as_dict(self) -> dict:
        return {"area": self.area, "item": self.item, "status": self.status, "message": self.message}


def _image_checks(p: ContentPiece) -> list[Check]:
    meta = p.meta or {}
    fmt = meta.get("format", "")
    path = Path(p.file_path or "")
    if not path.exists() or path.stat().st_size < 2000:
        return [Check("grafiche", p.title, "err", "Il file della grafica manca o è vuoto: rifai le immagini.")]
    out = []
    with Image.open(path) as im:
        size = im.size
        small = np.asarray(im.convert("L").resize((96, 96)), dtype=np.float32)
    want = SIZES.get(fmt)
    if want and size != want:
        out.append(Check("grafiche", p.title, "warn", f"Misura {size[0]}×{size[1]} invece di {want[0]}×{want[1]}."))
    if float(small.std()) < 6:
        out.append(Check("grafiche", p.title, "err", "La grafica sembra vuota o di un solo colore."))
    if not out:
        out.append(Check("grafiche", p.title, "ok", "File, misura e contenuto a posto."))
    return out


def _ffmpeg_info(path: Path) -> tuple[float, tuple[int, int] | None, bool]:
    from .video.render import ffmpeg_path, probe_duration
    info = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Video:.*?(\d{3,4})x(\d{3,4})", info)
    return probe_duration(path), ((int(m.group(1)), int(m.group(2))) if m else None), "Audio:" in info


def _video_checks(p: ContentPiece) -> list[Check]:
    meta = p.meta or {}
    path = Path(p.file_path or "")
    if not path.exists() or path.stat().st_size < 20000:
        return [Check("video", p.title, "err", "Il file del video manca o è vuoto: rifallo.")]
    dur, size, audio = _ffmpeg_info(path)
    out = []
    want = VIDEO_SIZES.get(meta.get("format", ""))
    if want and size and size != want:
        out.append(Check("video", p.title, "warn", f"Risoluzione {size[0]}×{size[1]} invece di {want[0]}×{want[1]}."))
    if dur < 4:
        out.append(Check("video", p.title, "err", f"Il video dura solo {dur:.1f} secondi."))
    elif meta.get("format") in ("portrait", "clip") and dur > 90:
        out.append(Check("video", p.title, "warn", f"Dura {dur:.0f} secondi: per i Reel meglio stare sotto il minuto e mezzo."))
    if meta.get("music") and not audio:
        out.append(Check("video", p.title, "warn", "Doveva avere la musica ma non c'è audio."))
    if not out:
        out.append(Check("video", p.title, "ok", f"{dur:.0f} secondi, {size[0]}×{size[1] if size else 0}, "
                                                 f"{'con audio' if audio else 'senza audio'}." if size else f"{dur:.0f} secondi."))
    return out


_JUNK = re.compile(r"\{|\}|\bNone\b|\bnan\b|\bnull\b|\s{3,}|\.\.\.\.|,,")


def _text_checks(p: ContentPiece, allowed: set[int]) -> list[Check]:
    body = p.body or ""
    label = {"instagram": "Post Instagram", "facebook": "Post Facebook", "reel": "Didascalia Reel e TikTok",
             "plan": "Piano della settimana"}.get(p.kind, p.title)
    out = []
    if not body.strip():
        return [Check("testi", label, "err", "Il testo è vuoto.")]
    if _JUNK.search(body.replace("\n\n", "\n")):
        out.append(Check("testi", label, "warn", "Nel testo sono rimasti segni strani: rileggilo."))
    if p.kind in ("instagram", "reel"):
        tags = re.findall(r"#\w+", body + " " + " ".join((p.meta or {}).get("hashtags", [])))
        if len(body) > IG_LIMIT:
            out.append(Check("testi", label, "err", f"{len(body)} caratteri: Instagram ne accetta {IG_LIMIT}."))
        if len(set(tags)) > IG_TAGS:
            out.append(Check("testi", label, "warn", f"{len(set(tags))} hashtag: Instagram ne accetta al massimo {IG_TAGS}."))
    if p.kind != "plan":
        from .till import strip as till_strip      # il premio della Parola alla cassa non è un prezzo del volantino
        wrong = [c for c in find_prices(till_strip(body)) if c not in allowed]
        if wrong:
            out.append(Check("testi", label, "err",
                             "Prezzi che non sono nel volantino: " + ", ".join(format_eur(c) for c in wrong[:3]) + "."))
    if not out:
        out.append(Check("testi", label, "ok", "Prezzi veri, lunghezza giusta, nessun segno strano."))
    return out


def allowed_prices(store: Store, flyer: Flyer) -> set[int]:
    from .content.writer import computed_prices, gather_facts
    try:
        return computed_prices(gather_facts(store, flyer, list(flyer.offers)))
    except Exception:
        out = set()
        for o in flyer.offers:
            out.add(o.price_cents)
            if o.old_price_cents:
                out.update((o.old_price_cents, o.old_price_cents - o.price_cents))
        return out


def review(session: Session, store: Store, flyer: Flyer) -> dict:
    pieces = session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id)
                             .order_by(ContentPiece.id)).all()
    allowed = allowed_prices(store, flyer)
    checks: list[Check] = []
    unverified = [o for o in flyer.offers if not o.price_verified]
    checks.append(Check("offerte", "Prezzi", "warn" if unverified else "ok",
                        ("1 prezzo ancora da controllare" if len(unverified) == 1 else f"{len(unverified)} prezzi ancora da controllare")
                        + " nel passo 1." if unverified
                        else f"Tutti i {len(flyer.offers)} prezzi confermati."))
    from .omnibus import check as omni_check
    om = omni_check(session, store, flyer)
    if om:
        checks.append(Check("offerte", "Prezzi barrati (Omnibus)", "warn",
                            ("1 prezzo barrato più alto" if len(om) == 1 else f"{len(om)} prezzi barrati più alti")
                            + " del minimo dei 30 giorni prima: rivedili nel passo 1."))
    from .soldout import stale_pieces
    gone = {x["piece_id"]: x for x in stale_pieces(session, flyer)}
    now = price_snapshot(flyer)
    names = {str(o.id): o.name for o in flyer.offers}
    for p in pieces:
        if p.id in gone:
            area = {"image": "grafiche", "video": "video"}.get(p.kind, "testi")
            names = gone[p.id]["offers"]
            checks.append(Check(area, p.title or p.kind, "err",
                                f"Mostra «{names[0]}»" + (f" e altri {len(names) - 1} prodotti" if len(names) > 1 else "")
                                + ", segnato esaurito: premi «Rifai i materiali»."))
            continue
        was = (p.meta or {}).get("prices_at")
        if was:
            changed = [k for k, v in now.items() if k in was and list(was[k]) != list(v)]
            if changed:
                area = {"image": "grafiche", "video": "video"}.get(p.kind, "testi")
                checks.append(Check(area, p.title or p.kind, "err",
                                    f"Fatto prima che cambiassi il prezzo di «{names[changed[0]]}»"
                                    + (f" e di altre {len(changed) - 1} offerte" if len(changed) > 1 else "")
                                    + ": premi «Rifai i materiali»."))
                continue
        if p.kind == "image":
            checks += _image_checks(p)
        elif p.kind == "video":
            checks += _video_checks(p)
        elif p.kind in ("instagram", "facebook", "reel", "plan"):
            checks += _text_checks(p, allowed)
    counts = {k: sum(1 for c in checks if c.status == k) for k in ("ok", "warn", "err")}
    verdict = "da sistemare" if counts["err"] else "da guardare" if counts["warn"] else "pronto da consegnare"
    return {"verdict": verdict, "counts": counts, "materials": len(pieces),
            "checks": [c.as_dict() for c in checks]}
