"""«Lavora con noi»: l'annuncio di lavoro del punto vendita, pronto per ogni canale e scritto nel rispetto delle regole.

Molti negozi cercano personale con un foglio scritto a mano sulla porta o un post improvvisato, e spesso con parole
che la legge non permette («ragazza max 30 anni», «bella presenza»). Promovo prepara dallo stesso annuncio:
- il testo completo per i portali di lavoro e il sito;
- il post e la storia per i social, nello stile del negozio;
- il messaggio per lo stato WhatsApp;
- il cartello A4 per la porta e la cassa, con il QR per candidarsi;
- la schermata per gli schermi del negozio.

Prima di salvare, il controllo dell'annuncio blocca le richieste discriminatorie (età, genere, stato civile, figli,
nazionalità, religione, opinioni, aspetto: D.Lgs. 198/2006, D.Lgs. 215/2003 e 216/2003, D.Lgs. 276/2003 art. 10)
e segnala quello che conviene rivedere (foto nel curriculum, «madrelingua», patente). Il titolo è sempre rivolto a
tutti i generi e il testo chiude con la nota sul trattamento dei dati dei candidati (art. 13 GDPR).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

from ..models import JobPost, Store
from .video.render import (INK, WHITE, brand_background, fit_text, font, hex_rgb, logo_image, pill, qr_image,
                           readable_on_paper, text_layer, text_on)

CONTRACTS = {"indeterminato": "tempo indeterminato", "determinato": "tempo determinato",
             "apprendistato": "apprendistato", "stagionale": "contratto stagionale", "tirocinio": "tirocinio"}
HOURS = {"full-time": "tempo pieno", "part-time": "part-time"}

LEGAL_NOTE = ("L'annuncio è aperto a candidate e candidati di ogni genere, età e provenienza "
              "(D.Lgs. 198/2006; D.Lgs. 215/2003 e 216/2003).")
PRIVACY_NOTE = ("I dati dei candidati sono trattati solo per questa selezione (art. 13 Regolamento UE 2016/679): "
                "l'informativa completa al primo contatto.")


class JobError(ValueError):
    pass


# ----------------------------------------------------------------- il controllo dell'annuncio

# (espressione, livello, spiegazione). «err» blocca il salvataggio, «warn» chiede di pensarci.
RULES: list[tuple[str, str, str]] = [
    (r"\b(max|massimo|massima|non oltre|entro i)\s*\d{2}\s*anni\b|\b(under|over)\s*\d{2}\b", "err",
     "Non si può chiedere un'età: togli il limite di anni."),
    (r"\b\d{2}\s*[-–]\s*\d{2}\s*anni\b|\bet[àa]\s*(massima|minima|compresa|tra|non superiore|inferiore)\b|\betà\b", "err",
     "Non si può chiedere un'età: togli la fascia di età."),
    (r"\bgiovan[ei]\b|\bgiovanissim", "err",
     "«Giovane» esclude per età: scrivi cosa serve davvero (per esempio «voglia di imparare»)."),
    (r"\b(ragazz[aeio]|uom[oi]ni|uomo|donn[ae]|signor[ae]|signorina|signorine)\b", "err",
     "L'annuncio deve essere rivolto a tutti i generi: scrivi «persona» o il ruolo (per esempio «addetto/a»)."),
    (r"\bdi sesso\b|\bsesso (maschile|femminile)\b|\bmaschil[ei]\b|\bfemminil[ei]\b", "err",
     "Non si può scegliere il genere dei candidati."),
    (r"\bbella presenza\b|\bpresenza gradevole\b|\bfisico\b|\balta\b|\balto\b|\bstatura\b|\bpeso\b", "err",
     "Non si può chiedere l'aspetto fisico: scrivi invece «cura e cortesia con i clienti»."),
    (r"\bnubil[ei]\b|\bcelib[ei]\b|\bsposat[oaie]\b|\bsenza figli\b|\bfigli\b|\bgravidanz|\bincinta\b|\bstato civile\b",
     "err", "Non si possono chiedere stato civile, figli o gravidanza."),
    (r"\bnazionalit[àa]\b|\bcittadinanza\b|\b(solo|soltanto|esclusivamente|persone|candidat[ie]|cittadini)\s+"
     r"italian|\bstranier|\bextracomunitar|\bresident[ei] (a|in|nel)\b",
     "err", "Non si può scegliere per nazionalità o origine: se serve, chiedi «buona conoscenza dell'italiano»."),
    (r"\breligion|\bcattolic|\bmusulman|\bpolitic|\bsindacat|\borientamento sessuale\b", "err",
     "Non si possono chiedere religione, opinioni politiche o sindacali, orientamento."),
    (r"\bmilitesente\b", "err", "«Militesente» non si usa più ed esclude per genere: toglilo."),
    (r"\bsana e robusta costituzione\b", "warn",
     "Meglio togliere «sana e robusta costituzione»: l'idoneità la valuta il medico competente."),
    (r"\bfoto\b|\bfotografia\b", "warn",
     "Chiedere la foto nel curriculum può portare a scelte per aspetto: meglio non chiederla."),
    (r"\bmadrelingua\b", "warn",
     "«Madrelingua» esclude chi l'ha imparata dopo: meglio «ottima conoscenza dell'italiano»."),
    (r"\bautomunit|\bpatente\b", "warn",
     "Chiedi auto o patente solo se servono davvero per il lavoro (per esempio per le consegne)."),
    (r"\bneolaureat|\bneodiplomat|\bprima esperienza\b", "warn",
     "«Neodiplomato» o «prima esperienza» possono escludere per età: valuta «anche senza esperienza»."),
]


@dataclass
class Issue:
    level: str          # err | warn | info
    field: str
    found: str
    message: str


@dataclass
class JobIn:
    role: str
    contract: str = "indeterminato"
    hours: str = "full-time"
    hours_note: str = ""
    tasks: str = ""
    requirements: str = ""
    offer: str = ""
    pay: str = ""
    start: str = ""
    apply_link: str = ""
    apply_email: str = ""
    in_store: bool = True
    issues: list[Issue] = field(default_factory=list)


FIELDS = {"role": "ruolo", "hours_note": "orario", "tasks": "cosa farà", "requirements": "cosa chiedete",
          "offer": "cosa offrite", "pay": "retribuzione", "start": "inizio"}


def check(d: JobIn) -> list[Issue]:
    """Il controllo dell'annuncio: parole che la legge non permette (err) e cose da rivedere (warn, info)."""
    out: list[Issue] = []
    for f in FIELDS:
        text = getattr(d, f) or ""
        for rx, level, msg in RULES:
            m = re.search(rx, text, flags=re.I)
            if m:
                out.append(Issue(level, f, m.group(0), msg))
    gendered = re.search(r"\b(commessa|cassiera|banconiera|magazziniera|addetta|impiegata|macellaia|panettiera|"
                         r"pescivendola|commesso|cassiere|banconiere|magazziniere|addetto|impiegato|macellaio|"
                         r"panettiere|pescivendolo)\b(?!\s*/)", d.role or "", flags=re.I)
    if gendered and not re.search(r"/[aeoi]\b|m/f|f/m", d.role, flags=re.I):
        w = gendered.group(1)
        out.append(Issue("warn", "role", w, f"Meglio scrivere il ruolo per tutti i generi (per esempio «{_both(w)}»): "
                                            "altrimenti Promovo aggiunge «(m/f)»."))
    if not (d.apply_link or d.apply_email or d.in_store):
        out.append(Issue("err", "apply", "", "Scrivi come candidarsi: un link, un'email o il curriculum in negozio."))
    if not d.pay.strip():
        out.append(Issue("info", "pay", "", "Se puoi, indica la retribuzione o la sua fascia: la direttiva UE "
                                            "2023/970 sulla trasparenza retributiva chiede di comunicarla ai "
                                            "candidati, nell'annuncio o prima del colloquio."))
    # una sola segnalazione per campo e parola
    seen, uniq = set(), []
    for i in out:
        k = (i.field, i.message)
        if k not in seen:
            seen.add(k)
            uniq.append(i)
    return uniq


