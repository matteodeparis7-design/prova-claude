"""Agente "Assistente clienti": risponde 24 ore su 24 e prende ordini da ritirare in negozio.

L'agente non conosce prezzi a memoria: li legge sempre dagli strumenti, che
interrogano il database. Gli ordini vengono validati dal codice, non dall'IA.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...llm import LLM, ToolSpec
from ...models import Conversation, Customer, Offer, Order, OrderItem, OrderStatus, Store
from ...money import format_eur
from ...text_utils import CATEGORIES
from ..catalog import active_offers, search_offers
from ..content.service import validity_text

TZ = ZoneInfo("Europe/Rome")
MAX_ITEMS = 30
MAX_QTY = 50
MAX_HISTORY_MESSAGES = 60
PHONE_RE = re.compile(r"^\+?[0-9 ]{6,20}$")


class OrderError(ValueError):
    pass


def normalize_phone(phone: str) -> str:
    p = (phone or "").strip().replace("-", " ").replace(".", " ")
    if not PHONE_RE.match(p):
        raise OrderError("Numero di telefono non valido.")
    digits = re.sub(r"\D", "", p)
    if p.startswith("+"):
        return "+" + digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    return "+39" + digits if len(digits) <= 11 else "+" + digits


def offer_view(o: Offer) -> dict:
    return {
        "id": o.id, "nome": o.name, "marca": o.brand, "formato": o.description, "categoria": o.category,
        "prezzo": format_eur(o.price_cents),
        "prezzo_precedente": format_eur(o.old_price_cents) if o.old_price_cents else "",
        "sconto": f"-{o.discount_percent}%" if o.discount_percent else "",
        "condizioni": o.conditions, "validita": validity_text(o.flyer),
    }


def create_pickup_order(session: Session, store: Store, *, name: str, phone: str, items: list[dict],
                        pickup_iso: str, notes: str = "", now: datetime | None = None) -> Order:
    """Crea un ordine con tutte le verifiche. Solleva OrderError con un messaggio chiaro."""
    if not store.pickup_enabled:
        raise OrderError("Questo negozio non accetta ordini da ritirare.")
    name = " ".join((name or "").split())
    if len(name) < 2:
        raise OrderError("Serve il nome del cliente.")
    phone_n = normalize_phone(phone)
    if not items:
        raise OrderError("L'ordine è vuoto.")
    if len(items) > MAX_ITEMS:
        raise OrderError(f"Massimo {MAX_ITEMS} articoli per ordine.")
    now = now or datetime.now(timezone.utc)
    try:
        pickup = datetime.fromisoformat(pickup_iso)
    except (TypeError, ValueError) as exc:
        raise OrderError("Orario di ritiro non valido: usa il formato AAAA-MM-GGTHH:MM.") from exc
    if pickup.tzinfo is None:
        pickup = pickup.replace(tzinfo=TZ)
    if pickup < now + timedelta(hours=1):
        raise OrderError("Il ritiro deve essere almeno tra un'ora.")
    if pickup > now + timedelta(days=7):
        raise OrderError("Il ritiro può essere al massimo tra 7 giorni.")

    valid = {o.id: o for o in active_offers(session, store.id, pickup.astimezone(TZ).date())}
    merged: dict[int, int] = {}
    for it in items:
        try:
            oid, qty = int(it["offerta_id"]), int(it["quantita"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OrderError("Ogni articolo deve avere offerta_id e quantita.") from exc
        if oid not in valid:
            raise OrderError(f"L'offerta {oid} non esiste o non è valida nel giorno del ritiro.")
        if not 1 <= qty <= MAX_QTY:
            raise OrderError(f"Quantità non valida per l'offerta {oid} (da 1 a {MAX_QTY}).")
        merged[oid] = merged.get(oid, 0) + qty
        if merged[oid] > MAX_QTY:
            raise OrderError(f"Quantità totale troppo alta per l'offerta {oid}.")

    customer = session.scalar(select(Customer).where(Customer.store_id == store.id, Customer.phone == phone_n))
    if customer is None:
        customer = Customer(store_id=store.id, name=name, phone=phone_n)
        session.add(customer)
        session.flush()
    order = Order(store_id=store.id, customer_id=customer.id, customer_name=name, customer_phone=phone_n,
                  pickup_at=pickup.astimezone(timezone.utc), notes=(notes or "")[:1000], status=OrderStatus.new)
    total = 0
    for oid, qty in merged.items():
        o = valid[oid]
        order.items.append(OrderItem(offer_id=oid, name=o.name, quantity=qty, unit_price_cents=o.price_cents))
        total += qty * o.price_cents
    order.total_cents = total
    session.add(order)
    session.flush()
    return order


def _hours_text(store: Store) -> str:
    if not store.opening_hours:
        return "non indicati"
    return "; ".join(f"{k}: {v}" for k, v in store.opening_hours.items())


def build_tools(session: Session, store: Store, now: datetime) -> list[ToolSpec]:
    today = now.astimezone(TZ).date()

    def cerca_offerte(args: dict) -> dict:
        offers = active_offers(session, store.id, today)
        cat = args.get("categoria", "")
        if cat and cat not in CATEGORIES:
            cat = ""
        found = search_offers(offers, args.get("testo", ""), cat)
        return {"offerte": [offer_view(o) for o in found], "totale_offerte_attive": len(offers)}

    def info_negozio(_: dict) -> dict:
        return {"nome": store.name, "insegna": store.banner, "indirizzo": store.address, "citta": store.city,
                "telefono": store.phone, "orari": _hours_text(store), "servizi": store.services,
                "ritiro_in_negozio": store.pickup_enabled}

    def crea_ordine_ritiro(args: dict) -> dict:
        order = create_pickup_order(
            session, store, name=args["nome"], phone=args["telefono"], items=args["articoli"],
            pickup_iso=args["ritiro"], notes=args.get("note", ""), now=now)
        return {"ordine_id": order.id, "totale": format_eur(order.total_cents),
                "ritiro": order.pickup_at.astimezone(TZ).strftime("%d/%m/%Y %H:%M") if order.pickup_at else "",
                "articoli": [{"nome": i.name, "quantita": i.quantity,
                              "prezzo": format_eur(i.unit_price_cents)} for i in order.items]}

    def stato_ordine(args: dict) -> dict:
        order = session.get(Order, int(args["ordine_id"]))
        try:
            phone = normalize_phone(args["telefono"])
        except OrderError:
            phone = ""
        if order is None or order.store_id != store.id or order.customer_phone != phone:
            raise OrderError("Ordine non trovato per questo numero di telefono.")
        return {"ordine_id": order.id, "stato": order.status.value, "totale": format_eur(order.total_cents)}

    obj = {"type": "object", "additionalProperties": False}
    return [
        ToolSpec("cerca_offerte",
                 "Cerca tra le offerte attive del volantino del negozio. Usalo SEMPRE prima di citare un prezzo. "
                 "testo vuoto = offerte in evidenza.",
                 {**obj, "properties": {
                     "testo": {"type": "string", "description": "Prodotto cercato, es. 'pollo'. Può essere vuoto."},
                     "categoria": {"type": "string", "enum": [""] + CATEGORIES,
                                   "description": "Categoria, oppure stringa vuota."}},
                  "required": ["testo", "categoria"]},
                 cerca_offerte),
        ToolSpec("info_negozio", "Indirizzo, orari, telefono e servizi del negozio.",
                 {**obj, "properties": {}, "required": []}, info_negozio),
        ToolSpec("crea_ordine_ritiro",
                 "Crea un ordine da ritirare in negozio. Usalo SOLO dopo che il cliente ha confermato "
                 "esplicitamente articoli, quantità, nome, telefono e orario.",
                 {**obj, "properties": {
                     "nome": {"type": "string"},
                     "telefono": {"type": "string"},
                     "articoli": {"type": "array", "items": {
                         **obj, "properties": {"offerta_id": {"type": "integer"}, "quantita": {"type": "integer"}},
                         "required": ["offerta_id", "quantita"]}},
                     "ritiro": {"type": "string", "description": "Data e ora locali, formato AAAA-MM-GGTHH:MM"},
                     "note": {"type": "string"}},
                  "required": ["nome", "telefono", "articoli", "ritiro", "note"]},
                 crea_ordine_ritiro),
        ToolSpec("stato_ordine", "Stato di un ordine, verificando il telefono del cliente.",
                 {**obj, "properties": {"ordine_id": {"type": "integer"}, "telefono": {"type": "string"}},
                  "required": ["ordine_id", "telefono"]},
                 stato_ordine),
    ]


def system_prompt(store: Store, now: datetime) -> str:
    local = now.astimezone(TZ)
    return (
        f"Sei l'assistente virtuale di {store.name}"
        f"{' (' + store.banner + ')' if store.banner else ''}, un supermercato a {store.city or 'n.d.'}. "
        f"Oggi è {local.strftime('%d/%m/%Y')}, ore {local.strftime('%H:%M')}.\n"
        "Rispondi in italiano, in modo breve, gentile e concreto (adatto a WhatsApp).\n"
        "Regole:\n"
        "- Prezzi, offerte e disponibilità li ricavi SOLO dagli strumenti; se un prodotto non è in offerta, "
        "dillo senza inventare prezzi.\n"
        "- Per un ordine: riepiloga articoli, quantità, totale, nome, telefono e orario di ritiro e chiedi "
        "conferma; crea l'ordine solo dopo un sì esplicito.\n"
        "- Non chiedere dati che non servono. Non dare consigli medici o legali.\n"
        "- Se non sai rispondere, suggerisci di chiamare il negozio."
    )


def _trim_history(history: list[dict]) -> list[dict]:
    """Tiene la cronologia entro un limite, tagliando solo all'inizio di un turno dell'utente."""
    if len(history) <= MAX_HISTORY_MESSAGES:
        return history
    cut = len(history) - MAX_HISTORY_MESSAGES
    while cut < len(history):
        m = history[cut]
        if m["role"] == "user" and isinstance(m["content"], str):
            return history[cut:]
        cut += 1
    return history[-1:]


def chat(session: Session, store: Store, llm: LLM, message: str, conversation: Conversation | None = None,
         channel: str = "web", customer_phone: str = "", now: datetime | None = None) -> tuple[str, Conversation]:
    message = (message or "").strip()
    if not message:
        raise ValueError("Messaggio vuoto.")
    if len(message) > 4000:
        raise ValueError("Messaggio troppo lungo.")
    now = now or datetime.now(timezone.utc)
    if conversation is None:
        conversation = Conversation(store_id=store.id, channel=channel, customer_phone=customer_phone, history=[])
        session.add(conversation)
        session.flush()
    history = _trim_history(list(conversation.history) + [{"role": "user", "content": message}])
    result = llm.run_tools(system=system_prompt(store, now), messages=history,
                           tools=build_tools(session, store, now), effort="low")
    reply = result.text or "Mi scusi, non sono riuscito a rispondere. Può chiamare il negozio?"
    conversation.history = result.messages
    conversation.updated_at = now
    session.flush()
    return reply, conversation
