"""Modello dei dati.

Struttura multi-negozio pensata per due modalità:
- agenzia: un'organizzazione (la tua) gestisce molti punti vendita;
- SaaS: ogni cliente ha la sua organizzazione con i suoi punti vendita.

Tutti gli importi sono in centesimi di euro (interi) per evitare errori di arrotondamento.
"""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, JSON,
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


class OrderStatus(str, enum.Enum):
    new = "new"
    confirmed = "confirmed"
    ready = "ready"
    collected = "collected"
    cancelled = "cancelled"


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
    services: Mapped[list] = mapped_column(JSON, default=list)       # es. ["ritiro in negozio", "consegna"]
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="stores")
    flyers: Mapped[list[Flyer]] = relationship(back_populates="store", cascade="all, delete-orphan")
    customers: Mapped[list[Customer]] = relationship(back_populates="store", cascade="all, delete-orphan")


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

    flyer: Mapped[Flyer] = relationship(back_populates="offers")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("store_id", "phone", name="uq_customer_store_phone"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(255), default="")
    # Consenso esplicito (GDPR) a ricevere comunicazioni promozionali.
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferred_categories: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    store: Mapped[Store] = relationship(back_populates="customers")
    orders: Mapped[list[Order]] = relationship(back_populates="customer")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="web")   # web | whatsapp | phone
    customer_phone: Mapped[str] = mapped_column(String(40), default="")
    # Cronologia nel formato dell'API Messages (solo testo e blocchi strumento serializzati).
    history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_phone: Mapped[str] = mapped_column(String(40))
    pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.new)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    customer: Mapped[Customer | None] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_cents: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")


class SaleRecord(Base):
    """Una riga di vendite importata dalla cassa (giorno x prodotto)."""
    __tablename__ = "sale_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    product: Mapped[str] = mapped_column(String(300))
    sku: Mapped[str] = mapped_column(String(60), default="")
    quantity: Mapped[float] = mapped_column(Float)
    revenue_cents: Mapped[int] = mapped_column(Integer)


class ContentPiece(Base):
    """Un contenuto generato (post social, messaggio WhatsApp, newsletter, video)."""
    __tablename__ = "content_pieces"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    flyer_id: Mapped[int | None] = mapped_column(ForeignKey("flyers.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))     # instagram | facebook | whatsapp | newsletter | video
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