def _both(word: str) -> str:
    """«commessa» -> «Commesso/a», «cassiere» -> «Cassiere/a», «addetto» -> «Addetto/a»."""
    w = word.lower()
    for fem, mas in (("iera", "iere"), ("aia", "aio"), ("essa", "esso"), ("ola", "olo")):
        if w.endswith(fem):
            w = w[: -len(fem)] + mas
            break
    else:
        if w.endswith("a"):
            w = w[:-1] + "o"
    return (w + "/a").capitalize()


def validate(d: JobIn) -> JobIn:
    d.role = " ".join((d.role or "").split())
    if not d.role:
        raise JobError("Scrivi il ruolo che cercate (per esempio «Addetto/a al banco gastronomia»).")
    limits = {"role": 80, "hours_note": 120, "tasks": 600, "requirements": 600, "offer": 600, "pay": 120,
              "start": 80, "apply_link": 300, "apply_email": 160}
    for k, n in limits.items():
        v = (getattr(d, k) or "").strip()
        if len(v) > n:
            raise JobError(f"Il campo «{FIELDS.get(k, k)}» è troppo lungo (massimo {n} caratteri).")
        setattr(d, k, v)
    if d.contract not in CONTRACTS:
        raise JobError("Contratto non valido.")
    if d.hours not in HOURS:
        raise JobError("Orario non valido.")
    if d.apply_link and not re.match(r"^https?://[^\s]+\.[^\s]+$", d.apply_link):
        raise JobError("Il link per candidarsi deve iniziare con https://")
    if d.apply_email and not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", d.apply_email, flags=re.I):
        raise JobError("L'email per candidarsi non è valida.")
    d.issues = check(d)
    errs = [i for i in d.issues if i.level == "err"]
    if errs:
        raise JobError("Da correggere prima di pubblicare: " + " ".join(
            (f"«{i.found}»: " if i.found else "") + i.message for i in errs))
    return d


