"""Il report della settimana per il cliente (PDF): cosa hanno fatto gli agenti e perché.

È il documento da consegnare al supermercato insieme ai materiali: offerte e prezzi controllati
(con il modo in cui è stato confermato ciascuno), l'idea della settimana, il piano di pubblicazione,
l'anteprima dei materiali e i controlli di conformità.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from .. import pdfdoc
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ContentPiece, Flyer, Store
from ..money import format_eur
from .content.writer import fmt_date, validity_text

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
A4 = pdfdoc.paper_rect("a4")
M = 46                                   # margine
INK, MUTED, LINE = (0.08, 0.11, 0.18), (0.42, 0.45, 0.52), (0.88, 0.87, 0.84)
VERIFIED = {"testo PDF": "letto dal testo del PDF", "doppia lettura": "seconda lettura ingrandita",
            "OCR": "lettura ottica", "doppia lettura IA": "seconda lettura dell'IA", "persona": "confermato a mano"}


def _hex(c: str) -> tuple[float, float, float]:
    c = (c or "#D7262E").lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]



# Gli stessi caratteri di grafiche e video: Inter per il testo, Bricolage Grotesque per i titoli.
FONT_FILES = {"pr": "Inter-Medium.ttf", "pb": "Inter-Bold.ttf", "pd": "BricolageGrotesque-ExtraBold.ttf"}
_FONTS: dict[str, pdfdoc.Font] = {}


def _font(name: str) -> pdfdoc.Font:
    if name not in _FONTS:
        _FONTS[name] = pdfdoc.Font(fontfile=str(FONTS / FONT_FILES[name]))
    return _FONTS[name]

class Doc:
    def __init__(self, brand: tuple[float, float, float]):
        self.pdf = pdfdoc.new_document()
        self.brand = brand
        self.page = None
        self.y = 0.0
        self.n = 0

    def new_page(self, title: str, store: Store) -> None:
        self.page = self.pdf.new_page(width=A4.width, height=A4.height)
        for name, file in FONT_FILES.items():
            self.page.insert_font(fontname=name, fontfile=str(FONTS / file))
        self.n += 1
        self.page.draw_rect(pdfdoc.Rect(0, 0, A4.width, 8), color=None, fill=self.brand)
        self.text(M, 30, store.name.upper(), 8.5, bold=True, color=MUTED)
        self.text(A4.width - M - 160, 30, f"Promovo · pagina {self.n}", 8.5, color=MUTED, width=160, align=2)
        self.y = 58
        if title:
            self.text(M, self.y, title, 21, bold="display")
            self.y += 34

    def text(self, x: float, y: float, s: str, size: float = 10, bold: bool | str = False, color=INK,
             width: float | None = None, align: int = 0) -> float:
        """Scrive un blocco di testo a capo automatico; restituisce l'altezza usata."""
        width = width or (A4.width - M - x)
        rect = pdfdoc.Rect(x, y, x + width, y + 2000)
        font = "pd" if bold == "display" else "pb" if bold else "pr"
        lh = size * 1.32
        # misura le righe con la larghezza dei caratteri
        f = _font(font)
        lines = []
        for para in s.split("\n"):
            cur = ""
            for w in para.split(" "):
                t = (cur + " " + w).strip()
                if f.text_length(t, fontsize=size) <= width or not cur:
                    cur = t
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
        for i, ln in enumerate(lines):
            xx = x
            if align == 2:
                xx = x + width - f.text_length(ln, fontsize=size)
            self.page.insert_text((xx, y + size + i * lh), ln, fontname=font, fontsize=size, color=color)
        del rect
        return len(lines) * lh

    def para(self, s: str, size: float = 10, bold: bool = False, color=INK, gap: float = 6) -> None:
        self.y += self.text(M, self.y, s, size, bold, color) + gap

    def heading(self, s: str) -> None:
        self.y += 8
        self.page.draw_rect(pdfdoc.Rect(M, self.y + 2, M + 4, self.y + 15), color=None, fill=self.brand)
        self.text(M + 12, self.y, s, 12.5, bold=True)
        self.y += 24

    def need(self, h: float, title: str, store: Store) -> None:
        if self.y + h > A4.height - M:
            self.new_page(title, store)


