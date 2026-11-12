#!/usr/bin/env python3
"""Compone il fascicolo: capitoli Markdown + codice C collaudato -> HTML.

Uso:  python3 build.py            (scrive fascicolo.html e fascicolo-stampa.html)

Direttive nei capitoli:
  {{inc file.c tag}}        inserisce la regione tra /* >>> tag */ e /* <<< tag */
  ::: tipo Titolo ... :::   riquadro (esame, errore, nota, esercizio)
  ::: soluzione ... :::     soluzione a scomparsa
  ::: domanda Testo ... ::: domanda d'orale con risposta a scomparsa
"""
import html
import pathlib
import re
import textwrap

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import CLexer

RADICE = pathlib.Path(__file__).resolve().parent.parent
CAPITOLI = RADICE / "capitoli"
CODICE = RADICE / "codice"
USCITA = RADICE

TITOLI_BOX = {
    "esame": "All'esame",
    "errore": "Errore tipico",
    "nota": "Da sapere",
    "esercizio": "Esercizio",
}


PARTI = [
    ("Per cominciare", [0, -1]),
    ("Il calcolatore", [1, 2]),
    ("Programmare in C", [3, 4, 5, 6, 7]),
    ("Memoria e dati strutturati", [8, 9, 10]),
    ("Metodo", [11, 12, 13]),
    ("Strutture dati dinamiche", [14, 15]),
    ("Verso l'esame", [16, 17, 18, 19, 20]),
    ("Allenamento", [21]),
]


def regione(file, tag):
    testo = (CODICE / file).read_text(encoding="utf-8")
    m = re.search(r"/\* >>> %s \*/\n(.*?)/\* <<< %s \*/" % (re.escape(tag), re.escape(tag)), testo, re.S)
    if not m:
        raise SystemExit("regione %s non trovata in %s" % (tag, file))
    return textwrap.dedent(m.group(1)).rstrip() + "\n"


def evidenzia(codice):
    fmt = HtmlFormatter(nowrap=True)
    return highlight(codice, CLexer(), fmt)


def blocco_codice(codice, lingua, didascalia=None):
    if lingua == "c":
        corpo = evidenzia(codice)
        classe = "codice"
    else:
        corpo = html.escape(codice)
        classe = "codice schema"
    cap = ""
    if didascalia:
        cap = '<figcaption>%s</figcaption>' % html.escape(didascalia)
    return '<figure class="%s">%s<pre><code>%s</code></pre></figure>' % (classe, cap, corpo.rstrip("\n"))


SEGNAPOSTO = {}


def segnaposto(html_frammento):
    chiave = "XXBLOCCO%dXX" % len(SEGNAPOSTO)
    SEGNAPOSTO[chiave] = html_frammento
    return "\n\n" + chiave + "\n\n"


def preprocessa(md):
    # inclusioni di codice
    def inc(m):
        file, tag = m.group(1), m.group(2)
        return segnaposto(blocco_codice(regione(file, tag), "c", "codice/" + file))
    md = re.sub(r"\{\{inc (\S+) (\S+)\}\}", inc, md)

    # blocchi di codice recintati
    def recinto(m):
        lingua = m.group(1) or "text"
        return segnaposto(blocco_codice(m.group(2), lingua))
    md = re.sub(r"```(\w*)\n(.*?)```", recinto, md, flags=re.S)
    return md


def converti_md(testo):
    return markdown.markdown(testo, extensions=["tables", "attr_list", "md_in_html", "sane_lists"])


