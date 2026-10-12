# Porta le pagine PDF alle misure esatte (Chromium arrotonda per eccesso)
# e imposta TrimBox/BleedBox per la tipografia.
import sys
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
MM = 72/25.4
pagine = [(150, 100), (130, 88)]
def rifila(path, bleed, marks):
    r = PdfReader(path); w = PdfWriter()
    for pg, (tw, th) in zip(r.pages, pagine):
        top = float(pg.mediabox.top)
        W = (tw + 2*(bleed+marks))*MM; H = (th + 2*(bleed+marks))*MM
        box = lambda off: RectangleObject([off*MM, top - H + off*MM, W - off*MM, top - off*MM])
        pg.mediabox = box(0); pg.cropbox = box(0)
        pg.trimbox = box(bleed+marks); pg.bleedbox = box(marks)
        w.add_page(pg)
    w.add_metadata({'/Title': 'Gustoso – Pizza Romana surgelata – etichette fronte/retro', '/Author': 'Gustoso Cucina Italiana'})
    with open(path, 'wb') as f: w.write(f)
rifila(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