def build_report(session: Session, store: Store, flyer: Flyer, out_path: Path) -> Path:
    pieces = session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id).order_by(ContentPiece.id)).all()
    by_kind: dict[str, list[ContentPiece]] = {}
    for p in pieces:
        by_kind.setdefault(p.kind, []).append(p)
    offers = list(flyer.offers)
    ok = [o for o in offers if o.price_verified]
    doc = Doc(_hex(store.brand_color))
    doc.new_page("", store)
    # ---- copertina
    doc.y = 80
    doc.para("Report della settimana", 26, bold=True, gap=4)
    doc.para(f"{store.name} · volantino {validity_text(flyer) or 'senza date'}", 12, color=MUTED, gap=2)
    doc.para(f"Preparato da Promovo il {fmt_date(datetime.now().date())}", 9, color=MUTED, gap=18)
    if store.logo_path and Path(store.logo_path).exists():
        doc.page.insert_image(pdfdoc.Rect(A4.width - M - 130, 70, A4.width - M, 120), filename=store.logo_path,
                              keep_proportion=True)
    kpis = [(str(len(offers)), "offerte lette"), (f"{len(ok)}/{len(offers)}", "prezzi confermati"),
            (str(len(by_kind.get("video", []))), "video"), (str(len(by_kind.get("image", []))), "immagini"),
            (str(sum(len(by_kind.get(k, [])) for k in ("instagram", "facebook", "reel"))), "testi")]
    w = (A4.width - 2 * M - 4 * 10) / 5
    for i, (v, k) in enumerate(kpis):
        x = M + i * (w + 10)
        doc.page.draw_rect(pdfdoc.Rect(x, doc.y, x + w, doc.y + 62), color=LINE, fill=(0.98, 0.97, 0.95), width=0.8)
        doc.text(x + 10, doc.y + 10, v, 19, bold="display", color=doc.brand, width=w - 20)
        doc.text(x + 10, doc.y + 38, k, 8.5, color=MUTED, width=w - 20)
    doc.y += 82
    ig = (by_kind.get("instagram") or [None])[0]
    if ig is not None:
        doc.heading("L'idea della settimana")
        strategy = (ig.meta or {}).get("strategy", "")
        if strategy:
            doc.para(strategy, 10.5, gap=6)
        from .content.writer import _EMOJI_RE
        first = _EMOJI_RE.sub("", ig.body.splitlines()[0] if ig.body else "").replace("\ufe0f", "").strip()
        doc.page.draw_rect(pdfdoc.Rect(M, doc.y, A4.width - M, doc.y + 4 + 15 * max(1, len(first) // 80 + 1)),
                           color=None, fill=(0.96, 0.95, 0.92))
        doc.para("«" + first + "»", 11, bold=True, gap=8)
        doc.para("Gli agenti scelgono l'idea tra quelle che i numeri della settimana permettono (risparmi, "
                 "ricorrenze, reparti freschi, cene complete con le offerte...) e non ripetono quelle già usate "
                 "per questo negozio nelle settimane precedenti.", 9, color=MUTED, gap=6)
    # ---- anteprima dei materiali
    imgs = [p for p in by_kind.get("image", []) if p.file_path and Path(p.file_path).exists()][:4]
    posters = [p for p in by_kind.get("video", []) if (p.meta or {}).get("poster") and Path(p.meta["poster"]).exists()][:3]
    if imgs or posters:
        doc.need(230, "", store)
        doc.heading("I materiali preparati")
        x, h = M, 170
        for p in imgs:
            doc.page.insert_image(pdfdoc.Rect(x, doc.y, x + 118, doc.y + h), filename=p.file_path, keep_proportion=True)
            x += 126
        doc.y += h + 8
        if posters:
            x = M
            for p in posters:
                doc.page.insert_image(pdfdoc.Rect(x, doc.y, x + 160, doc.y + 100), filename=p.meta["poster"],
                                      keep_proportion=True)
                doc.text(x, doc.y + 102, p.title, 8, color=MUTED, width=160)
                x += 170
            doc.y += 126
    # ---- piano
    plan = (by_kind.get("plan") or [None])[0]
    if plan is not None:
        doc.new_page("Il piano della settimana", store)
        blocks = [b for b in plan.body.split("\n\n") if b.strip()]
        for b in blocks[1:]:
            lines = b.split("\n")
            if b.startswith("COSA FILMARE"):
                doc.need(80, "Il piano della settimana", store)
                doc.heading("Cosa filmare al banco")
                for ln in lines[1:]:
                    doc.para(ln, 9.5, gap=3)
                continue
            if len(lines) < 3:
                doc.para(b, 8.5, color=MUTED, gap=6)
                continue
            doc.need(50, "Il piano della settimana", store)
            doc.text(M, doc.y, lines[0], 9.5, bold=True, color=doc.brand, width=170)
            hgt = doc.text(M + 180, doc.y, lines[1], 10, bold=True, width=A4.width - 2 * M - 180)
            hgt += doc.text(M + 180, doc.y + hgt, " ".join(lines[2:]), 9.5, color=MUTED, width=A4.width - 2 * M - 180)
            doc.y += max(hgt, 28) + 8
            doc.page.draw_line((M, doc.y - 4), (A4.width - M, doc.y - 4), color=LINE, width=0.6)
    # ---- offerte e controllo dei prezzi
    doc.new_page("Offerte e controllo dei prezzi", store)
    doc.para("Ogni prezzo viene letto e poi confermato da una seconda lettura indipendente; quelli che restano "
             "da controllare sono segnalati e non vanno pubblicati finché non li conferma una persona.", 9, color=MUTED, gap=10)
    cols = [(M, "Prodotto", 230), (M + 236, "Prezzo", 60), (M + 300, "Prima", 60), (M + 364, "Controllo", 140)]
    for x, t, wd in cols:
        doc.text(x, doc.y, t, 8.5, bold=True, color=MUTED, width=wd)
    doc.y += 16
    for o in offers:
        doc.need(24, "Offerte e controllo dei prezzi (segue)", store)
        name = " ".join(x for x in (o.name, o.brand, o.description) if x)
        hgt = doc.text(M, doc.y, name, 9, width=230)
        doc.text(M + 236, doc.y, format_eur(o.price_cents), 9, bold=True, width=60)
        doc.text(M + 300, doc.y, format_eur(o.old_price_cents) if o.old_price_cents else "—", 9, color=MUTED, width=60)
        status = ("✓ " + VERIFIED.get(o.verified_by, "confermato")) if o.price_verified else "! da controllare"
        doc.text(M + 364, doc.y, status, 8.5, color=(0.1, 0.5, 0.25) if o.price_verified else (0.75, 0.45, 0.0), width=150)
        doc.y += max(hgt, 13) + 5
        doc.page.draw_line((M, doc.y - 2), (A4.width - M, doc.y - 2), color=LINE, width=0.4)
    # ---- revisore finale
    from .reviewer import review as final_review
    rv = final_review(session, store, flyer)
    doc.need(120, "Controllo di qualità", store)
    doc.heading("Controllo di qualità (Revisore finale)")
    doc.para(f"{rv['counts']['ok']} controlli superati su {len(rv['checks'])}: misure di grafiche e video, durate, "
             f"prezzi citati nei testi, materiali aggiornati agli ultimi prezzi. Esito: {rv['verdict']}.", 9.5, gap=4)
    for c in [c for c in rv["checks"] if c["status"] != "ok"][:8]:
        doc.para(f"   – {c['item']}: {c['message']}", 9, gap=3)
    # ---- Salvaspreco del mese
    from . import rescue as rescuemod
    ref = flyer.valid_from or date.today()
    rst = rescuemod.month_stats(session, store, ref.year, ref.month)
    if rst["products"]:
        doc.need(110, "Salvaspreco", store)
        doc.heading(f"Salvaspreco di {rst['label']}")
        sold = (f"{rst['kg_saved']:.1f}".replace(".", ",") + " kg di cibo salvato dallo spreco") if rst["kg_saved"] >= 0.1 \
            else f"{int(round(rst['pieces_sold']))} pezzi venduti invece di buttarli"
        doc.para(f"{rst['products']} prodotti vicini alla scadenza messi in offerta lampo; {sold}; "
                 f"{rst['revenue']} recuperati" + (f"; venduto il {rst['sell_through']}% di quanto messo in offerta"
                                                   if rst["sell_through"] is not None else "") + ".", 9.5, gap=4)
        if rst["open"]:
            doc.para(f"   – {rst['open']} prodotti ancora da chiudere con i venduti.", 9, color=MUTED, gap=3)
    # ---- Parola alla cassa
    from ..models import TillCode
    from . import till as tillmod
    if session.scalars(select(TillCode).where(TillCode.flyer_id == flyer.id)).first() is not None:
        tres = tillmod.results(session, store, flyer, date.today())
        if tres["total"]:
            doc.need(120, "Parola alla cassa", store)
            doc.heading("Parola alla cassa: chi ha portato clienti in negozio")
            doc.para(f"{tres['total']} clienti hanno detto la parola d'ordine alla cassa durante il volantino:", 9.5, gap=4)
            for r in sorted(tres["rows"], key=lambda x: x["total"], reverse=True):
                doc.para(f"   – {r['label']} («{r['word']}»): {r['total']} clienti ({r['share']}%)", 9, gap=3)
            for tip in tillmod.advice(tres, []):
                doc.para("   " + tip, 9, color=MUTED, gap=3)
    # ---- conformità
    doc.need(200, "Note di conformità", store)
    doc.heading("Note di conformità")
    struck = [o for o in offers if o.old_price_cents]
    notes = []
    if struck:
        from .omnibus import check, previous_flyers
        prev = previous_flyers(session, store, flyer)
        found = check(session, store, flyer) if prev else []
        base = (f"Prezzi barrati ({len(struck)} offerte): il prezzo «prima» deve essere il più basso praticato "
                "nei 30 giorni precedenti l'inizio dello sconto (art. 17-bis del Codice del Consumo, Direttiva Omnibus). ")
        if not prev:
            notes.append(base + "Non ci sono volantini dei 30 giorni precedenti caricati in Promovo: i prezzi barrati "
                         "sono quelli stampati sul volantino e la loro correttezza resta responsabilità del punto vendita.")
        elif not found:
            vol = "il volantino precedente" if len(prev) == 1 else f"{len(prev)} volantini precedenti"
            notes.append(base + f"Controllo automatico con {vol} del negozio: nessun prezzo "
                         "barrato più alto del minimo dei 30 giorni.")
        else:
            vol = "il volantino precedente" if len(prev) == 1 else f"{len(prev)} volantini precedenti"
            notes.append(base + f"Controllo automatico con {vol} del negozio: {len(found)} prezzi barrati "
                         "da rivedere prima della pubblicazione:")
            for x in found:
                notes.append("   – " + x.as_dict()["message"])
    notes.append("I testi citano solo prodotti e prezzi presenti nel volantino; nessuna affermazione sulla qualità o "
                 "sull'origine dei prodotti viene aggiunta dagli agenti.")
    notes.append("Le immagini dei prodotti provengono dal volantino del negozio; la musica dei video è originale, "
                 "senza diritti da pagare.")
    if any((p.meta or {}).get("voice") == "ai" for p in pieces):
        notes.append("Alcuni video usano una voce generata con IA: è dichiarata nel video, come richiede l'AI Act (art. 50).")
    notes.append("Il materiale va pubblicato dopo l'approvazione del negozio.")
    for n in notes:
        doc.para(n if n.startswith("   –") else "• " + n, 9.5, gap=5)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.pdf.save(str(out_path), garbage=3, deflate=True)
    doc.pdf.close()
    return out_path