def riquadri(md):
    """Trasforma i blocchi ::: in HTML (i blocchi non sono annidati)."""
    def sost(m):
        tipo = m.group(1)
        titolo = (m.group(2) or "").strip()
        corpo = converti_md(m.group(3))
        if tipo == "soluzione":
            return segnaposto('<details class="sol"><summary>Soluzione</summary><div class="sol-corpo">%s</div></details>' % corpo)
        if tipo == "domanda":
            return segnaposto('<details class="domanda"><summary>%s</summary><div class="sol-corpo">%s</div></details>'
                              % (html.escape(titolo), corpo))
        etichetta = titolo or TITOLI_BOX.get(tipo, tipo)
        return segnaposto('<aside class="box box-%s"><p class="box-titolo">%s</p>%s</aside>'
                          % (tipo, html.escape(etichetta), corpo))
    return re.sub(r"^::: (\w+)[ ]?([^\n]*)\n(.*?)\n:::[ ]*$", sost, md, flags=re.S | re.M)


def ripristina(h):
    # i segnaposto possono essere annidati (codice dentro i riquadri)
    for _ in range(3):
        h = re.sub(r"<p>(XXBLOCCO\d+XX)</p>", lambda m: SEGNAPOSTO[m.group(1)], h)
        h = re.sub(r"XXBLOCCO\d+XX", lambda m: SEGNAPOSTO[m.group(0)], h)
    return h


def checklist(h):
    return h.replace("<li>[ ] ", '<li class="check"><span class="casella" aria-hidden="true"></span>')


def capitolo(percorso, numero):
    md = percorso.read_text(encoding="utf-8")
    m = re.match(r"# (.+?) \{#(\w+)\}\n", md)
    titolo, ident = m.group(1), m.group(2)
    md = md[m.end():]
    md = preprocessa(md)
    md = riquadri(md)
    corpo = ripristina(checklist(converti_md(md)))
    # titoli di secondo livello con ancore
    contatore = [0]

    def ancora(mm):
        contatore[0] += 1
        return '<h2 id="%s-%d">%s</h2>' % (ident, contatore[0], mm.group(1))
    corpo = re.sub(r"<h2>(.*?)</h2>", ancora, corpo)
    etichetta = {0: "Introduzione", -1: "Laboratorio"}.get(numero, "Capitolo %d" % numero)
    sezione = ('<section class="capitolo" id="%s" aria-labelledby="t-%s">'
               '<header class="cap-testa"><p class="cap-num">%s</p><h1 id="t-%s">%s</h1></header>%s</section>'
               % (ident, ident, etichetta, ident, titolo, corpo))
    return ident, numero, titolo, sezione


