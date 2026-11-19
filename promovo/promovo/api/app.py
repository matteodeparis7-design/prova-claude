"""API web di Promovo e cruscotto."""
from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.background import BackgroundTask as StarletteTask
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import Database
from ..llm import AIRefused, AIUnavailable, LLM
from .. import keys
from ..models import ContentPiece, Flyer, FlyerStatus, Job, JobStatus, Offer, Organization, Role, Store, User
from ..imaging import ImageError, load_logo, open_image, save_product_photo
from ..money import discount_percent, format_eur, parse_price
from ..security import hash_password, issue_token, revoke_token, verify_password
from ..text_utils import CATEGORIES
from ..modules.catalog import active_offers
from ..modules.kit import DEFAULT_ITEMS, ITEMS, build_zip, run_kit
from ..modules.content.service import generate_content, save_content
from ..modules.flyer.pdf import InvalidPDF
from ..modules.flyer.service import create_flyer, delete_flyer_files, process_flyer, replicate_flyer
from ..modules.video.render import FORMATS
from ..modules.video.service import render_flyer_video
from ..modules.clip.analyze import ClipError
from ..modules.clip.service import AUDIO_EXT, VIDEO_EXT, VOICE_MODES, ClipFailed, delete_clip_files, make_reel, script_for
from .. import voice as voicemod
from ..modules.radar.service import radar as radar_report
from ..modules.radar import nearby as nearbymod
from ..modules.weather.service import weekly_weather
from .deps import (
    AppState, bearer_token, content_for, current_user, flyer_for, get_session, job_for, offer_for,
    require_owner, state, store_for,
)

log = logging.getLogger("promovo.api")
WEB_DIR = Path(__file__).resolve().parents[1] / "web"


# ------------------------------------------------------------------ schemi di input

class RegisterIn(BaseModel):
    organization: str = Field(min_length=2, max_length=200)
    kind: str = Field(default="agency", pattern="^(agency|store)$")
    name: str = Field(default="", max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class UserIn(BaseModel):
    name: str = Field(default="", max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    role: Role = Role.staff


_HEX = r"^#[0-9A-Fa-f]{6}$"
_TONES = r"^(familiare|elegante|giovane|essenziale)$"


def _clean_hashtags(tags: list[str]) -> list[str]:
    out = []
    for t in tags:
        t = re.sub(r"[^\w]", "", t.strip().lstrip("#"), flags=re.UNICODE)[:40]
        if t and t.lower() not in [x.lower() for x in out]:
            out.append(t)
    return out


class StoreIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    banner: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=300)
    city: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=40)
    opening_hours: dict[str, str] = Field(default_factory=dict)
    brand_color: str = Field(default="#D7262E", pattern=_HEX)
    accent_color: str = Field(default="#FFD23F", pattern=_HEX)
    services: list[str] = Field(default_factory=list, max_length=20)
    pickup_enabled: bool = True
    tone: str = Field(default="familiare", pattern=_TONES)
    hashtags: list[str] = Field(default_factory=list, max_length=15)
    whatsapp: str = Field(default="", max_length=40)
    website: str = Field(default="", max_length=200)
    video_music: bool = True

    _clean_tags = field_validator("hashtags")(lambda cls, v: _clean_hashtags(v))


class KeyIn(BaseModel):
    service: str = Field(pattern="^(ai|voice)$")
    key: str = Field(max_length=400)


class CompetitorLinkIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    competitor: str = Field(min_length=2, max_length=120)


class ReplicateIn(BaseModel):
    store_ids: list[int] = Field(min_length=1, max_length=200)
    make: bool = True                  # crea subito tutti i materiali per ogni negozio


class FeatureIn(BaseModel):
    offer_ids: list[int] = Field(max_length=50)


class StorePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    banner: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    opening_hours: dict[str, str] | None = None
    brand_color: str | None = Field(default=None, pattern=_HEX)
    accent_color: str | None = Field(default=None, pattern=_HEX)
    services: list[str] | None = Field(default=None, max_length=20)
    pickup_enabled: bool | None = None
    tone: str | None = Field(default=None, pattern=_TONES)
    hashtags: list[str] | None = Field(default=None, max_length=15)
    whatsapp: str | None = Field(default=None, max_length=40)
    website: str | None = Field(default=None, max_length=200)
    video_music: bool | None = None

    _clean_tags = field_validator("hashtags")(lambda cls, v: None if v is None else _clean_hashtags(v))


class OfferPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    brand: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    category: str | None = None
    price: str | None = None
    old_price: str | None = None
    conditions: str | None = Field(default=None, max_length=300)
    is_featured: bool | None = None
    cost: str | None = None
    confirm: bool | None = None      # conferma il prezzo così com'è (controllato da una persona)

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str | None) -> str | None:
        if v is not None and v not in CATEGORIES:
            raise ValueError("Categoria non valida.")
        return v


class OfferIn(BaseModel):
    """Offerta aggiunta a mano (quando la lettura automatica ne ha saltata una)."""
    name: str = Field(min_length=1, max_length=300)
    brand: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=500)
    category: str = "altro"
    price: str
    old_price: str = ""
    conditions: str = Field(default="", max_length=300)
    is_featured: bool = False

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError("Categoria non valida.")
        return v


class KitIn(BaseModel):
    items: list[str] = Field(default_factory=lambda: list(DEFAULT_ITEMS), min_length=1, max_length=10)

    @field_validator("items")
    @classmethod
    def _items(cls, v: list[str]) -> list[str]:
        bad = [i for i in v if i not in ITEMS]
        if bad:
            raise ValueError(f"Materiali sconosciuti: {', '.join(bad)}")
        return list(dict.fromkeys(v))


class ConfirmIn(BaseModel):
    offer_ids: list[int] = Field(max_length=2000)


class ContentPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=10000)
    approved: bool | None = None
    scheduled_for: datetime | None = None


# ------------------------------------------------------------------ serializzazione

def store_out(s: Store) -> dict:
    return {"id": s.id, "name": s.name, "banner": s.banner, "address": s.address, "city": s.city,
            "phone": s.phone, "opening_hours": s.opening_hours, "brand_color": s.brand_color,
            "accent_color": s.accent_color, "services": s.services, "pickup_enabled": s.pickup_enabled,
            "tone": s.tone, "hashtags": s.hashtags or [], "whatsapp": s.whatsapp, "website": s.website,
            "video_music": s.video_music,
            "voice_ready": bool(s.voice_id and s.voice_consent_at), "voice_consent_name": s.voice_consent_name,
            "voice_consent_at": s.voice_consent_at.isoformat() if s.voice_consent_at else None,
            "voice_service": voicemod.api_key() is not None,
            "logo_url": f"/api/stores/{s.id}/logo" if s.logo_path and Path(s.logo_path).exists() else None}


