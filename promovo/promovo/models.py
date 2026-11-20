"""Modello dei dati.

Struttura multi-negozio: chi usa Promovo (un'agenzia, un professionista o il negozio stesso)
gestisce uno o più punti vendita, ognuno con la sua identità (logo, colori, stile).

Tutti gli importi sono in centesimi di euro (interi) per evitare errori di arrotondamento.
"""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    owner = "owner"   # gestisce l'organizzazione e tutti i suoi negozi
    staff = "staff"   # lavora sui negozi, senza gestire utenti


class FlyerStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # "agency" = gestisce negozi di terzi; "store" = cliente diretto della piattaforma.
    kind: Mapped[str] = mapped_column(String(20), default="agency")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    users: Mapped[list[User]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    stores: Mapped[list[Store]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.owner)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="users")


class ApiToken(Base):
    __tablename__ = "api_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship()


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    banner: Mapped[str] = mapped_column(String(200), default="")      # insegna, es. "Superstore"
    address: Mapped[str] = mapped_column(String(300), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    # Orari: {"lun": "8:00-20:00", ...}
    opening_hours: Mapped[dict] = mapped_column(JSON, default=dict)
    brand_color: Mapped[str] = mapped_column(String(7), default="#D7262E")
    accent_color: Mapped[str] = mapped_column(String(7), default="#FFD23F")
    # Non più usati: restano solo perché i database già creati li hanno come colonne obbligatorie.
    services: Mapped[list] = mapped_column(JSON, default=list)
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Identità e comunicazione
    tone: Mapped[str] = mapped_column(String(30), default="familiare")   # familiare | elegante | giovane | essenziale
    hashtags: Mapped[list] = mapped_column(JSON, default=list)           # hashtag sempre presenti nei post
    whatsapp: Mapped[str] = mapped_column(String(40), default="")
    website: Mapped[str] = mapped_column(String(200), default="")
    logo_path: Mapped[str] = mapped_column(String(500), default="")
    video_music: Mapped[bool] = mapped_column(Boolean, default=True)
    # Voce clonata (ElevenLabs), solo con il consenso scritto di chi la presta.
    voice_id: Mapped[str] = mapped_column(String(100), default="")
    voice_consent_name: Mapped[str] = mapped_column(String(200), default="")
    voice_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Parola alla cassa: una parola d'ordine per canale nei testi, contata alla cassa
    till_on: Mapped[bool] = mapped_column(Boolean, default=False)
    till_reward: Mapped[str] = mapped_column(String(80), default="il 5% di sconto sulla spesa")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="stores")
    flyers: Mapped[list[Flyer]] = relationship(back_populates="store", cascade="all, delete-orphan")