# ----------------------------------------------------------------- testi

def title_role(role: str) -> str:
    """Il ruolo rivolto a tutti i generi: «Addetto/a» resta com'è, altrimenti si aggiunge «(m/f)»."""
    r = role.strip()
    if re.search(r"/[aeoi]\b|\(m/f|\bm/f\b|\(f/m", r, flags=re.I):
        return r
    return f"{r} (m/f)"


def _lines(text: str) -> list[str]:
    out = []
    for x in re.split(r"[\n;]+", text or ""):
        x = x.strip().lstrip("•-–* ").strip()
        if x:
            out.append(x[:1].upper() + x[1:])
    return out


def how_to_apply(store: Store, j: JobPost) -> list[str]:
    out = []
    if j.apply_link:
        out.append(f"Candidati qui: {j.apply_link}")
    if j.apply_email:
        out.append(f"Manda il curriculum a {j.apply_email}")
    if j.in_store:
        where = ", ".join(x for x in (store.address, store.city) if x)
        out.append("Lascia il curriculum alla cassa" + (f" ({where})" if where else ""))
    return out


def conditions(j: JobPost) -> str:
    s = f"{CONTRACTS[j.contract][:1].upper() + CONTRACTS[j.contract][1:]}, {HOURS[j.hours]}"
    return s + (f" ({j.hours_note})" if j.hours_note else "")