def offer_out(o: Offer) -> dict:
    return {"id": o.id, "page": o.page, "position": o.position, "name": o.name, "brand": o.brand,
            "description": o.description, "category": o.category, "price_cents": o.price_cents,
            "price": format_eur(o.price_cents), "old_price_cents": o.old_price_cents,
            "old_price": format_eur(o.old_price_cents), "discount_percent": o.discount_percent,
            "unit_price_text": o.unit_price_text, "conditions": o.conditions, "bbox": o.bbox,
            "price_verified": o.price_verified, "verified_by": o.verified_by, "is_featured": o.is_featured, "cost_cents": o.cost_cents,
            "image_url": f"/api/offers/{o.id}/image" if o.crop_path else None,
            "photo_url": f"/api/offers/{o.id}/photo" if o.photo_path else None, "manual": o.manual}


def flyer_out(f: Flyer, with_offers: bool = False) -> dict:
    out = {"id": f.id, "store_id": f.store_id, "title": f.title, "page_count": f.page_count,
           "valid_from": f.valid_from.isoformat() if f.valid_from else None,
           "valid_to": f.valid_to.isoformat() if f.valid_to else None, "status": f.status.value,
           "extraction_method": f.extraction_method, "error": f.error, "warnings": f.warnings,
           "competitor": f.competitor, "offer_count": len(f.offers), "unverified_count": sum(1 for o in f.offers if not o.price_verified),
           "created_at": f.created_at.isoformat()}
    if with_offers:
        out["offers"] = [offer_out(o) for o in f.offers]
    return out


def content_out(c: ContentPiece) -> dict:
    return {"id": c.id, "store_id": c.store_id, "flyer_id": c.flyer_id, "kind": c.kind, "title": c.title,
            "body": c.body, "approved": c.approved, "meta": c.meta,
            "scheduled_for": c.scheduled_for.isoformat() if c.scheduled_for else None,
            "file_url": f"/api/content/{c.id}/file" if c.file_path else None,
            "poster_url": f"/api/content/{c.id}/poster" if (c.meta or {}).get("poster") else None,
            "created_at": c.created_at.isoformat()}