class Flyer(Base):
    __tablename__ = "flyers"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    # Vuoto = volantino del negozio; altrimenti nome del concorrente (radar del quartiere).
    competitor: Mapped[str] = mapped_column(String(120), default="")
    pdf_path: Mapped[str] = mapped_column(String(500))
    pdf_sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[FlyerStatus] = mapped_column(Enum(FlyerStatus), default=FlyerStatus.uploaded)
    extraction_method: Mapped[str] = mapped_column(String(20), default="")   # "ai" | "heuristic"
    error: Mapped[str] = mapped_column(Text, default="")
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    store: Mapped[Store] = relationship(back_populates="flyers")
    offers: Mapped[list[Offer]] = relationship(
        back_populates="flyer", cascade="all, delete-orphan", order_by="Offer.position")


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[int] = mapped_column(primary_key=True)
    flyer_id: Mapped[int] = mapped_column(ForeignKey("flyers.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int] = mapped_column(Integer)                         # 1-based
    name: Mapped[str] = mapped_column(String(300))
    brand: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(String(500), default="")  # formato, peso, varianti
    category: Mapped[str] = mapped_column(String(60), default="altro")
    price_cents: Mapped[int] = mapped_column(Integer)
    old_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price_text: Mapped[str] = mapped_column(String(80), default="")  # es. "€ 4,98 al kg"
    conditions: Mapped[str] = mapped_column(String(300), default="")      # es. "con carta fedeltà"
    # Riquadro del prodotto sulla pagina, normalizzato 0..1 (x0, y0, x1, y1).
    bbox: Mapped[list] = mapped_column(JSON, default=list)
    crop_path: Mapped[str] = mapped_column(String(500), default="")
    # Solo la foto del prodotto (senza prezzi e scritte), per video e grafiche.
    photo_bbox: Mapped[list] = mapped_column(JSON, default=list)
    photo_path: Mapped[str] = mapped_column(String(500), default="")
    manual: Mapped[bool] = mapped_column(Boolean, default=False)       # aggiunta a mano
    price_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[str] = mapped_column(String(40), default="")   # testo PDF | OCR | doppia lettura IA | persona
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)  # costo d'acquisto, se noto
    # «Esaurito»: il prodotto è finito in questo punto vendita (esce dai materiali nuovi)
    sold_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sold_out_note: Mapped[str] = mapped_column(String(120), default="")

    flyer: Mapped[Flyer] = relationship(back_populates="offers")


class ContentPiece(Base):
    """Un contenuto generato (post social, piano della settimana, video, Reel)."""
    __tablename__ = "content_pieces"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    flyer_id: Mapped[int | None] = mapped_column(ForeignKey("flyers.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))     # instagram | facebook | plan | video | clip
    title: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    """Lavoro lungo eseguito in background (es. rendering video)."""
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Rescue(Base):
    """Salvaspreco: un prodotto vicino alla scadenza (o molto maturo, o in confezione rovinata) messo in offerta lampo."""
    __tablename__ = "rescues"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    offer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)     # se scelto dal volantino (solo riferimento)
    day: Mapped[date] = mapped_column(Date, index=True)                       # giorno dell'offerta lampo
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(200), default="")         # formato: "500 g", "al kg"
    reason: Mapped[str] = mapped_column(String(20), default="scadenza")       # scadenza | maturo | forno | confezione | ultimi
    date_kind: Mapped[str] = mapped_column(String(10), default="")            # scadenza | tmc | "" (nessuna data)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    until: Mapped[date | None] = mapped_column(Date, nullable=True)           # ultimo giorno dell'offerta lampo
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit: Mapped[str] = mapped_column(String(12), default="pezzi")            # pezzi | kg
    unit_weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True) # peso di un pezzo, per i kg salvati
    price_cents: Mapped[int] = mapped_column(Integer)                         # prezzo normale
    rescue_price_cents: Mapped[int] = mapped_column(Integer)                  # prezzo salvaspreco
    photo_path: Mapped[str] = mapped_column(String(500), default="")
    story_path: Mapped[str] = mapped_column(String(500), default="")
    post_path: Mapped[str] = mapped_column(String(500), default="")
    text: Mapped[str] = mapped_column(Text, default="")                       # post Instagram/Facebook
    short_text: Mapped[str] = mapped_column(Text, default="")                 # stato WhatsApp
    sold_qty: Mapped[float | None] = mapped_column(Float, nullable=True)      # segnato a fine giornata
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TillCode(Base):
    """Parola alla cassa: la parola d'ordine di un canale (Instagram, Facebook, WhatsApp, Reel) per un volantino."""
    __tablename__ = "till_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    flyer_id: Mapped[int] = mapped_column(ForeignKey("flyers.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    word: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TillHit(Base):
    """Quante volte, in un giorno, un cliente ha detto la parola alla cassa (solo il numero: nessun dato personale)."""
    __tablename__ = "till_hits"
    id: Mapped[int] = mapped_column(primary_key=True)
    code_id: Mapped[int] = mapped_column(ForeignKey("till_codes.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, default=0)


class Producer(Base):
    """Filiera vicina: un produttore del territorio da cui il negozio compra (dati scritti dal negozio)."""
    __tablename__ = "producers"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))                       # «Caseificio Rossi»
    town: Mapped[str] = mapped_column(String(120))                       # comune
    what: Mapped[str] = mapped_column(String(120))                       # «mozzarella e ricotta»
    story: Mapped[str] = mapped_column(String(300), default="")          # una frase vera, facoltativa
    keywords: Mapped[str] = mapped_column(String(200), default="")       # parole per riconoscere i prodotti nel volantino
    photo_path: Mapped[str] = mapped_column(String(500), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    km: Mapped[float | None] = mapped_column(Float, nullable=True)       # in linea d'aria dal negozio
    geo_error: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CounterItem(Base):
    """Banco e allergeni: un prodotto venduto sfuso al banco (gastronomia, forno...) con ingredienti e allergeni."""
    __tablename__ = "counter_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    counter: Mapped[str] = mapped_column(String(30), default="gastronomia")
    name: Mapped[str] = mapped_column(String(160))
    ingredients: Mapped[str] = mapped_column(Text, default="")
    allergens: Mapped[list] = mapped_column(JSON, default=list)          # codici confermati dalla persona
    may_contain: Mapped[list] = mapped_column(JSON, default=list)        # «può contenere tracce di» (dichiarato)
    checked_by: Mapped[str] = mapped_column(String(80), default="")      # chi ha controllato
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notice(Base):
    """Avviso di servizio del punto vendita: orari festivi, chiusure, lavori. Scritto una volta, pronto per ogni canale."""
    __tablename__ = "notices"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="festivo")      # festivo | chiusura | orari | lavori | altro
    title: Mapped[str] = mapped_column(String(120))
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    hours: Mapped[str] = mapped_column(String(80), default="")            # «8:00 – 13:00» oppure vuoto se chiuso
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobPost(Base):
    """Annuncio «Lavora con noi» del punto vendita: dallo stesso annuncio il post, la storia e il cartello con QR."""
    __tablename__ = "job_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(80))
    contract: Mapped[str] = mapped_column(String(30), default="indeterminato")
    hours: Mapped[str] = mapped_column(String(30), default="full-time")
    hours_note: Mapped[str] = mapped_column(String(120), default="")
    tasks: Mapped[str] = mapped_column(String(600), default="")
    requirements: Mapped[str] = mapped_column(String(600), default="")
    offer: Mapped[str] = mapped_column(String(600), default="")
    pay: Mapped[str] = mapped_column(String(120), default="")
    start: Mapped[str] = mapped_column(String(80), default="")
    apply_link: Mapped[str] = mapped_column(String(300), default="")
    apply_email: Mapped[str] = mapped_column(String(160), default="")
    in_store: Mapped[bool] = mapped_column(Boolean, default=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