def texts(store: Store, j: JobPost) -> dict:
    tone = store.tone or "familiare"
    emoji = tone in ("familiare", "giovane")
    role = title_role(j.role)
    where = store.city or ""
    head = f"{store.name}{' – ' + where if where else ''} cerca: {role}"
    full = [head, "", f"Contratto: {conditions(j)}"]
    if j.start:
        full.append(f"Inizio: {j.start}")
    for label, items in (("Cosa farai", _lines(j.tasks)), ("Cosa chiediamo", _lines(j.requirements)),
                         ("Cosa offriamo", _lines(j.offer))):
        if items:
            full += ["", label + ":"] + [f"• {x}" for x in items]
    if j.pay:
        full += ["", f"Retribuzione: {j.pay}"]
    full += ["", "Come candidarsi:"] + [f"• {x}" for x in how_to_apply(store, j)]
    full += ["", LEGAL_NOTE, PRIVACY_NOTE]

    post = [("🧑‍🍳 " if emoji else "") + f"Lavora con noi! {store.name} cerca: {role}", "",
            conditions(j) + (f" · inizio {j.start}" if j.start else "") + "."]
    perks = _lines(j.offer)[:3]
    if perks:
        post += [""] + [("✅ " if emoji else "• ") + x for x in perks]
    if j.pay:
        post.append(("💶 " if emoji else "") + j.pay)
    post += [""] + [("👉 " if emoji else "") + x for x in how_to_apply(store, j)]
    post += ["", LEGAL_NOTE]
    tags = ["#lavoro", "#lavoraconnoi", "#offertadilavoro"]
    if where:
        tags.append("#lavoro" + re.sub(r"[^A-Za-zÀ-ÿ]", "", where.title()))
    post += ["", " ".join(tags)]
    status = f"{store.name} cerca: {role}. {conditions(j)}. " + " · ".join(how_to_apply(store, j))
    return {"title": head, "full": "\n".join(full), "post": "\n".join(post), "status": status}


# ----------------------------------------------------------------- grafiche