def job_out(j: Job) -> dict:
    return {"id": j.id, "kind": j.kind, "status": j.status.value, "params": j.params, "result": j.result,
            "error": j.error, "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None}


# ------------------------------------------------------------------ lavori in background

def run_flyer_job(app_state: AppState, flyer_id: int) -> None:
    s = app_state.db.new_session()
    try:
        flyer = s.get(Flyer, flyer_id)
        if flyer is not None:
            process_flyer(s, flyer, app_state.settings, app_state.llm)
            s.commit()
    except Exception:  # process_flyer gestisce già gli errori di lettura; questo è l'ultimo riparo
        s.rollback()
        log.exception("Lettura del volantino %s fallita", flyer_id)
        flyer = s.get(Flyer, flyer_id)
        if flyer is not None:
            flyer.status, flyer.error = FlyerStatus.failed, "Errore interno durante la lettura."
            s.commit()
    finally:
        s.close()


def run_kit_job(app_state: AppState, job_id: int) -> None:
    s = app_state.db.new_session()
    try:
        job = s.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.running
        s.commit()
        flyer = s.get(Flyer, job.params["flyer_id"])
        store = s.get(Store, job.store_id)

        def progress(item: str, done: int, total: int) -> None:
            j = s.get(Job, job_id)
            j.result = {**(j.result or {}), "current": ITEMS.get(item, ""), "done": done, "total": total}
            s.commit()
        try:
            res = run_kit(s, store, flyer, app_state.settings, app_state.llm, job.params["items"], progress)
            job = s.get(Job, job_id)
            job.result = {**job.result, **res, "current": ""}
            job.status = JobStatus.done if not res["errors"] or res["done"] else JobStatus.failed
            job.error = "; ".join(res["errors"])[:2000]
        except Exception as exc:
            s.rollback()
            job = s.get(Job, job_id)
            job.status, job.error = JobStatus.failed, str(exc)[:2000]
            log.exception("Pacchetto del lavoro %s fallito", job_id)
        job.finished_at = datetime.now(timezone.utc)
        s.commit()
    finally:
        s.close()


AUTOPILOT_ITEMS = ["texts", "images", "video_portrait", "video_square", "video_landscape"]


def run_autopilot_job(app_state: AppState, job_id: int) -> None:
    """Gli agenti fanno tutto da soli: leggono il volantino, controllano i prezzi, scelgono le offerte,
    scrivono i testi, preparano grafiche e video e il piano della settimana."""
    s = app_state.db.new_session()
    try:
        job = s.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.running
        job.result = {**job.result, "stage": "reading"}
        s.commit()
        flyer_id = job.params["flyer_id"]

        def update(**kw) -> None:
            j = s.get(Job, job_id)
            j.result = {**(j.result or {}), **kw}
            s.commit()

        # 1. Lettore e Controllo
        try:
            flyer = s.get(Flyer, flyer_id)
            process_flyer(s, flyer, app_state.settings, app_state.llm,
                          progress=lambda page, pages: update(stage="reading", page=page + 1, pages=pages))
            s.commit()
        except Exception:  # noqa: BLE001 - l'ultimo riparo: il volantino resta con l'errore
            s.rollback()
            log.exception("Lettura del volantino %s fallita", flyer_id)
            flyer = s.get(Flyer, flyer_id)
            if flyer is not None:
                flyer.status, flyer.error = FlyerStatus.failed, "Errore interno durante la lettura."
            s.commit()
        flyer = s.get(Flyer, flyer_id)
        job = s.get(Job, job_id)
        if flyer is None or flyer.status != FlyerStatus.ready or not flyer.offers:
            job.status = JobStatus.failed
            job.error = (flyer.error if flyer is not None and flyer.error else
                         "Nessuna offerta trovata nel volantino: aggiungile a mano o prova un file più nitido.")
            job.result = {**job.result, "stage": "failed"}
            job.finished_at = datetime.now(timezone.utc)
            s.commit()
            return
        update(stage="checked", offers=len(flyer.offers),
               unverified=sum(1 for o in flyer.offers if not o.price_verified))
        # 2. Stratega, copywriter, grafico, montatore, pianificatore
        store = s.get(Store, job.store_id)
        items = job.params.get("items") or AUTOPILOT_ITEMS

        def progress(item: str, done: int, total: int) -> None:
            update(stage="making", item=item, current=ITEMS.get(item, ""), done=done, total=total)
        res = run_kit(s, store, flyer, app_state.settings, app_state.llm, items, progress)
        job = s.get(Job, job_id)
        job.result = {**job.result, **res, "stage": "done", "current": "", "item": ""}
        job.status = JobStatus.done if res["done"] else JobStatus.failed
        job.error = "; ".join(res["errors"])[:2000]
        job.finished_at = datetime.now(timezone.utc)
        s.commit()
    except Exception as exc:  # noqa: BLE001
        s.rollback()
        log.exception("Pilota automatico %s fallito", job_id)
        job = s.get(Job, job_id)
        if job is not None:
            job.status, job.error = JobStatus.failed, str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            s.commit()
    finally:
        s.close()


def run_clip_job(app_state: AppState, job_id: int) -> None:
    """Monta un Reel "dal banco" in background."""
    s = app_state.db.new_session()
    try:
        job = s.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.running
        s.commit()
        p = job.params
        voice_file = Path(p["voice"]) if p.get("voice") else None
        try:
            store = s.get(Store, job.store_id)
            piece = make_reel(s, store, app_state.settings, app_state.llm, Path(p["video"]), p.get("offer_id"),
                              p.get("note", ""), p.get("voice_mode", "none"), voice_file,
                              voice_client=app_state.voice_client, spoken_script=p.get("script", ""))
            job = s.get(Job, job_id)
            job.status = JobStatus.done
            job.result = {"content_id": piece.id, "warnings": piece.meta.get("warnings", []),
                          "duration": piece.meta.get("duration"), "subtitles": piece.meta.get("subtitles", "")}
        except (ClipFailed, ClipError, voicemod.VoiceError) as exc:   # errori spiegabili al negoziante
            s.rollback()
            job = s.get(Job, job_id)
            job.status, job.error = JobStatus.failed, str(exc)[:2000]
            Path(p["video"]).unlink(missing_ok=True)
        except Exception as exc:
            s.rollback()
            job = s.get(Job, job_id)
            job.status, job.error = JobStatus.failed, f"Montaggio non riuscito: {str(exc)[:1500]}"
            Path(p["video"]).unlink(missing_ok=True)
            log.exception("Reel del lavoro %s fallito", job_id)
        finally:
            if voice_file is not None:
                voice_file.unlink(missing_ok=True)
        job.finished_at = datetime.now(timezone.utc)
        s.commit()
    finally:
        s.close()


def run_video_job(app_state: AppState, job_id: int) -> None:
    s = app_state.db.new_session()
    try:
        job = s.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.running
        s.commit()
        try:
            flyer = s.get(Flyer, job.params["flyer_id"])
            store = s.get(Store, job.store_id)
            piece = render_flyer_video(s, store, flyer, app_state.settings, job.params["format"],
                                       float(job.params.get("scale", 1.0)))
            job.status = JobStatus.done
            job.result = {"content_id": piece.id, **piece.meta}
        except Exception as exc:  # il lavoro fallisce in modo pulito, con il motivo
            s.rollback()
            job = s.get(Job, job_id)
            job.status = JobStatus.failed
            job.error = str(exc)[:2000]
            log.exception("Video del lavoro %s fallito", job_id)
        job.finished_at = datetime.now(timezone.utc)
        s.commit()
    finally:
        s.close()


# ------------------------------------------------------------------ applicazione

def create_app(settings: Settings | None = None, llm: LLM | None = None, db: Database | None = None,
               use_ai: bool = True) -> FastAPI:
    settings = settings or get_settings()
    db = db or Database(settings.database_url)
    db.create_all()
    settings.ensure_dirs()
    from .. import extras
    extras.set_data_dir(settings.data_dir)
    keys.load_voice_key(settings)
    if llm is None and use_ai:
        llm = keys.make_llm(settings)

    app = FastAPI(title="Promovo", version="0.1.0",
                  description="Agenti che trasformano il volantino del supermercato in contenuti pronti per i social.")
    app.state.promovo = AppState(settings=settings, db=db, llm=llm)

    @app.exception_handler(AIUnavailable)
    async def _ai_unavailable(_: Request, exc: AIUnavailable):
        return JSONResponse(status_code=503, content={"detail": f"IA non disponibile: {exc}"})

    @app.exception_handler(AIRefused)
    async def _ai_refused(_: Request, exc: AIRefused):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    # -------------------------------------------------- sistema

    @app.get("/api/health")
    def health(request: Request):
        return {"ok": True, "ai": state(request).llm is not None, "version": app.version}

    # -------------------------------------------------- impostazioni: chiavi facoltative

    def settings_out(request: Request) -> dict:
        st = state(request)
        from ..modules.flyer import ocr
        out = {"agents": {"ocr": ocr.available(), "weather": st.settings.weather},
               "ai_mode_off": st.settings.ai_mode == "off"}
        for service in keys.SERVICES:
            key = keys.get(st.settings, service)
            out[service] = {"configured": bool(key), "masked": keys.mask(key), "source": keys.source(st.settings, service)}
        out["ai"]["active"] = st.llm is not None
        return out

    @app.get("/api/settings")
    def get_app_settings(request: Request, user: User = Depends(current_user)):
        return settings_out(request)

    # -------------------------------------------------- agenti aggiuntivi (modelli open source sul computer)

    @app.get("/api/extras")
    def list_extras(user: User = Depends(current_user)):
        return extras.status()

    @app.post("/api/extras/{key}/download", status_code=202)
    def download_extra(key: str, request: Request, user: User = Depends(require_owner)):
        if key not in extras.EXTRAS:
            raise HTTPException(404, "Agente sconosciuto.")
        if not any(x["key"] == key and (x["ready"] or x["downloading"]) for x in extras.status()):
            fetch = getattr(state(request), "extras_download", None) or extras.download
            import threading

            def run():
                try:
                    fetch(key)
                except Exception as exc:          # l'errore resta visibile nello stato dell'agente
                    log.warning("scaricamento %s non riuscito: %s", key, exc)
            threading.Thread(target=run, daemon=True).start()
        return next(x for x in extras.status() if x["key"] == key)

    @app.delete("/api/extras/{key}", status_code=204)
    def remove_extra(key: str, user: User = Depends(require_owner)):
        if key not in extras.EXTRAS:
            raise HTTPException(404, "Agente sconosciuto.")
        extras.remove(key)

    @app.post("/api/settings/keys")
    def save_key(body: KeyIn, request: Request, user: User = Depends(require_owner)):
        st = state(request)
        try:
            key = keys.clean(body.service, body.key)
            (keys.test_ai if body.service == "ai" else keys.test_voice)(key, st.key_test_client)
        except keys.KeyError_ as exc:
            raise HTTPException(422, str(exc)) from exc
        keys.save(st.settings, body.service, key)
        if body.service == "ai":
            st.llm = keys.make_llm(st.settings, st.llm_client)
        return settings_out(request)

    @app.delete("/api/settings/keys/{service}")
    def delete_key(service: str, request: Request, user: User = Depends(require_owner)):
        if service not in keys.SERVICES:
            raise HTTPException(404, "Servizio sconosciuto.")
        st = state(request)
        keys.remove(st.settings, service)
        if service == "ai":
            st.llm = keys.make_llm(st.settings, None) if keys.get(st.settings, "ai") else None
        return settings_out(request)

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))

    WEB_TYPES = {".woff2": "font/woff2", ".jpg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml"}

    @app.get("/assets/{name}")
    def web_asset(name: str):
        """Caratteri e immagini dell'interfaccia: inclusi nel programma, funzionano anche senza internet."""
        path = WEB_DIR / "assets" / name
        if "/" in name or "\\" in name or path.suffix not in WEB_TYPES or not path.is_file():
            raise HTTPException(404, "File non trovato.")
        return FileResponse(path, media_type=WEB_TYPES[path.suffix], headers={"Cache-Control": "public, max-age=86400"})

    # -------------------------------------------------- accesso

    @app.post("/api/auth/register", status_code=201)
    def register(body: RegisterIn, request: Request, session: Session = Depends(get_session)):
        email = body.email.lower()
        if session.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "Email già registrata.")
        org = Organization(name=body.organization.strip(), kind=body.kind)
        session.add(org)
        session.flush()
        user = User(organization_id=org.id, email=email, name=body.name.strip(),
                    password_hash=hash_password(body.password), role=Role.owner)
        session.add(user)
        session.flush()
        token = issue_token(session, user, state(request).settings.token_ttl_hours)
        return {"token": token, "user": {"id": user.id, "email": user.email, "role": user.role.value},
                "organization": {"id": org.id, "name": org.name, "kind": org.kind}}

    @app.post("/api/auth/login")
    def login(body: LoginIn, request: Request, session: Session = Depends(get_session)):
        user = session.scalar(select(User).where(User.email == body.email.lower()))
        if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "Email o password non corretti.")
        return {"token": issue_token(session, user, state(request).settings.token_ttl_hours)}

    @app.post("/api/auth/logout", status_code=204)
    def logout(request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
        revoke_token(session, bearer_token(request))

    @app.get("/api/me")
    def me(user: User = Depends(current_user)):
        org = user.organization
        return {"id": user.id, "email": user.email, "name": user.name, "role": user.role.value,
                "organization": {"id": org.id, "name": org.name, "kind": org.kind}}

    @app.post("/api/users", status_code=201)
    def add_user(body: UserIn, owner: User = Depends(require_owner), session: Session = Depends(get_session)):
        email = body.email.lower()
        if session.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "Email già registrata.")
        u = User(organization_id=owner.organization_id, email=email, name=body.name,
                 password_hash=hash_password(body.password), role=body.role)
        session.add(u)
        session.flush()
        return {"id": u.id, "email": u.email, "role": u.role.value}

    # -------------------------------------------------- negozi

    @app.get("/api/stores")
    def list_stores(user: User = Depends(current_user), session: Session = Depends(get_session)):
        rows = session.scalars(select(Store).where(Store.organization_id == user.organization_id)
                               .order_by(Store.name)).all()
        return [store_out(s) for s in rows]

    @app.post("/api/stores", status_code=201)
    def create_store(body: StoreIn, user: User = Depends(require_owner), session: Session = Depends(get_session)):
        s = Store(organization_id=user.organization_id, **body.model_dump())
        session.add(s)
        session.flush()
        return store_out(s)

    @app.get("/api/stores/{store_id}")
    def get_store(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        return store_out(store_for(session, user, store_id))

    @app.patch("/api/stores/{store_id}")
    def patch_store(store_id: int, body: StorePatch, user: User = Depends(require_owner),
                    session: Session = Depends(get_session)):
        s = store_for(session, user, store_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            if v is not None:
                setattr(s, k, v)
        session.flush()
        return store_out(s)

    @app.post("/api/stores/{store_id}/logo")
    async def upload_logo(store_id: int, request: Request, file: UploadFile = File(...),
                          user: User = Depends(require_owner), session: Session = Depends(get_session)):
        """Logo del negozio: compare nei video e nelle grafiche (JPG su bianco viene scontornato)."""
        s_ = store_for(session, user, store_id)
        data = await file.read(8 * 1024 * 1024 + 1)
        out = state(request).settings.data_dir / "logos" / f"{s_.id}_{secrets.token_hex(4)}.png"
        try:
            load_logo(data, out)
        except ImageError as exc:
            raise HTTPException(400, str(exc)) from exc
        if s_.logo_path:
            Path(s_.logo_path).unlink(missing_ok=True)
        s_.logo_path = str(out)
        session.flush()
        return store_out(s_)

    @app.get("/api/stores/{store_id}/logo")
    def get_logo(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        s_ = store_for(session, user, store_id)
        if not s_.logo_path or not Path(s_.logo_path).exists():
            raise HTTPException(404, "Logo non presente.")
        return FileResponse(s_.logo_path, media_type="image/png")

    @app.delete("/api/stores/{store_id}/logo", status_code=204)
    def delete_logo(store_id: int, user: User = Depends(require_owner), session: Session = Depends(get_session)):
        s_ = store_for(session, user, store_id)
        if s_.logo_path:
            Path(s_.logo_path).unlink(missing_ok=True)
        s_.logo_path = ""

    @app.get("/api/agency/overview")
    def agency_overview(user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Tutti i negozi dell'organizzazione con lo stato dell'ultimo volantino: la vista dell'agenzia."""
        out = []
        for st in session.scalars(select(Store).where(Store.organization_id == user.organization_id)
                                  .order_by(Store.name)).all():
            last = session.scalars(select(Flyer).where(Flyer.store_id == st.id, Flyer.competitor == "")
                                   .order_by(Flyer.created_at.desc(), Flyer.id.desc()).limit(1)).first()
            pieces = session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == last.id,
                                                                ContentPiece.kind != "plan")).all() if last else []
            out.append({
                "store": store_out(st),
                "last_flyer": flyer_out(last) if last else None,
                "content_total": len(pieces),
                "content_approved": sum(1 for p in pieces if p.approved),
            })
        return out

    @app.delete("/api/stores/{store_id}", status_code=204)
    def delete_store(store_id: int, request: Request, user: User = Depends(require_owner),
                     session: Session = Depends(get_session)):
        s = store_for(session, user, store_id)
        for f in list(s.flyers):
            delete_flyer_files(f, state(request).settings)
        if s.logo_path:
            Path(s.logo_path).unlink(missing_ok=True)
        session.delete(s)

    # -------------------------------------------------- volantini e offerte

    @app.post("/api/stores/{store_id}/flyers", status_code=202)
    async def upload_flyer(store_id: int, request: Request, background: BackgroundTasks,
                           file: UploadFile = File(...), title: str = Form(default=""),
                           autopilot: bool = Form(default=False),
                           user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Salva il PDF e avvia la lettura in background: interrogare GET /api/flyers/{id} fino a "ready".
        Con autopilot=true gli agenti preparano anche tutti i materiali: seguire il lavoro con
        GET /api/jobs/{autopilot_job}."""
        store = store_for(session, user, store_id)
        st = state(request)
        limit = st.settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"Il file supera {st.settings.max_upload_mb} MB.")
        try:
            flyer = create_flyer(session, store, data, st.settings, title=title.strip()[:300])
        except InvalidPDF as exc:
            raise HTTPException(400, str(exc)) from exc
        session.commit()
        if autopilot:
            job = Job(store_id=store.id, kind="autopilot", params={"flyer_id": flyer.id, "items": AUTOPILOT_ITEMS},
                      result={"stage": "queued", "total": len(AUTOPILOT_ITEMS), "done": 0, "current": "", "errors": []})
            session.add(job)
            session.commit()
            background.add_task(run_autopilot_job, st, job.id)
            return {**flyer_out(flyer), "autopilot_job": job.id}
        background.add_task(run_flyer_job, st, flyer.id)
        return flyer_out(flyer)

    @app.post("/api/flyers/{flyer_id}/reprocess", status_code=202)
    def reprocess_flyer(flyer_id: int, request: Request, background: BackgroundTasks,
                        user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Rilegge un volantino (es. dopo un errore o con l'IA appena attivata). Le correzioni manuali si perdono."""
        f = flyer_for(session, user, flyer_id)
        if f.status == FlyerStatus.processing:
            raise HTTPException(409, "Il volantino è già in lettura.")
        for o in list(f.offers):
            session.delete(o)
        f.status, f.error, f.warnings = FlyerStatus.processing, "", []
        session.commit()
        background.add_task(run_flyer_job, state(request), f.id)
        return flyer_out(f)

    # -------------------------------------------------- radar del quartiere

    @app.post("/api/stores/{store_id}/competitors", status_code=202)
    async def upload_competitor(store_id: int, request: Request, background: BackgroundTasks,
                                file: UploadFile = File(...), competitor: str = Form(...),
                                user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Volantino di un concorrente della zona: si legge come gli altri, serve solo per il confronto."""
        store = store_for(session, user, store_id)
        name = competitor.strip()
        if len(name) < 2:
            raise HTTPException(400, "Scrivi il nome del concorrente (es. «Conad via Roma»).")
        st = state(request)
        limit = st.settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"Il file supera {st.settings.max_upload_mb} MB.")
        try:
            flyer = create_flyer(session, store, data, st.settings, title=f"Volantino {name}"[:300], competitor=name)
        except InvalidPDF as exc:
            raise HTTPException(400, str(exc)) from exc
        session.commit()
        background.add_task(run_flyer_job, st, flyer.id)
        return flyer_out(flyer)

    @app.post("/api/stores/{store_id}/competitors/link", status_code=202)
    def competitor_from_link(store_id: int, body: CompetitorLinkIn, request: Request, background: BackgroundTasks,
                             user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Volantino del concorrente da un link (il PDF pubblicato sul sito dell'insegna)."""
        store = store_for(session, user, store_id)
        st = state(request)
        get = st.link_download or nearbymod.download_flyer
        try:
            data = get(body.url, st.settings.max_upload_mb * 1024 * 1024)
            flyer = create_flyer(session, store, data, st.settings, title=f"Volantino {body.competitor.strip()}"[:300],
                                 competitor=body.competitor.strip())
        except (nearbymod.LinkError, InvalidPDF) as exc:
            raise HTTPException(400, str(exc)) from exc
        session.commit()
        background.add_task(run_flyer_job, st, flyer.id)
        return flyer_out(flyer)

    @app.get("/api/stores/{store_id}/nearby")
    def stores_nearby(store_id: int, request: Request, radius: int = 3000, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
        """I supermercati veri intorno al negozio (OpenStreetMap): i concorrenti da mettere nel radar."""
        store = store_for(session, user, store_id)
        st = state(request)
        try:
            return {"ok": True, **nearbymod.nearby(store, radius, fetch=st.nearby_fetch or nearbymod.http_json,
                                                   cache_dir=st.settings.data_dir / "nearby",
                                                   pause=0 if st.nearby_fetch else 3.0)}
        except nearbymod.NearbyUnavailable as exc:
            return {"ok": False, "reason": str(exc), "places": [], "attribution": nearbymod.ATTRIBUTION}

    @app.get("/api/stores/{store_id}/competitors")
    def list_competitors(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        rows = session.scalars(select(Flyer).where(Flyer.store_id == store.id, Flyer.competitor != "")
                               .order_by(Flyer.created_at.desc(), Flyer.id.desc())).all()
        return [flyer_out(f) for f in rows]

    @app.get("/api/flyers/{flyer_id}/radar")
    def flyer_radar(flyer_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        f = flyer_for(session, user, flyer_id)
        if f.competitor:
            raise HTTPException(400, "Il radar si calcola sui volantini del negozio, non su quelli dei concorrenti.")
        return radar_report(session, f.store, f)

    @app.get("/api/flyers/{flyer_id}/weather")
    def flyer_weather(flyer_id: int, request: Request, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
        """Previsioni della zona per i giorni del volantino e prodotti da spingere."""
        f = flyer_for(session, user, flyer_id)
        st = state(request)
        return weekly_weather(f.store, f, fetch=st.weather_fetch, enabled=st.settings.weather)

    @app.post("/api/flyers/{flyer_id}/feature")
    def feature_offers(flyer_id: int, body: FeatureIn, user: User = Depends(current_user),
                       session: Session = Depends(get_session)):
        """Mette in evidenza le offerte indicate (es. quelle dove il negozio è il più conveniente)."""
        f = flyer_for(session, user, flyer_id)
        ids = set(body.offer_ids)
        for o in f.offers:
            if o.id in ids:
                o.is_featured = True
        session.flush()
        return flyer_out(f, with_offers=True)

    @app.get("/api/stores/{store_id}/flyers")
    def list_flyers(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        rows = session.scalars(select(Flyer).where(Flyer.store_id == store.id, Flyer.competitor == "")
                               .order_by(Flyer.created_at.desc(), Flyer.id.desc())).all()
        return [flyer_out(f) for f in rows]

    @app.get("/api/flyers/{flyer_id}")
    def get_flyer(flyer_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        return flyer_out(flyer_for(session, user, flyer_id), with_offers=True)

    @app.delete("/api/flyers/{flyer_id}", status_code=204)
    def delete_flyer(flyer_id: int, request: Request, user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
        f = flyer_for(session, user, flyer_id)
        delete_flyer_files(f, state(request).settings)
        session.delete(f)

    @app.patch("/api/offers/{offer_id}")
    def patch_offer(offer_id: int, body: OfferPatch, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
        o = offer_for(session, user, offer_id)
        data = body.model_dump(exclude_unset=True)
        prices_changed = "price" in data or "old_price" in data
        if data.pop("confirm", None):
            o.price_verified = True
            o.verified_by = "persona"
        if "price" in data:
            cents = parse_price(data.pop("price"))
            if cents is None or cents <= 0:
                raise HTTPException(422, "Prezzo non valido.")
            o.price_cents = cents
            o.price_verified = True  # corretto a mano da una persona
            o.verified_by = "persona"
        if "old_price" in data:
            raw = data.pop("old_price")
            cents = parse_price(raw) if raw else None
            if raw and cents is None:
                raise HTTPException(422, "Prezzo precedente non valido.")
            o.old_price_cents = cents
        if "cost" in data:
            raw = data.pop("cost")
            cents = parse_price(raw) if raw else None
            if raw and cents is None:
                raise HTTPException(422, "Costo non valido.")
            o.cost_cents = cents
        if o.old_price_cents is not None and o.old_price_cents <= o.price_cents:
            raise HTTPException(422, "Il prezzo precedente deve essere più alto del prezzo in offerta.")
        if prices_changed:
            # Lo sconto si ricalcola solo se cambiano i prezzi: uno sconto stampato resta.
            o.discount_percent = discount_percent(o.price_cents, o.old_price_cents)
        for k, v in data.items():
            if v is not None:
                setattr(o, k, v)
        session.flush()
        return offer_out(o)

    @app.get("/api/flyers/{flyer_id}/thumb")
    def flyer_thumb(flyer_id: int, request: Request, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
        """La prima pagina del volantino in piccolo, per riconoscerlo a colpo d'occhio."""
        f = flyer_for(session, user, flyer_id)
        out = state(request).settings.data_dir / "thumbs" / f"{f.id}.jpg"
        src = Path(f.pdf_path)
        if not src.exists():
            raise HTTPException(404, "Volantino non disponibile.")
        if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
            import pymupdf
            out.parent.mkdir(parents=True, exist_ok=True)
            with pymupdf.open(src) as doc:
                page = doc[0]
                zoom = 420 / max(page.rect.width, page.rect.height)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                pix.save(str(out), jpg_quality=82)
        return FileResponse(out, media_type="image/jpeg")

    @app.get("/api/offers/{offer_id}/image")
    def offer_image(offer_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        o = offer_for(session, user, offer_id)
        if not o.crop_path or not Path(o.crop_path).exists():
            raise HTTPException(404, "Immagine non disponibile.")
        return FileResponse(o.crop_path, media_type="image/png")

    @app.get("/api/offers/{offer_id}/photo")
    def offer_photo(offer_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        o = offer_for(session, user, offer_id)
        if not o.photo_path or not Path(o.photo_path).exists():
            raise HTTPException(404, "Foto non disponibile.")
        return FileResponse(o.photo_path, media_type="image/png")

    @app.post("/api/offers/{offer_id}/photo")
    async def upload_offer_photo(offer_id: int, request: Request, file: UploadFile = File(...),
                                 user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Sostituisce la foto del prodotto (es. una foto migliore della confezione)."""
        o = offer_for(session, user, offer_id)
        data = await file.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, "La foto supera 10 MB.")
        try:
            img = open_image(data)
        except ImageError as exc:
            raise HTTPException(400, str(exc)) from exc
        out = state(request).settings.data_dir / "crops" / str(o.flyer_id) / f"manuale_{o.id}_{secrets.token_hex(4)}.png"
        if o.photo_path and "manuale_" in o.photo_path:
            Path(o.photo_path).unlink(missing_ok=True)
        o.photo_path = str(save_product_photo(img, out))
        session.flush()
        return offer_out(o)

    @app.delete("/api/offers/{offer_id}", status_code=204)
    def delete_offer(offer_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Toglie un'offerta letta per errore (es. un riquadro che non è un prodotto)."""
        o = offer_for(session, user, offer_id)
        session.delete(o)

    @app.post("/api/flyers/{flyer_id}/offers", status_code=201)
    def add_offer(flyer_id: int, body: OfferIn, user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
        """Aggiunge a mano un'offerta che la lettura automatica non ha trovato."""
        f = flyer_for(session, user, flyer_id)
        price = parse_price(body.price)
        if price is None or price <= 0:
            raise HTTPException(422, "Prezzo non valido.")
        old = parse_price(body.old_price) if body.old_price.strip() else None
        if body.old_price.strip() and old is None:
            raise HTTPException(422, "Prezzo precedente non valido.")
        if old is not None and old <= price:
            raise HTTPException(422, "Il prezzo precedente deve essere più alto del prezzo in offerta.")
        o = Offer(flyer_id=f.id, position=max((x.position for x in f.offers), default=-1) + 1, page=0,
                  name=body.name.strip(), brand=body.brand.strip(), description=body.description.strip(),
                  category=body.category, price_cents=price, old_price_cents=old,
                  discount_percent=discount_percent(price, old), conditions=body.conditions.strip(),
                  is_featured=body.is_featured, price_verified=True, verified_by="persona", manual=True)
        session.add(o)
        session.flush()
        return offer_out(o)

    @app.post("/api/flyers/{flyer_id}/confirm")
    def confirm_offers(flyer_id: int, body: ConfirmIn, user: User = Depends(current_user),
                       session: Session = Depends(get_session)):
        """Conferma in blocco i prezzi controllati da una persona."""
        f = flyer_for(session, user, flyer_id)
        wanted = set(body.offer_ids)
        n = 0
        for o in f.offers:
            if o.id in wanted and not o.price_verified:
                o.price_verified, o.verified_by = True, "persona"
                n += 1
        session.flush()
        return {"confirmed": n, "unverified_left": sum(1 for o in f.offers if not o.price_verified)}

    # -------------------------------------------------- contenuti e video

    @app.post("/api/flyers/{flyer_id}/content", status_code=201)
    def make_content(flyer_id: int, request: Request, another: bool = False, user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
        """Scrive (o riscrive) i testi del volantino. another=true: un'idea diversa da quella attuale."""
        f = flyer_for(session, user, flyer_id)
        from ..modules.weather.service import weekly_weather
        st = state(request)
        weather = weekly_weather(f.store, f, fetch=st.weather_fetch, enabled=st.settings.weather) \
            if st.settings.weather else None
        pack = generate_content(f.store, f, st.llm, weather=weather, another=another)
        pieces = save_content(session, f.store, f, pack)
        has_images = session.scalar(select(func.count()).select_from(ContentPiece).where(
            ContentPiece.flyer_id == f.id, ContentPiece.kind == "image"))
        if another and has_images:
            from ..modules.graphics.service import render_idea_image
            render_idea_image(session, f.store, f, st.settings)      # la grafica segue la nuova idea
        return {"source": pack.source, "warnings": pack.warnings, "content": [content_out(p) for p in pieces]}

    @app.get("/api/stores/{store_id}/content")
    def list_content(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        rows = session.scalars(select(ContentPiece).where(ContentPiece.store_id == store.id)
                               .order_by(ContentPiece.created_at.desc(), ContentPiece.id.desc())).all()
        return [content_out(c) for c in rows]

    @app.patch("/api/content/{content_id}")
    def patch_content(content_id: int, body: ContentPatch, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
        c = content_for(session, user, content_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(c, k, v)
        session.flush()
        return content_out(c)

    @app.get("/api/content/{content_id}/file")
    def content_file(content_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        c = content_for(session, user, content_id)
        if not c.file_path or not Path(c.file_path).exists():
            raise HTTPException(404, "File non disponibile.")
        media = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
        return FileResponse(c.file_path, media_type=media.get(Path(c.file_path).suffix.lower(), "application/octet-stream"),
                            filename=Path(c.file_path).name)

    @app.get("/api/content/{content_id}/poster")
    def content_poster(content_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        c = content_for(session, user, content_id)
        poster = (c.meta or {}).get("poster")
        if not poster or not Path(poster).exists():
            raise HTTPException(404, "Anteprima non disponibile.")
        return FileResponse(poster, media_type="image/jpeg")

    @app.get("/api/flyers/{flyer_id}/content")
    def flyer_content(flyer_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        f = flyer_for(session, user, flyer_id)
        rows = session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == f.id).order_by(ContentPiece.id)).all()
        return [content_out(c) for c in rows]

    @app.post("/api/flyers/{flyer_id}/replicate", status_code=202)
    def replicate(flyer_id: int, body: ReplicateIn, request: Request, background: BackgroundTasks,
                  user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Catene: lo stesso volantino per altri punti vendita, con i materiali di ciascuno."""
        f = flyer_for(session, user, flyer_id)
        if f.status != FlyerStatus.ready or not f.offers:
            raise HTTPException(409, "Il volantino non è pronto o non ha offerte.")
        out = []
        for sid in dict.fromkeys(body.store_ids):
            if sid == f.store_id:
                continue
            target = store_for(session, user, sid)
            copy = replicate_flyer(session, f, target, state(request).settings)
            item = {"store_id": target.id, "store": target.name, "flyer_id": copy.id, "job_id": None}
            if body.make:
                job = Job(store_id=target.id, kind="kit", params={"flyer_id": copy.id, "items": AUTOPILOT_ITEMS},
                          result={"total": len(AUTOPILOT_ITEMS), "done": 0, "current": "", "errors": []})
                session.add(job)
                session.flush()
                item["job_id"] = job.id
            out.append(item)
        session.commit()
        for item in out:
            if item["job_id"]:
                background.add_task(run_kit_job, state(request), item["job_id"])
        return out

    @app.post("/api/flyers/{flyer_id}/kit", status_code=202)
    def make_kit(flyer_id: int, body: KitIn, request: Request, background: BackgroundTasks,
                 user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Crea in background tutti i materiali scelti; seguire l'avanzamento con GET /api/jobs/{id}."""
        f = flyer_for(session, user, flyer_id)
        if f.status != FlyerStatus.ready or not f.offers:
            raise HTTPException(409, "Il volantino non è pronto o non ha offerte.")
        running = session.scalars(select(Job).where(Job.store_id == f.store_id, Job.kind.in_(["kit", "autopilot"]),
                                                    Job.status.in_([JobStatus.queued, JobStatus.running]))).all()
        if any(j.params.get("flyer_id") == f.id for j in running):
            raise HTTPException(409, "I materiali di questo volantino sono già in preparazione.")
        job = Job(store_id=f.store_id, kind="kit", params={"flyer_id": f.id, "items": body.items},
                  result={"total": len(body.items), "done": 0, "current": "", "errors": []})
        session.add(job)
        session.commit()
        background.add_task(run_kit_job, state(request), job.id)
        return job_out(job)

    @app.get("/api/flyers/{flyer_id}/report.pdf")
    def download_report(flyer_id: int, request: Request, user: User = Depends(current_user),
                        session: Session = Depends(get_session)):
        """Il report della settimana da consegnare al cliente."""
        from ..modules.report import build_report
        f = flyer_for(session, user, flyer_id)
        out = state(request).settings.data_dir / "renders" / f"report_{uuid.uuid4().hex}.pdf"
        build_report(session, f.store, f, out)
        name = re.sub(r"[^\w]+", "_", f"Report_{f.store.name}")[:60] + ".pdf"
        return FileResponse(out, media_type="application/pdf", filename=name,
                            background=StarletteTask(lambda: out.unlink(missing_ok=True)))

    @app.get("/api/flyers/{flyer_id}/kit.zip")
    def download_kit(flyer_id: int, request: Request, approved_only: bool = False,
                     user: User = Depends(current_user), session: Session = Depends(get_session)):
        f = flyer_for(session, user, flyer_id)
        tmp_dir = state(request).settings.data_dir / "renders"
        tmp = tmp_dir / f"pacchetto_{f.id}_{secrets.token_hex(4)}.zip"
        build_zip(session, f.store, f, tmp, approved_only)
        name = f"Promovo_{re.sub(r'[^A-Za-z0-9]+', '_', f.store.name)}_{f.valid_from or f.id}.zip"
        return FileResponse(tmp, media_type="application/zip", filename=name,
                            background=StarletteTask(lambda: tmp.unlink(missing_ok=True)))

    @app.post("/api/flyers/{flyer_id}/video", status_code=202)
    def make_video(flyer_id: int, request: Request, background: BackgroundTasks, format: str = "landscape",
                   scale: float = 1.0, user: User = Depends(current_user), session: Session = Depends(get_session)):
        if format not in FORMATS:
            raise HTTPException(422, f"Formato non valido. Usa: {', '.join(FORMATS)}")
        if not 0.25 <= scale <= 1.0:
            raise HTTPException(422, "scale deve essere tra 0.25 e 1.")
        f = flyer_for(session, user, flyer_id)
        if f.status != FlyerStatus.ready or not f.offers:
            raise HTTPException(409, "Il volantino non è pronto o non ha offerte.")
        job = Job(store_id=f.store_id, kind="video", params={"flyer_id": f.id, "format": format, "scale": scale})
        session.add(job)
        session.commit()
        background.add_task(run_video_job, state(request), job.id)
        return job_out(job)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        return job_out(job_for(session, user, job_id))

    # -------------------------------------------------- dal banco al Reel

    async def _save_stream(file: UploadFile, dest_dir: Path, limit_mb: int, allowed: set[str], kind: str) -> Path:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in allowed:
            raise HTTPException(400, f"Formato {kind} non supportato ({ext or 'senza estensione'}).")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dst = dest_dir / f"up_{uuid.uuid4().hex}{ext}"
        size, limit = 0, limit_mb * 1024 * 1024
        with dst.open("wb") as fh:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    fh.close()
                    dst.unlink(missing_ok=True)
                    raise HTTPException(413, f"Il file supera {limit_mb} MB.")
                fh.write(chunk)
        if size == 0:
            dst.unlink(missing_ok=True)
            raise HTTPException(400, "Il file è vuoto.")
        return dst

    @app.post("/api/stores/{store_id}/clips", status_code=202)
    async def create_clip(store_id: int, request: Request, background: BackgroundTasks,
                          video: UploadFile = File(...), offer_id: str = Form(default=""), note: str = Form(default=""),
                          voice_mode: str = Form(default="none"), voice: UploadFile | None = File(default=None),
                          script: str = Form(default=""),
                          user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Carica un video girato in negozio e avvia il montaggio del Reel (seguire GET /api/jobs/{id})."""
        store = store_for(session, user, store_id)
        st = state(request)
        if voice_mode not in VOICE_MODES:
            raise HTTPException(400, "Modalità della voce non valida.")
        oid = None
        if offer_id.strip():
            try:
                oid = int(offer_id)
            except ValueError:
                raise HTTPException(400, "Prodotto non valido.")
            o = session.get(Offer, oid)
            if o is None or o.flyer.store_id != store.id:
                raise HTTPException(404, "Prodotto non trovato.")
        if voice_mode == "ai":
            if not (store.voice_id and store.voice_consent_at):
                raise HTTPException(409, "Prima crea la voce del negozio, con il consenso (Negozio → Voce).")
            if voicemod.api_key() is None:
                raise HTTPException(409, "Per la voce generata serve la chiave ElevenLabs (CHIAVE_VOCE.txt).")
        if voice_mode == "recorded" and voice is None:
            raise HTTPException(400, "Manca la registrazione della voce.")
        st.settings.ensure_dirs()
        video_path = await _save_stream(video, st.settings.data_dir / "clips", st.settings.max_video_mb,
                                        VIDEO_EXT, "video")
        voice_path = None
        if voice_mode == "recorded" and voice is not None:
            voice_path = await _save_stream(voice, st.settings.data_dir / "voices", 50, AUDIO_EXT, "audio")
        job = Job(store_id=store.id, kind="clip",
                  params={"video": str(video_path), "offer_id": oid, "note": note.strip()[:300],
                          "voice_mode": voice_mode, "voice": str(voice_path) if voice_path else "",
                          "script": script.strip()[:500] if voice_mode == "recorded" else ""})
        session.add(job)
        session.commit()
        background.add_task(run_clip_job, st, job.id)
        return job_out(job)

    @app.get("/api/stores/{store_id}/clips")
    def list_clips(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        rows = session.scalars(select(ContentPiece).where(ContentPiece.store_id == store.id,
                                                          ContentPiece.kind == "video")
                               .order_by(ContentPiece.created_at.desc(), ContentPiece.id.desc())).all()
        return [content_out(c) for c in rows if (c.meta or {}).get("format") == "clip"]

    @app.get("/api/stores/{store_id}/clips/script")
    def clip_script(store_id: int, offer_id: int | None = None, note: str = "", user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
        """Il testo da leggere per chi registra la propria voce."""
        store = store_for(session, user, store_id)
        return script_for(session, store, offer_id, note[:300])

    @app.delete("/api/content/{content_id}", status_code=204)
    def delete_content(content_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        c = content_for(session, user, content_id)
        if (c.meta or {}).get("format") == "clip":
            delete_clip_files(c)
        session.delete(c)

    # -------------------------------------------------- voce del negozio

    @app.post("/api/stores/{store_id}/voice")
    async def create_voice(store_id: int, request: Request, sample: UploadFile = File(...),
                           consent_name: str = Form(...), consent: str = Form(default=""),
                           user: User = Depends(require_owner), session: Session = Depends(get_session)):
        """Crea la voce clonata dal campione registrato. Serve il consenso esplicito di chi presta la voce."""
        store = store_for(session, user, store_id)
        st = state(request)
        if consent.lower() not in ("1", "true", "si", "sì", "on"):
            raise HTTPException(400, "Serve il consenso di chi presta la voce.")
        if len(consent_name.strip()) < 3:
            raise HTTPException(400, "Scrivi nome e cognome di chi presta la voce.")
        key = voicemod.api_key()
        if key is None:
            raise HTTPException(409, "Per la voce generata serve la chiave ElevenLabs (CHIAVE_VOCE.txt).")
        st.settings.ensure_dirs()
        sample_path = await _save_stream(sample, st.settings.data_dir / "voices", 50, AUDIO_EXT, "audio")
        try:
            from ..modules.clip.render import clean_voice
            wav = sample_path.with_name(sample_path.stem + "_pulita.wav")
            seconds = clean_voice(sample_path, wav)
            if seconds < 20:
                raise HTTPException(400, f"La registrazione dura {seconds:.0f} secondi: ne servono almeno 30 "
                                         "per una voce credibile.")
            try:
                vid = voicemod.clone_voice(f"{store.name} – {consent_name.strip()}", [wav], key,
                                           client=st.voice_client)
            except voicemod.VoiceError as exc:
                raise HTTPException(502, str(exc)) from exc
        finally:
            sample_path.unlink(missing_ok=True)
            sample_path.with_name(sample_path.stem + "_pulita.wav").unlink(missing_ok=True)
        if store.voice_id and store.voice_id != vid:
            try:
                voicemod.delete_voice(store.voice_id, key, client=st.voice_client)
            except voicemod.VoiceError:
                log.warning("Voce precedente non eliminata su ElevenLabs")
        store.voice_id, store.voice_consent_name = vid, consent_name.strip()[:200]
        store.voice_consent_at = datetime.now(timezone.utc)
        session.flush()
        return store_out(store)

    @app.delete("/api/stores/{store_id}/voice")
    def remove_voice(store_id: int, request: Request, user: User = Depends(require_owner),
                     session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        key = voicemod.api_key()
        if store.voice_id and key:
            try:
                voicemod.delete_voice(store.voice_id, key, client=state(request).voice_client)
            except voicemod.VoiceError:
                log.warning("Voce non eliminata su ElevenLabs")
        store.voice_id, store.voice_consent_name, store.voice_consent_at = "", "", None
        session.flush()
        return store_out(store)

    @app.get("/api/stores/{store_id}/overview")
    def overview(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        count = lambda model, *cond: session.scalar(select(func.count()).select_from(model).where(*cond))  # noqa: E731
        return {
            "store": store_out(store),
            "flyers": count(Flyer, Flyer.store_id == store.id, Flyer.competitor == ""),
            "active_offers": len(active_offers(session, store.id)),
            "content_to_approve": count(ContentPiece, ContentPiece.store_id == store.id,
                                        ContentPiece.approved.is_(False), ContentPiece.kind != "plan"),
        }

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        return JSONResponse(status_code=409, content={"detail": "Dato duplicato o in conflitto."})

    return app
