"""Dal banco al Reel: dal video girato col telefono al Reel pubblicabile.

Regole che non si toccano:
- i prezzi vengono solo dal volantino (già controllato); l'IA non scrive mai un prezzo suo;
- un cartellino compare solo nei tratti dove si vede quel prodotto (riconosciuto dall'IA o indicato
  dal negoziante); dove non si sa cosa c'è, nessun prezzo;
- nessuna frase inventata sui prodotti ("pescato stamattina", "a km zero"...): quello lo può dire
  solo il negoziante nella nota, e allora si usa la sua frase;
- la voce sintetica è sempre dichiarata nel video.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import Settings
from ...llm import AIRefused, AIUnavailable, LLM, image_block
from ...models import ContentPiece, Flyer, FlyerStatus, Offer, Store
from ...money import find_prices, format_eur
from ... import voice as voicemod
from ..content.service import AI_TELLS, ai_tells, product_name, validity_text
from ..video.service import store_contacts
from ..video.render import VideoSpec
from .analyze import Analysis, analyze, grab_frame, pick_in_main_scene, pick_segments
from .render import (ClipSpec, ClipText, ProductCard, caption_chunks, clean_voice, plan_length, poster,
                     render_clip)

log = logging.getLogger("promovo.clip")

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".3gp", ".mkv", ".avi"}
AUDIO_EXT = {".webm", ".ogg", ".oga", ".mp3", ".m4a", ".wav", ".aac", ".opus", ".mp4", ".3gp", ".amr"}
VOICE_MODES = ("none", "recorded", "ai")

# Reparti: un'apertura vera e neutra, che non promette nulla sul prodotto.
REPARTO = {"pesce": "Al banco del pesce", "carne": "Dalla nostra macelleria", "frutta e verdura": "Dal reparto ortofrutta",
           "salumi e formaggi": "Dal banco gastronomia", "pane e forno": "Dal nostro forno",
           "latte e latticini": "Dal reparto freschi", "surgelati": "Dal reparto surgelati",
           "vino e alcolici": "Dalla nostra cantina"}

# Affermazioni che solo il negoziante può fare: l'IA non le scrive mai di sua iniziativa.
UNVERIFIABLE = ["pescat", "stamattina", "di giornata", "appena arrivat", "km zero", "chilometro zero", "nostrano",
                "nostrana", "biologic", "artigianal", "fatto in casa", "fatta in casa", "locale", "del territorio"]


class ClipFailed(RuntimeError):
    pass


# ------------------------------------------------------------------ prodotti del volantino

def current_flyer(session: Session, store: Store, today: date | None = None) -> Flyer | None:
    """Il volantino in corso (o, se nessuno è in corso, l'ultimo pronto)."""
    today = today or date.today()
    rows = session.scalars(select(Flyer).where(Flyer.store_id == store.id, Flyer.status == FlyerStatus.ready,
                                              Flyer.competitor == "")
                           .order_by(Flyer.created_at.desc(), Flyer.id.desc())).all()
    rows = [f for f in rows if f.offers]
    for f in rows:
        if (f.valid_from is None or f.valid_from <= today) and (f.valid_to is None or f.valid_to >= today):
            return f
    return rows[0] if rows else None


def to_card(o: Offer) -> ProductCard:
    return ProductCard(product=o.name, price_cents=o.price_cents, brand=o.brand, description=o.description,
                       unit_text=o.unit_price_text, conditions=o.conditions)


def said_name(o: Offer) -> str:
    """Nome del prodotto dentro una frase: "spigola", ma "Peroni Birra" resta com'è."""
    n = product_name(o, False)
    return n if o.brand else n[:1].lower() + n[1:]


# ------------------------------------------------------------------ testi

class AIClipFrame(BaseModel):
    numero: int = Field(description="Numero del fotogramma, come indicato")
    visto: str = Field(description="Cosa si vede, in poche parole")
    offerta: int | None = Field(description="Numero dell'offerta che si vede chiaramente, altrimenti null")
    frase: str = Field(default="", description="Sottotitolo per questo tratto, max 32 caratteri, senza prezzi")


class AIClip(BaseModel):
    fotogrammi: list[AIClipFrame]
    titolo: str = Field(description="Titolo d'apertura, massimo 38 caratteri")
    voce: str = Field(description="Testo per voce fuori campo e sottotitoli, 15-35 parole")


_CLIP_SYSTEM = f"""\
Sei il montatore e copywriter di Promovo per i supermercati di quartiere italiani.
Ricevi alcuni fotogrammi numerati di un video girato col telefono in negozio, l'elenco numerato delle
offerte del volantino in corso e, se c'è, una nota scritta dal negoziante.

1. Per ogni fotogramma scrivi cosa si vede. Se si vede CHIARAMENTE un prodotto che corrisponde a
   un'offerta dell'elenco, indica il numero dell'offerta. Se non sei sicuro, o il prodotto non è
   nell'elenco, metti null. Non indovinare: un prezzo sul prodotto sbagliato è un danno per il negozio.
2. Scrivi un titolo d'apertura (massimo 38 caratteri): concreto, senza punto esclamativo.
3. Per ogni fotogramma scrivi anche una "frase" da sottotitolo (massimo 32 caratteri, senza prezzi:
   il prezzo lo mostra già il cartellino). Descrive solo ciò che si vede davvero.
4. Scrivi il testo per la voce fuori campo (15-35 parole), che diventa i sottotitoli quando c'è la voce.
   Parla il negozio, in prima persona plurale ("da noi", "ti aspettiamo"), nel tono indicato.
   Puoi citare i prodotti riconosciuti e il loro prezzo, scritto esattamente come nell'elenco
   (es. "€ 12,99 al kg"), e la data di fine offerta.

REGOLE TASSATIVE
- Nessun prezzo che non sia nell'elenco. Nessuno sconto inventato.
- Non dire mai che un prodotto è pescato oggi, arrivato stamattina, di giornata, a km zero, nostrano,
  biologico, artigianale o locale, a meno che lo dica la nota del negoziante: in quel caso usa le sue parole.
- Niente frasi fatte da pubblicità: {", ".join(t for t in AI_TELLS[:24])}.
- Frasi brevi, italiano parlato, nessuna emoji, nessun hashtag.
"""


@dataclass
class ClipPlan:
    cards: list[ProductCard | None]
    offers: list[Offer | None]
    lines: list[str]        # un sottotitolo per tratto (usato quando non c'è la voce)
    hook: str
    script: str
    source: str            # "ai" | "template"
    warnings: list[str]


def _validity_short(flyer: Flyer | None) -> str:
    if flyer is None or not flyer.valid_to:
        return ""
    from ..content.service import fmt_date
    return f"fino al {fmt_date(flyer.valid_to)}"


def template_script(store: Store, offers: list[Offer], flyer: Flyer | None, note: str = "") -> tuple[str, str]:
    """Titolo e testo senza IA: solo fatti veri (prodotti, prezzi, date, la nota del negoziante)."""
    uniq: list[Offer] = []
    for o in offers:
        if o is not None and o not in uniq:
            uniq.append(o)
    cat = uniq[0].category if uniq else ""
    note = note.strip().rstrip(".")
    # Il titolo segue le parole del negoziante; altrimenti il reparto, altrimenti il negozio.
    if note and len(note) <= 38:
        hook = note[:1].upper() + note[1:]
    else:
        hook = REPARTO.get(cat, f"Da {store.name}")[:38]
    parts = []
    if note:
        parts.append(note[:1].upper() + note[1:] + ".")
    if uniq:
        items = [f"{said_name(o)} a {format_eur(o.price_cents)}"
                 + (f" {o.unit_price_text}" if o.unit_price_text and o.unit_price_text.startswith("al") else "")
                 for o in uniq[:3]]
        lead = "Questa settimana da noi " if not note else "Da noi "
        parts.append(lead + (", ".join(items[:-1]) + " e " + items[-1] if len(items) > 1 else items[0]) + ".")
    until = _validity_short(flyer)
    where = f"Ti aspettiamo{(' in ' + store.address) if store.address else ''}"
    parts.append(f"Offerte valide {until}. {where}." if until else f"{where}.")
    return hook, " ".join(parts)


def template_lines(store: Store, flyer: Flyer | None, seg_offers: list[Offer | None], note: str = "") -> list[str]:
    """Sottotitoli per tratto senza IA: la nota del negoziante all'inizio, l'invito alla fine."""
    n = len(seg_offers)
    lines = [""] * n
    if n == 0:
        return lines
    note = note.strip().rstrip(".")
    if note:
        lines[0] = note[:1].upper() + note[1:]
    until = _validity_short(flyer)
    last = f"Ti aspettiamo {until}" if until and any(seg_offers) else f"Ti aspettiamo da {store.name}"
    if n == 1 and lines[0]:
        lines[0] = lines[0] + ". " + last
    else:
        lines[-1] = last
    return lines


def _clean(text: str) -> str:
    text = re.sub(r"[#*_]+", "", text or "")
    text = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def plan_texts(store: Store, flyer: Flyer | None, analysis: Analysis, video: Path, llm: LLM | None,
               chosen: Offer | None, note: str = "") -> ClipPlan:
    """Decide cosa c'è in ogni tratto e scrive titolo e testo."""
    segs = analysis.segments
    warnings: list[str] = []
    offers = list(flyer.offers) if flyer is not None else []
    if chosen is not None:                      # il negoziante ha detto cosa c'è: vale per tutto il video
        seg_offers: list[Offer | None] = [chosen] * len(segs)
    else:
        seg_offers = [None] * len(segs)
    source = "template"
    hook, script = template_script(store, [o for o in seg_offers if o], flyer, note)
    ai_lines: list[str] = []
    if llm is not None:
        try:
            content: list[dict] = []
            for i, s in enumerate(segs, start=1):
                content.append({"type": "text", "text": f"Fotogramma {i}:"})
                content.append(image_block(grab_frame(video, s.best_time), "image/jpeg"))
            listing = "\n".join(f"{k}. {product_name(o)} – {format_eur(o.price_cents)}"
                                f"{(' ' + o.unit_price_text) if o.unit_price_text else ''} [{o.category}]"
                                for k, o in enumerate(offers, start=1)) or "(nessuna offerta disponibile)"
            content.append({"type": "text", "text":
                            f"Negozio: {store.name}, {store.city or ''}. Tono: {store.tone or 'familiare'}.\n"
                            f"Offerte valide: {validity_text(flyer) if flyer else 'nessun volantino'}.\n"
                            f"Offerte del volantino:\n{listing}\n\n"
                            f"Nota del negoziante: {note.strip() or '(nessuna)'}\n"
                            + (f"Il negoziante ha indicato che il video mostra: {product_name(chosen)}.\n"
                               if chosen is not None else "")})
            res = llm.parse(system=_CLIP_SYSTEM, content=content, schema=AIClip, effort="medium", max_tokens=3000)
            if chosen is None:
                by_num = {f.numero: f.offerta for f in res.fotogrammi}
                for i in range(len(segs)):
                    k = by_num.get(i + 1)
                    seg_offers[i] = offers[k - 1] if isinstance(k, int) and 1 <= k <= len(offers) else None
            ai_hook, ai_script = _clean(res.titolo)[:60], _clean(res.voce)
            by_line = {f.numero: _clean(f.frase)[:40] for f in res.fotogrammi}
            ai_lines = [by_line.get(i + 1, "") for i in range(len(segs))]
            allowed = {o.price_cents for o in seg_offers if o is not None}
            low = (note or "").lower()
            every = " ".join([ai_script, ai_hook, *ai_lines]).lower()
            invented = [w for w in UNVERIFIABLE if w in every and w not in low]
            if any(find_prices(x) for x in ai_lines) or ai_tells("\n".join(ai_lines)):
                ai_lines = []
            if not ai_script or not all(p in allowed for p in find_prices(ai_hook + " " + ai_script)):
                warnings.append("Il testo dell'IA citava un prezzo non presente: usato il testo standard.")
            elif invented:
                warnings.append(f"Il testo dell'IA diceva «{invented[0]}…», che non possiamo sapere: "
                                "usato il testo standard. Scrivilo nella nota, se è vero.")
            elif ai_tells(ai_hook + "\n" + ai_script):
                warnings.append("Il testo dell'IA conteneva frasi fatte: usato il testo standard.")
            else:
                hook, script, source = ai_hook[:38].rstrip(" ,.;:!"), ai_script, "ai"
            if source != "ai":
                hook, script = template_script(store, [o for o in seg_offers if o], flyer, note)
        except (AIUnavailable, AIRefused) as exc:
            warnings.append(f"IA non disponibile: {exc}")
    if not any(seg_offers) and offers:
        warnings.append("Nessun prodotto del volantino riconosciuto: il video non mostra prezzi. "
                        "Puoi indicare tu il prodotto e rifarlo.")
    cards: list[ProductCard | None] = []
    made: dict[int, ProductCard] = {}
    for o in seg_offers:
        if o is None:
            cards.append(None)
        else:
            made.setdefault(o.id, to_card(o))
            cards.append(made[o.id])
    if source != "ai" or len(ai_lines) != len(segs):
        ai_lines = template_lines(store, flyer, seg_offers, note)
    return ClipPlan(cards=cards, offers=seg_offers, lines=ai_lines, hook=hook, script=script, source=source,
                    warnings=warnings)


def outro_spec(store: Store, flyer: Flyer | None) -> VideoSpec:
    contacts, qr, qr_label = store_contacts(store)
    return VideoSpec(store_name=store.name, headline="", validity=validity_text(flyer) if flyer else "",
                     address=", ".join(x for x in (store.address, store.city) if x), offers=[],
                     brand_color=store.brand_color, accent_color=store.accent_color, format="portrait", fps=30,
                     logo_path=store.logo_path or None, contact_lines=contacts, qr_data=qr, qr_label=qr_label)


def post_caption(store: Store, flyer: Flyer | None, plan: ClipPlan) -> str:
    """Didascalia da incollare sotto il Reel: il testo detto nel video più dove e fino a quando."""
    lines = [plan.script]
    seen = []
    for o in plan.offers:
        if o is not None and o not in seen:
            seen.append(o)
            lines.append(f"{product_name(o)}: {format_eur(o.price_cents)}"
                         + (f" {o.unit_price_text}" if o.unit_price_text else ""))
    where = ", ".join(x for x in (store.address, store.city) if x)
    if where:
        lines.append(f"{store.name}, {where}")
    tags = " ".join("#" + t for t in (store.hashtags or [])[:5])
    return "\n".join(lines) + (f"\n\n{tags}" if tags else "")


# ------------------------------------------------------------------ Reel

def make_reel(session: Session, store: Store, settings: Settings, llm: LLM | None, video: Path,
              offer_id: int | None = None, note: str = "", voice_mode: str = "none",
              voice_file: Path | None = None, today: date | None = None,
              voice_client=None, spoken_script: str = "") -> ContentPiece:
    """Crea il Reel e lo salva tra i contenuti del negozio (da approvare)."""
    if voice_mode not in VOICE_MODES:
        raise ClipFailed("Modalità della voce non valida.")
    chosen = None
    flyer = current_flyer(session, store, today)
    if offer_id is not None:
        chosen = session.get(Offer, offer_id)
        if chosen is None or chosen.flyer.store_id != store.id:
            raise ClipFailed("Prodotto non trovato tra le offerte di questo negozio.")
        flyer = chosen.flyer
    analysis = analyze(video)
    trimmed = False
    if chosen is not None:
        # Prodotto indicato a mano: si usa solo l'inquadratura principale, così il cartellino
        # non finisce sopra un altro prodotto inquadrato di passaggio.
        analysis.segments, trimmed = pick_in_main_scene(analysis.times, analysis.score, analysis.cuts, 11.0)
    plan = plan_texts(store, flyer, analysis, video, llm, chosen, note)
    settings.ensure_dirs()
    work = settings.data_dir / "clips"
    voice_path: Path | None = None
    voice_is_ai = False
    if voice_mode == "recorded":
        if voice_file is None or not voice_file.exists():
            raise ClipFailed("Manca la registrazione della voce.")
        voice_path = voice_file
    elif voice_mode == "ai":
        key = voicemod.api_key()
        if not store.voice_id or not store.voice_consent_at:
            raise ClipFailed("Prima crea la voce del negozio (Negozio → Voce), con il consenso.")
        if not key:
            raise ClipFailed("Per la voce generata serve la chiave ElevenLabs (file CHIAVE_VOCE.txt).")
        voice_path = voicemod.synthesize(voicemod.to_spoken(plan.script), store.voice_id,
                                         work / f"tts_{uuid.uuid4().hex}.mp3", key, client=voice_client)
        voice_is_ai = True
    # Con la voce il video dura quanto serve per dirla: si rifà la scelta dei tratti su quella durata.
    if voice_path is not None:
        tmp_wav = work / f"voice_{uuid.uuid4().hex}.wav"
        try:
            vlen = clean_voice(voice_path, tmp_wav)
        finally:
            tmp_wav.unlink(missing_ok=True)
        target = plan_length(analysis.segments, vlen)
        if chosen is not None:
            new, _ = pick_in_main_scene(analysis.times, analysis.score, analysis.cuts, target, max_segments=4)
        else:
            new = pick_segments(analysis.times, analysis.score, analysis.cuts, target, max_segments=4)
        if new and [(s.start, s.end) for s in new] != [(s.start, s.end) for s in analysis.segments]:
            analysis.segments = new
            plan = plan_texts(store, flyer, analysis, video, llm, chosen, note)
    if voice_mode == "recorded" and spoken_script.strip():
        # Voce vera del negoziante: i sottotitoli riportano esattamente quello che ha letto.
        plan.script = _clean(spoken_script)[:500]
    if trimmed:
        plan.warnings.append("Il video inquadrava più cose: ho tenuto solo la parte principale, dove c'è "
                             f"«{chosen.name}». Per mostrare più prodotti, carica un video per prodotto "
                             "oppure lascia che li riconosca l'IA.")
    text = ClipText(hook=plan.hook, captions=caption_chunks(plan.script) if voice_path is not None else [],
                    segment_lines=plan.lines,
                    validity=validity_text(flyer) if flyer is not None and any(plan.offers) else "", cards=plan.cards)
    spec = ClipSpec(source=video, info=analysis.info, segments=analysis.segments, store_name=store.name, text=text,
                    brand_color=store.brand_color, accent_color=store.accent_color, logo_path=store.logo_path or None,
                    outro=outro_spec(store, flyer), voice_path=voice_path, voice_is_ai=voice_is_ai,
                    music=bool(store.video_music))
    name = f"clip_{uuid.uuid4().hex[:12]}"
    out = settings.data_dir / "renders" / f"{name}.mp4"
    _, duration = render_clip(spec, out)
    post = poster(out, min(2.2, duration / 3), out.with_suffix(".jpg"))
    if voice_is_ai and voice_path is not None:
        voice_path.unlink(missing_ok=True)
    names = []
    for o in plan.offers:
        if o is not None and o.name not in names:
            names.append(o.name)
    piece = ContentPiece(store_id=store.id, flyer_id=flyer.id if flyer is not None and any(plan.offers) else None,
                         kind="video", title=("Reel dal banco: " + ", ".join(names[:3])) if names else "Reel dal banco",
                         body=post_caption(store, flyer, plan), file_path=str(out),
                         meta={"format": "clip", "duration": round(duration, 2), "music": spec.music,
                               "poster": str(post) if post else "", "source": plan.source, "hook": plan.hook,
                               "script": plan.script, "voice": voice_mode, "ai_voice": voice_is_ai,
                               "offers": [o.id if o else None for o in plan.offers],
                               "segments": [[round(s.start, 2), round(s.end, 2)] for s in analysis.segments],
                               "warnings": plan.warnings, "source_video": str(video)})
    session.add(piece)
    session.flush()
    return piece


def delete_clip_files(piece: ContentPiece) -> None:
    for p in (piece.file_path, (piece.meta or {}).get("poster"), (piece.meta or {}).get("source_video")):
        if p:
            Path(p).unlink(missing_ok=True)


def script_for(session: Session, store: Store, offer_id: int | None, note: str, llm: LLM | None = None) -> dict:
    """Testo da leggere per chi registra la propria voce (prima di girare o caricare il video)."""
    chosen = session.get(Offer, offer_id) if offer_id else None
    if chosen is not None and chosen.flyer.store_id != store.id:
        chosen = None
    flyer = chosen.flyer if chosen is not None else current_flyer(session, store)
    hook, script = template_script(store, [chosen] if chosen else [], flyer, note)
    return {"hook": hook, "script": script, "chunks": caption_chunks(script),
            "seconds": round(len(script.split()) / 2.6, 1)}
