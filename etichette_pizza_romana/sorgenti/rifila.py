# Porta le pagine PDF alle misure esatte (Chromium arrotonda per eccesso)
# e imposta TrimBox/BleedBox per la tipografia.
import sys, re
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject, NameObject

# Il nero puro RGB (0 0 0) - barre e cifre del codice a barre, crocini, pieghe della bandiera -
# viene scritto come solo nero K (C0 M0 Y0 K100): in stampa il codice a barre esce con un solo
# inchiostro, senza rischio di fuori registro tra i colori. Gli altri colori restano invariati.
NERO_RGB = re.compile(rb'(?<![\d.])0 0 0 (rg|RG)\b')
def nero_k(data):
    return NERO_RGB.sub(lambda m: b'0 0 0 1 ' + (b'k' if m.group(1) == b'rg' else b'K'), data)

def converti_neri(obj, visti):
    """Converte i neri negli stream di contenuto e nei Form XObject annidati."""
    res = obj.get('/Resources')
    if res is None: return
    res = res.get_object()
    xo = res.get('/XObject')
    if xo is None: return
    for nome, rif in xo.get_object().items():
        x = rif.get_object()
        if id(x) in visti or x.get('/Subtype') != '/Form': continue
        visti.add(id(x))
        x.set_data(nero_k(x.get_data()))
        converti_neri(x, visti)
MM = 72/25.4
pagine = [(150, 100), (130, 88)]
def rifila(path, bleed, marks, titolo='Gustoso – Pizza romana surgelata – etichette fronte/retro'):
    r = PdfReader(path); w = PdfWriter()
    for pg, (tw, th) in zip(r.pages, pagine):
        top = float(pg.mediabox.top)
        W = (tw + 2*(bleed+marks))*MM; H = (th + 2*(bleed+marks))*MM
        box = lambda off: RectangleObject([off*MM, top - H + off*MM, W - off*MM, top - off*MM])
        pg.mediabox = box(0); pg.cropbox = box(0)
        pg.trimbox = box(bleed+marks); pg.bleedbox = box(marks)
        c = pg.get_contents()
        c.set_data(nero_k(c.get_data())); pg[NameObject('/Contents')] = c
        converti_neri(pg, set())
        w.add_page(pg)
    w.add_metadata({'/Title': titolo, '/Author': 'Gustoso di Boccuccia Angelo'})
    with open(path, 'wb') as f: w.write(f)
rifila(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), *(sys.argv[4:5]))