def main():
    file = sorted(CAPITOLI.glob("*.md"))
    capitoli = []
    for f in file:
        numero = int(f.name[:2])
        if f.name[2] != "-":          # es. 00b-laboratorio: sezione senza numero
            numero = -1
        capitoli.append(capitolo(f, numero))

    parti = PARTI
    per_numero = {c[1]: c for c in capitoli}
    indice = []
    for nome, numeri in parti:
        voci = []
        for n in numeri:
            ident, num, titolo, _ = per_numero[n]
            pref = "" if num <= 0 else '<span class="toc-n">%d</span>' % num
            voci.append('<li><a href="#%s">%s<span class="toc-t">%s</span></a>'
                        '<input type="checkbox" class="fatto" id="fatto-%s" data-cap="%s" aria-label="Segna come studiato: %s"></li>'
                        % (ident, pref, titolo, ident, ident, html.escape(titolo)))
        indice.append('<li class="toc-parte"><p>%s</p><ol>%s</ol></li>' % (nome, "".join(voci)))
    indice_html = '<ol class="toc">%s</ol>' % "".join(indice)
    corpo = "\n".join(c[3] for c in capitoli)

    modello = (RADICE / "build" / "modello.html").read_text(encoding="utf-8")
    pagina = modello.replace("{{INDICE}}", indice_html).replace("{{CORPO}}", corpo)
    (USCITA / "fascicolo.html").write_text(pagina, encoding="utf-8")

    scrivi_stampa(modello, parti, per_numero, pagine={})
    print("ok:", len(capitoli), "capitoli,", len(pagina) // 1024, "KB")


def scrivi_stampa(modello, parti, per_numero, pagine):
    """Versione per il PDF: copertina, indice con numeri di pagina, capitoli.
    `pagine` mappa ident -> numero di pagina (vuoto al primo passaggio)."""
    testa = modello[:modello.index("<!--STAMPA-->")]
    stile = "<style>" + (RADICE / "build" / "stampa.css").read_text(encoding="utf-8") + "</style>"
    copertina = (
        '<section class="copertina">'
        '<p class="cop-occhiello">Sapienza Università di Roma · Ingegneria dell\'Informazione · sede di Latina</p>'
        '<h1 class="cop-titolo">Tecniche della<br><span>Programmazione</span></h1>'
        '<p class="cop-sotto">Fascicolo di preparazione all\'esame<br>corso del prof. Marco Temperini · A.A. 2026/27</p>'
        '<ul class="cop-lista">'
        '<li>Teoria spiegata in modo semplice, nell\'ordine del corso</li>'
        '<li>Laboratorio per imparare a programmare in C</li>'
        '<li>Codice ANSI C compilato e collaudato</li>'
        '<li>Le tracce d\'esame del professore risolte</li>'
        '<li>Tracce di esercitazione, palestra di 25 esercizi, orale</li>'
        '</ul>'
        '<p class="cop-nota">Materiale di studio non ufficiale, costruito sul programma e sui materiali '
        'pubblicati sul sito del corso. Per regole e date fanno fede il sito del corso e Classroom.</p>'
        '</section>')
    righe = []
    for nome, numeri in parti:
        righe.append('<li class="ind-parte">%s</li>' % nome)
        for n in numeri:
            ident, num, titolo, _ = per_numero[n]
            etich = "" if num <= 0 else "%d" % num
            righe.append('<li class="ind-voce"><span class="ind-n">%s</span><span class="ind-t">%s</span>'
                         '<span class="ind-punti"></span><span class="ind-p">%s</span></li>'
                         % (etich, titolo, pagine.get(ident, "00")))
    indice = '<section class="indice-stampa"><h1>Indice</h1><ol>%s</ol></section>' % "".join(righe)
    corpo = []
    for nome, numeri in parti:
        for n in numeri:
            ident, num, titolo, sezione = per_numero[n]
            # marcatore invisibile per ritrovare nel PDF la pagina d'inizio del capitolo
            sezione = sezione.replace('<header class="cap-testa">',
                                      '<header class="cap-testa"><span class="marca">@@CAP:%s@@</span>' % ident, 1)
            corpo.append(sezione)
    html_stampa = ('<!doctype html><html lang="it"><head><meta charset="utf-8">' + testa + stile +
                   '</head><body><main class="stampa">' + copertina + indice + "\n".join(corpo) +
                   '</main></body></html>')
    (RADICE / "build" / "fascicolo-stampa.html").write_text(html_stampa, encoding="utf-8")
    # elenco dei capitoli per l'impaginazione (ident, etichetta, titolo)
    import json
    elenco = []
    for nome, numeri in parti:
        for n in numeri:
            ident, num, titolo, _ = per_numero[n]
            etich = {0: "Introduzione", -1: "Laboratorio"}.get(num, "Capitolo %d" % num)
            elenco.append([ident, etich, re.sub(r"<[^>]+>", "", titolo)])
    (RADICE / "build" / "capitoli.json").write_text(json.dumps(elenco, ensure_ascii=False), encoding="utf-8")


def solo_stampa(pagine):
    """Rigenera solo la versione di stampa con i numeri di pagina noti."""
    main_stampa(pagine)


def main_stampa(pagine):
    file = sorted(CAPITOLI.glob("*.md"))
    capitoli = []
    for f in file:
        numero = int(f.name[:2])
        if f.name[2] != "-":
            numero = -1
        capitoli.append(capitolo(f, numero))
    per_numero = {c[1]: c for c in capitoli}
    modello = (RADICE / "build" / "modello.html").read_text(encoding="utf-8")
    scrivi_stampa(modello, PARTI, per_numero, pagine)


if __name__ == "__main__":
    main()
