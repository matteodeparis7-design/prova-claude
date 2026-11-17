"""API web di Promovo e cruscotto."""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import Database
from ..llm import AIRefused, AIUnavailable, LLM, get_llm
from ..models import (
    ContentPiece, Conversation, Customer, Flyer, FlyerStatus, Job, JobStatus, Offer, Order, OrderStatus, Organization, Role,
    SaleRecord, Store, User,
)
from ..money import discount_percent, format_eur, parse_price
from ..security import hash_password, issue_token, revoke_token, verify_password
from ..text_utils import CATEGORIES
from ..modules.analytics.service import SalesImportError, flyer_performance, import_sales_csv
from ..modules.assistant.agent import OrderError, chat, normalize_phone
from ..modules.catalog import active_offers
from ..modules.content.service import generate_content, save_content
from ..modules.flyer.pdf import InvalidPDF
from ..modules.flyer.service import create_flyer, delete_flyer_files, process_flyer
from ..modules.loyalty.service import build_campaign, handle_inbound, set_consent
from ..modules.video.render import FORMATS
from ..modules.video.service import render_flyer_video
from .deps import (
    AppState, bearer_token, content_for, current_user, flyer_for, get_session, job_for, offer_for, order_for,
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

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str | None) -> str | None:
        if v is not None and v not in CATEGORIES:
            raise ValueError("Categoria non valida.")
        return v


class ContentPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=10000)
    approved: bool | None = None
    scheduled_for: datetime | None = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


class CustomerIn(BaseModel):
    name: str = Field(default="", max_length=200)
    phone: str = Field(min_length=6, max_length=40)
    email: str = Field(default="", max_length=255)
    marketing_consent: bool = False
    preferred_categories: list[str] = Field(default_factory=list)

    @field_validator("preferred_categories")
    @classmethod
    def _cats(cls, v: list[str]) -> list[str]:
        bad = [c for c in v if c not in CATEGORIES]
        if bad:
            raise ValueError(f"Categorie non valide: {', '.join(bad)}")
        return v


class ConsentIn(BaseModel):
    marketing_consent: bool


class OrderPatch(BaseModel):
    status: OrderStatus


class InboundIn(BaseModel):
    phone: str = Field(max_length=40)
    text: str = Field(max_length=4000)


# ------------------------------------------------------------------ serializzazione

def store_out(s: Store) -> dict:
    return {"id": s.id, "name": s.name, "banner": s.banner, "address": s.address, "city": s.city,
            "phone": s.phone, "opening_hours": s.opening_hours, "brand_color": s.brand_color,
            "accent_color": s.accent_color, "services": s.services, "pickup_enabled": s.pickup_enabled}


def offer_out(o: Offer) -> dict:
    return {"id": o.id, "page": o.page, "position": o.position, "name": o.name, "brand": o.brand,
            "description": o.description, "category": o.category, "price_cents": o.price_cents,
            "price": format_eur(o.price_cents), "old_price_cents": o.old_price_cents,
            "old_price": format_eur(o.old_price_cents), "discount_percent": o.discount_percent,
            "unit_price_text": o.unit_price_text, "conditions": o.conditions, "bbox": o.bbox,
            "price_verified": o.price_verified, "verified_by": o.verified_by, "is_featured": o.is_featured, "cost_cents": o.cost_cents,
            "image_url": f"/api/offers/{o.id}/image" if o.crop_path else None}


def flyer_out(f: Flyer, with_offers: bool = False) -> dict:
    out = {"id": f.id, "store_id": f.store_id, "title": f.title, "page_count": f.page_count,
           "valid_from": f.valid_from.isoformat() if f.valid_from else None,
           "valid_to": f.valid_to.isoformat() if f.valid_to else None, "status": f.status.value,
           "extraction_method": f.extraction_method, "error": f.error, "warnings": f.warnings,
           "offer_count": len(f.offers), "created_at": f.created_at.isoformat()}
    if with_offers:
        out["offers"] = [offer_out(o) for o in f.offers]
    return out


def content_out(c: ContentPiece) -> dict:
    return {"id": c.id, "store_id": c.store_id, "flyer_id": c.flyer_id, "kind": c.kind, "title": c.title,
            "body": c.body, "approved": c.approved, "meta": c.meta,
            "scheduled_for": c.scheduled_for.isoformat() if c.scheduled_for else None,
            "file_url": f"/api/content/{c.id}/file" if c.file_path else None,
            "created_at": c.created_at.isoformat()}


def order_out(o: Order) -> dict:
    return {"id": o.id, "store_id": o.store_id, "customer_name": o.customer_name,
            "customer_phone": o.customer_phone, "status": o.status.value,
            "pickup_at": o.pickup_at.isoformat() if o.pickup_at else None, "notes": o.notes,
            "total_cents": o.total_cents, "total": format_eur(o.total_cents),
            "items": [{"offer_id": i.offer_id, "name": i.name, "quantity": i.quantity,
                       "unit_price": format_eur(i.unit_price_cents)} for i in o.items],
            "created_at": o.created_at.isoformat()}