def _block(store: Store, j: JobPost, W: int, dark: bool, bullets: int = 3, k: float = 1.0) -> Image.Image:
    u = W / 1080 * k
    brand = hex_rgb(store.brand_color)
    fg = WHITE if dark else INK
    sub = (235, 235, 240) if dark else (70, 74, 86)
    hi = (255, 220, 120) if dark else readable_on_paper(brand)
    pad = int(70 * W / 1080)
    layers = [(pill("LAVORA CON NOI", int(30 * u), WHITE if dark else brand, brand if dark else None), int(34 * u))]
    fc = font(int(56 * u), True)
    layers.append((text_layer(["Cerchiamo"], fc, sub, "center"), int(8 * u)))
    fr, lr = fit_text(title_role(j.role), W - 2 * pad, int(300 * u), int(104 * u), "display", 3)
    layers.append((text_layer(lr, fr, hi, "center"), int(28 * u)))
    fk, lk = fit_text(conditions(j) + (f" · inizio {j.start}" if j.start else ""), W - 2 * pad, int(110 * u),
                      int(44 * u), True, 2)
    layers.append((text_layer(lk, fk, fg, "center"), int(30 * u)))
    items = (_lines(j.offer) or _lines(j.tasks))[:bullets]
    if j.pay:
        pay = j.pay if j.pay.lower().startswith(("retribu", "stipend", "paga")) else f"Retribuzione: {j.pay}"
        items = (items + [pay])[: bullets + 1]
    for it in items:
        fb, lb = fit_text("• " + it, W - 2 * pad, int(110 * u), int(40 * u), False, 2)
        layers.append((text_layer(lb, fb, sub, "center"), int(12 * u)))
    total = sum(l.height + g for l, g in layers)
    block = Image.new("RGBA", (W, total), (0, 0, 0, 0))
    y = 0
    for lay, g in layers:
        block.alpha_composite(lay, ((W - lay.width) // 2, y))
        y += lay.height + g
    return block


def social_image(store: Store, j: JobPost, W: int = 1080, H: int = 1350) -> Image.Image:
    u = W / 1080
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = brand_background(W, H, brand, accent, u)
    d = ImageDraw.Draw(img)
    logo = logo_image(store.logo_path or None, int(300 * u), int(100 * u), brand)
    top = int(70 * u)
    if logo is not None:
        img.alpha_composite(logo, ((W - logo.width) // 2, top))
        top += logo.height + int(20 * u)
    else:
        fs, ls = fit_text(store.name, W - int(140 * u), int(70 * u), int(46 * u), True, 1)
        d.text((W // 2, top + int(30 * u)), ls[0], font=fs, fill=text_on(brand), anchor="mm")
        top += int(80 * u)
    block = _block(store, j, W, True, 4 if H > 1500 else 3, 1.3 if H > 1500 else 1.0)
    apply = how_to_apply(store, j)
    foot = int(170 * u)
    room = H - top - foot
    if block.height > room:
        block = block.resize((int(block.width * room / block.height), room), Image.LANCZOS)
    img.alpha_composite(block, ((W - block.width) // 2, top + (room - block.height) // 2))
    if apply:
        fa, la = fit_text(apply[0], W - int(140 * u), int(110 * u), int(38 * u), True, 2)
        lay = text_layer(la, fa, text_on(brand), "center")
        img.alpha_composite(lay, ((W - lay.width) // 2, H - int(60 * u) - lay.height))
    return img.convert("RGB")


def screen_image(store: Store, j: JobPost) -> Image.Image:
    """Schermata 16:9 per gli schermi del negozio, con il QR se c'è il link per candidarsi."""
    W, H = 1920, 1080
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = brand_background(W, H, brand, accent, 1.0)
    qr = qr_image(j.apply_link, 340) if j.apply_link else None
    bw = 1200 if qr is not None else 1400
    block = _block(store, j, bw, True, 3)
    if block.height > H - 180:
        block = block.resize((int(block.width * (H - 180) / block.height), H - 180), Image.LANCZOS)
    x0 = 120 if qr is not None else (W - block.width) // 2
    img.alpha_composite(block, (x0, (H - block.height) // 2))
    d = ImageDraw.Draw(img)
    if qr is not None:
        qx, qy = W - 140 - qr.width, (H - qr.height) // 2 - 30
        d.rounded_rectangle((qx - 24, qy - 24, qx + qr.width + 24, qy + qr.height + 24), 28, fill=WHITE)
        img.alpha_composite(qr, (qx, qy))
        d.text((qx + qr.width // 2, qy + qr.height + 70), "Inquadra e candidati", font=font(40, True),
               fill=text_on(brand), anchor="mm")
    d.text((W // 2, H - 50), store.name, font=font(36, True), fill=text_on(brand), anchor="mm")
    return img.convert("RGB")


def poster_pdf(store: Store, j: JobPost, out) -> object:
    """Il cartello A4 per la porta e la cassa: fondo chiaro, QR grande per candidarsi, stampa bene anche in b/n."""
    W, H = 2480, 3508
    brand = hex_rgb(store.brand_color)
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 360), fill=brand)
    fs, ls = fit_text(store.name, W - 300, 200, 130, "display", 1)
    d.text((W // 2, 180), ls[0], font=fs, fill=text_on(brand), anchor="mm")
    # il piede: come candidarsi (QR, email, cassa) e la nota di legge, misurato prima di disporre il resto
    foot: list[tuple[Image.Image, int]] = [(text_layer(["Come candidarti"], font(84, True), INK, "center"), 50)]
    qr = qr_image(j.apply_link, 620) if j.apply_link else None
    if qr is not None:
        foot.append((qr, 24))
        foot.append((text_layer(["Inquadra il codice con il telefono"], font(56), (70, 74, 86), "center"), 50))
    for a in how_to_apply(store, j):
        if a.startswith("Candidati qui"):
            continue
        fa, la = fit_text(a, W - 400, 150, 64, True, 2)
        foot.append((text_layer(la, fa, INK, "center"), 30))
    fn, ln = fit_text(LEGAL_NOTE, W - 400, 130, 40, False, 2)
    note = text_layer(ln, fn, (110, 114, 124), "center")
    foot_h = sum(l.height + g for l, g in foot) + 120
    y_foot = H - 80 - note.height - foot_h
    block = _block(store, j, W, False, 4)
    room = y_foot - 360 - 120
    if block.height > room:
        block = block.resize((int(block.width * room / block.height), room), Image.LANCZOS)
    img.paste(block, ((W - block.width) // 2, 400 + (room - block.height) // 2), block)
    d.line((240, y_foot, W - 240, y_foot), fill=(225, 220, 210), width=6)
    y = y_foot + 80
    for lay, g in foot:
        img.paste(lay, ((W - lay.width) // 2, y), lay)
        y += lay.height + g
    img.paste(note, ((W - note.width) // 2, H - 60 - note.height), note)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PDF", resolution=300)
    return out
