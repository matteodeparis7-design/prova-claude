#!/usr/bin/env python3
"""Impagina il PDF del fascicolo.

1. genera il PDF dalla versione di stampa (Playwright/Chromium);
2. trova la pagina d'inizio di ogni capitolo e la scrive nell'indice;
3. rigenera il PDF e aggiunge intestazione (capitolo corrente) e numero di pagina.

Uso:  python3 build/build.py && python3 build/impagina.py
"""
import io
import json
import pathlib
import subprocess
import sys

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

QUI = pathlib.Path(__file__).resolve().parent
RADICE = QUI.parent
sys.path.insert(0, str(QUI))
import build  # noqa: E402

GREZZO = QUI / "grezzo.pdf"
FINALE = RADICE / "Fascicolo-Tecniche-della-Programmazione.pdf"

JS = r"""
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto(process.argv[2], { waitUntil: 'networkidle' });
  await p.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true));
  await p.emulateMedia({ media: 'print', colorScheme: 'light' });
  await p.pdf({ path: process.argv[3], format: 'A4', printBackground: true, preferCSSPageSize: true });
  await b.close();
})();
"""


def genera_pdf():
    script = QUI / "_stampa.js"
    script.write_text(JS, encoding="utf-8")
    sorgente = (QUI / "fascicolo-stampa.html").as_uri()
    subprocess.run(["node", str(script), sorgente, str(GREZZO)], check=True)
    script.unlink()


def pagine_capitoli(elenco):
    lettore = PdfReader(str(GREZZO))
    inizio = {}
    for i, pagina in enumerate(lettore.pages):
        testo = pagina.extract_text() or ""
        for ident, _, _ in elenco:
            if ident not in inizio and ("@@CAP:%s@@" % ident) in testo:
                inizio[ident] = i + 1          # numeri di pagina da 1
    mancanti = [c[0] for c in elenco if c[0] not in inizio]
    if mancanti:
        raise SystemExit("capitoli non trovati nel PDF: %s" % mancanti)
    return inizio, len(lettore.pages)


def sovrapponi(elenco, inizio, totale):
    larghezza, altezza = A4
    margine = 18 * 72 / 25.4
    ordinati = sorted(((inizio[c[0]], c) for c in elenco))
    lettore = PdfReader(str(GREZZO))
    scrittore = PdfWriter()
    for i, pagina in enumerate(lettore.pages):
        n = i + 1
        if n > 1:                               # niente su copertina
            if n < ordinati[0][0]:
                sinistra = "Indice"
            else:
                corrente = [c for p, c in ordinati if p <= n][-1]
                sinistra = "%s · %s" % (corrente[1], corrente[2])
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            c.setFont("Helvetica", 7.8)
            c.setFillColorRGB(0.36, 0.40, 0.47)
            y = altezza - 13 * 72 / 25.4
            c.drawString(margine, y, sinistra[:95])
            c.drawRightString(larghezza - margine, y, "Tecniche della Programmazione")
            c.setStrokeColorRGB(0.82, 0.85, 0.89)
            c.setLineWidth(0.5)
            c.line(margine, y - 4, larghezza - margine, y - 4)
            c.setFont("Helvetica", 8.5)
            c.drawCentredString(larghezza / 2, 10 * 72 / 25.4, "%d / %d" % (n, totale))
            c.save()
            buf.seek(0)
            pagina.merge_page(PdfReader(buf).pages[0])
        scrittore.add_page(pagina)
    scrittore.add_metadata({"/Title": "Fascicolo di Tecniche della Programmazione",
                            "/Subject": "Preparazione all'esame - prof. M. Temperini, A.A. 2026/27"})
    # file piu` leggero: unisce gli oggetti duplicati (font, immagini) e comprime
    for pagina in scrittore.pages:
        pagina.compress_content_streams()
    scrittore.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    # segnalibri (indice cliccabile nel lettore PDF)
    for p, c in ordinati:
        scrittore.add_outline_item("%s - %s" % (c[1], c[2]), p - 1)
    with open(FINALE, "wb") as f:
        scrittore.write(f)


def main():
    elenco = json.loads((QUI / "capitoli.json").read_text(encoding="utf-8"))
    genera_pdf()
    inizio, _ = pagine_capitoli(elenco)
    build.main_stampa(inizio)                  # indice con i numeri veri
    genera_pdf()
    inizio2, totale = pagine_capitoli(elenco)
    if inizio2 != inizio:                      # l'indice non deve spostare nulla
        build.main_stampa(inizio2)
        genera_pdf()
        inizio2, totale = pagine_capitoli(elenco)
    sovrapponi(elenco, inizio2, totale)
    GREZZO.unlink()
    print("PDF:", FINALE.name, "-", totale, "pagine")
    for ident, etich, titolo in elenco:
        print("  %3d  %s  %s" % (inizio2[ident], etich, titolo))


if __name__ == "__main__":
    main()