def customer_out(c: Customer) -> dict:
    return {"id": c.id, "name": c.name, "phone": c.phone, "email": c.email,
            "marketing_consent": c.marketing_consent, "preferred_categories": c.preferred_categories}


def job_out(j: Job) -> dict:
    return {"id": j.id, "kind": j.kind, "status": j.status.value, "params": j.params, "result": j.result,
            "error": j.error, "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None}


# ------------------------------------------------------------------ limite di richieste (chat pubblica)

class RateLimiter:
    def __init__(self, limit: int, window_s: float):
        self.limit, self.window = limit, window_s
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


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
    if llm is None and use_ai and settings.ai_mode != "off":
        llm = get_llm(settings.ai_mode, settings.model)

    app = FastAPI(title="Promovo", version="0.1.0",
                  description="Piattaforma di agenti IA per il marketing e i clienti dei supermercati.")
    app.state.promovo = AppState(settings=settings, db=db, llm=llm)
    public_limiter = RateLimiter(limit=20, window_s=60)

    @app.exception_handler(AIUnavailable)
    async def _ai_unavailable(_: Request, exc: AIUnavailable):
        return JSONResponse(status_code=503, content={"detail": f"IA non disponibile: {exc}"})

    @app.exception_handler(AIRefused)
    async def _ai_refused(_: Request, exc: AIRefused):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    def need_llm(request: Request) -> LLM:
        llm_ = state(request).llm
        if llm_ is None:
            raise AIUnavailable("IA non configurata.")
        return llm_

    # -------------------------------------------------- sistema

    @app.get("/api/health")
    def health(request: Request):
        return {"ok": True, "ai": state(request).llm is not None, "version": app.version}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))

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

    @app.delete("/api/stores/{store_id}", status_code=204)
    def delete_store(store_id: int, request: Request, user: User = Depends(require_owner),
                     session: Session = Depends(get_session)):
        s = store_for(session, user, store_id)
        for f in list(s.flyers):
            delete_flyer_files(f, state(request).settings)
        session.delete(s)

    # -------------------------------------------------- volantini e offerte

    @app.post("/api/stores/{store_id}/flyers", status_code=202)
    async def upload_flyer(store_id: int, request: Request, background: BackgroundTasks,
                           file: UploadFile = File(...), title: str = Form(default=""),
                           user: User = Depends(current_user), session: Session = Depends(get_session)):
        """Salva il PDF e avvia la lettura in background: interrogare GET /api/flyers/{id} fino a "ready"."""
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

    @app.get("/api/stores/{store_id}/flyers")
    def list_flyers(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        rows = session.scalars(select(Flyer).where(Flyer.store_id == store.id)
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
        o.discount_percent = discount_percent(o.price_cents, o.old_price_cents)
        for k, v in data.items():
            if v is not None:
                setattr(o, k, v)
        session.flush()
        return offer_out(o)

    @app.get("/api/offers/{offer_id}/image")
    def offer_image(offer_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        o = offer_for(session, user, offer_id)
        if not o.crop_path or not Path(o.crop_path).exists():
            raise HTTPException(404, "Immagine non disponibile.")
        return FileResponse(o.crop_path, media_type="image/png")

    # -------------------------------------------------- contenuti e video

    @app.post("/api/flyers/{flyer_id}/content", status_code=201)
    def make_content(flyer_id: int, request: Request, user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
        f = flyer_for(session, user, flyer_id)
        pack = generate_content(f.store, f, state(request).llm)
        pieces = save_content(session, f.store, f, pack)
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
        return FileResponse(c.file_path, media_type="video/mp4", filename=Path(c.file_path).name)

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

    # -------------------------------------------------- assistente clienti e ordini

    @app.post("/api/stores/{store_id}/chat")
    def staff_chat(store_id: int, body: ChatIn, request: Request, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        return _chat(session, store, body, need_llm(request), channel="test")

    @app.post("/public/stores/{store_id}/chat")
    def public_chat(store_id: int, body: ChatIn, request: Request, session: Session = Depends(get_session)):
        client = request.client.host if request.client else "?"
        if not public_limiter.allow(f"{client}:{store_id}"):
            raise HTTPException(429, "Troppi messaggi, riprova tra un minuto.")
        store = session.get(Store, store_id)
        if store is None:
            raise HTTPException(404, "Negozio non trovato.")
        return _chat(session, store, body, need_llm(request), channel="web")

    def _chat(session: Session, store: Store, body: ChatIn, llm_: LLM, channel: str) -> dict:
        conv = None
        if body.conversation_id is not None:
            conv = session.get(Conversation, body.conversation_id)
            if conv is None or conv.store_id != store.id:
                raise HTTPException(404, "Conversazione non trovata.")
        reply, conv = chat(session, store, llm_, body.message, conv, channel=channel)
        return {"reply": reply, "conversation_id": conv.id}

    @app.post("/api/stores/{store_id}/inbound")
    def inbound(store_id: int, body: InboundIn, user: User = Depends(current_user),
                session: Session = Depends(get_session)):
        """Messaggio ricevuto da un canale esterno (es. WhatsApp): gestisce le richieste di STOP."""
        store = store_for(session, user, store_id)
        return {"unsubscribed": handle_inbound(session, store, body.phone, body.text)}

    @app.get("/api/stores/{store_id}/orders")
    def list_orders(store_id: int, status_filter: OrderStatus | None = None, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        q = select(Order).where(Order.store_id == store.id)
        if status_filter is not None:
            q = q.where(Order.status == status_filter)
        return [order_out(o) for o in session.scalars(q.order_by(Order.created_at.desc(), Order.id.desc())).all()]

    @app.patch("/api/orders/{order_id}")
    def patch_order(order_id: int, body: OrderPatch, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
        o = order_for(session, user, order_id)
        allowed = {
            OrderStatus.new: {OrderStatus.confirmed, OrderStatus.cancelled},
            OrderStatus.confirmed: {OrderStatus.ready, OrderStatus.cancelled},
            OrderStatus.ready: {OrderStatus.collected, OrderStatus.cancelled},
            OrderStatus.collected: set(),
            OrderStatus.cancelled: set(),
        }
        if body.status not in allowed[o.status]:
            raise HTTPException(409, f"Passaggio non consentito: da {o.status.value} a {body.status.value}.")
        o.status = body.status
        session.flush()
        return order_out(o)

    # -------------------------------------------------- clienti e fedeltà

    @app.get("/api/stores/{store_id}/customers")
    def list_customers(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        rows = session.scalars(select(Customer).where(Customer.store_id == store.id).order_by(Customer.id)).all()
        return [customer_out(c) for c in rows]

    @app.post("/api/stores/{store_id}/customers", status_code=201)
    def add_customer(store_id: int, body: CustomerIn, user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        try:
            phone = normalize_phone(body.phone)
        except OrderError as exc:
            raise HTTPException(422, str(exc)) from exc
        if session.scalar(select(Customer).where(Customer.store_id == store.id, Customer.phone == phone)):
            raise HTTPException(409, "Cliente già presente con questo telefono.")
        c = Customer(store_id=store.id, name=body.name, phone=phone, email=body.email,
                     preferred_categories=body.preferred_categories)
        session.add(c)
        session.flush()
        set_consent(session, c, body.marketing_consent)
        return customer_out(c)

    @app.patch("/api/customers/{customer_id}/consent")
    def customer_consent(customer_id: int, body: ConsentIn, user: User = Depends(current_user),
                         session: Session = Depends(get_session)):
        c = session.get(Customer, customer_id)
        if c is None or c.store.organization_id != user.organization_id:
            raise HTTPException(404, "Cliente non trovato.")
        set_consent(session, c, body.marketing_consent)
        return customer_out(c)

    @app.post("/api/flyers/{flyer_id}/campaign", status_code=201)
    def campaign(flyer_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        f = flyer_for(session, user, flyer_id)
        pieces = build_campaign(session, f.store, f)
        return {"messages": [content_out(p) for p in pieces]}

    # -------------------------------------------------- vendite e risultati

    @app.post("/api/stores/{store_id}/sales", status_code=201)
    async def upload_sales(store_id: int, file: UploadFile = File(...), user: User = Depends(current_user),
                           session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        data = await file.read(50 * 1024 * 1024 + 1)
        if len(data) > 50 * 1024 * 1024:
            raise HTTPException(413, "Il file supera 50 MB.")
        try:
            rep = import_sales_csv(session, store, data)
        except SalesImportError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"imported": rep.imported, "skipped": rep.skipped, "errors": rep.errors,
                "first_day": rep.first_day.isoformat() if rep.first_day else None,
                "last_day": rep.last_day.isoformat() if rep.last_day else None}

    @app.get("/api/flyers/{flyer_id}/performance")
    def performance(flyer_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        f = flyer_for(session, user, flyer_id)
        try:
            return flyer_performance(session, f)
        except SalesImportError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/stores/{store_id}/overview")
    def overview(store_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        store = store_for(session, user, store_id)
        count = lambda model, *cond: session.scalar(select(func.count()).select_from(model).where(*cond))  # noqa: E731
        return {
            "store": store_out(store),
            "flyers": count(Flyer, Flyer.store_id == store.id),
            "active_offers": len(active_offers(session, store.id)),
            "customers": count(Customer, Customer.store_id == store.id),
            "customers_with_consent": count(Customer, Customer.store_id == store.id,
                                            Customer.marketing_consent.is_(True)),
            "open_orders": count(Order, Order.store_id == store.id,
                                 Order.status.in_([OrderStatus.new, OrderStatus.confirmed, OrderStatus.ready])),
            "content_to_approve": count(ContentPiece, ContentPiece.store_id == store.id,
                                        ContentPiece.approved.is_(False)),
            "sales_rows": count(SaleRecord, SaleRecord.store_id == store.id),
        }

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        return JSONResponse(status_code=409, content={"detail": "Dato duplicato o in conflitto."})

    return app
