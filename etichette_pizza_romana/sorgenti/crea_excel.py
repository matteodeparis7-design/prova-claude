# Costruisce il file Excel compilabile a partire dai render delle etichette (vedi excel.js).
# Etichette = immagini a grandezza reale; aree da compilare = caselle di testo posizionate in mm
# sopra gli spazi vuoti (allineamento identico in Excel e LibreOffice, grassetto per gli allergeni).
import json, sys, os, zipfile, re, shutil
from xml.sax.saxutils import escape
from PIL import Image
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.drawing.spreadsheet_drawing import AbsoluteAnchor
from openpyxl.drawing.xdr import XDRPoint2D, XDRPositiveSize2D
from openpyxl.styles import Font
from openpyxl.worksheet.page import PageMargins

cfg = json.load(open(sys.argv[1])); OUT = sys.argv[2]
TMP = os.path.dirname(sys.argv[1])
EMU = 36000                          # EMU per mm
FRONTE = (0.0, 0.0, 150.0, 100.0)    # x, y, larghezza, altezza in mm sul foglio
RETRO = (10.0, 110.0, 130.0, 88.0)   # retro centrato sotto il fronte
# PROVA=1 riempie le caselle con testi di esempio (solo per collaudare l'impaginazione)
PROVA = {
  'ingredienti': [('Farina di ', 0), ('grano', 1), (' tenero tipo 0, polpa di pomodoro (32%), ', 0), ('mozzarella', 1), (' (', 0), ('latte', 1),
                  (', sale, caglio) (20%), acqua, semola rimacinata di ', 0), ('grano', 1), (' duro, salame piccante 12% (carne di suino, sale, peperoncino, destrosio, spezie, aromi naturali, antiossidante: ascorbato di sodio; conservante: nitrito di sodio), farina di ', 0), ('soia', 1),
                  (', olio extravergine di oliva, sale, lievito naturale, origano. Può contenere tracce di ', 0), ('frutta a guscio', 1), (' e ', 0), ('sesamo', 1), ('.', 0)],
  'preparazione': [('Cuocere senza scongelare in forno statico preriscaldato a 250 °C per 6–8 minuti, fino a doratura.', 0)],
  'peso': [('350', 1)],
  'imballaggio': [('Sacchetto: Plastica PP 5', 1), (' – Raccolta plastica. Verifica le disposizioni del tuo Comune.', 0)],
} if os.environ.get('PROVA') else {}
# stile delle caselle: punti tipografici, allineamento orizzontale e verticale
STILE = {'ingredienti': (7, 'l', 't'), 'preparazione': (7, 'l', 't'), 'peso': (16, 'r', 't'), 'imballaggio': (7, 'l', 't')}
NOMI = {'ingredienti': 'Ingredienti', 'preparazione': 'Preparazione', 'peso': 'Peso netto', 'imballaggio': 'Imballaggio'}

def ancora(img, x, y, w, h):
    img.anchor = AbsoluteAnchor(pos=XDRPoint2D(int(x*EMU), int(y*EMU)), ext=XDRPositiveSize2D(int(w*EMU), int(h*EMU)))
    return img

def casella(idx, nome, x, y, w, h, colore, pt, algn, anchor, runs):
    def run(t, b):
        return (f'<a:r><a:rPr lang="it-IT" sz="{int(pt*100)}" b="{1 if b else 0}"><a:solidFill><a:srgbClr val="231F20"/></a:solidFill>'
                f'<a:latin typeface="Arial Narrow"/><a:cs typeface="Arial Narrow"/></a:rPr><a:t>{escape(t)}</a:t></a:r>')
    corpo = ''.join(run(t, b) for t, b in runs) if runs else ''
    fine = (f'<a:endParaRPr lang="it-IT" sz="{int(pt*100)}" b="{1 if nome == "peso" else 0}"><a:solidFill><a:srgbClr val="231F20"/></a:solidFill>'
            f'<a:latin typeface="Arial Narrow"/></a:endParaRPr>')
    X, Y, W, H = (int(v*EMU) for v in (x, y, w, h))
    return (f'<xdr:absoluteAnchor><xdr:pos x="{X}" y="{Y}"/><xdr:ext cx="{W}" cy="{H}"/>'
            f'<xdr:sp macro="" textlink=""><xdr:nvSpPr><xdr:cNvPr id="{idx}" name="{NOMI[nome]}" descr="Area da compilare: {NOMI[nome]}"/><xdr:cNvSpPr txBox="1"/></xdr:nvSpPr>'
            f'<xdr:spPr><a:xfrm><a:off x="{X}" y="{Y}"/><a:ext cx="{W}" cy="{H}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{colore}">{"<a:alpha val=\"1000\"/>" if nome == "peso" else ""}</a:srgbClr></a:solidFill><a:ln><a:noFill/></a:ln></xdr:spPr>'
            f'<xdr:txBody><a:bodyPr vertOverflow="{"overflow" if nome == "peso" else "clip"}" horzOverflow="clip" wrap="square" lIns="18000" tIns="{0 if nome in ("peso", "imballaggio") else 18000}" rIns="18000" bIns="{0 if nome in ("peso", "imballaggio") else 18000}" rtlCol="0" anchor="{anchor}"><a:noAutofit/></a:bodyPr>'
            f'<a:lstStyle/><a:p><a:pPr algn="{algn}">{"" if nome == "peso" else "<a:lnSpc><a:spcPct val=\"92000\"/></a:lnSpc>"}</a:pPr>{corpo}{fine}</a:p></xdr:txBody></xdr:sp><xdr:clientData fLocksWithSheet="0"/></xdr:absoluteAnchor>')

wb = Workbook()
ist = wb.active; ist.title = 'Istruzioni'
righe = [
  ('ETICHETTE GUSTOSO – PIZZA ROMANA SURGELATA', Font(name='Arial', size=14, bold=True, color='8E3424')),
  ('', None),
  ('Ogni foglio contiene il fronte e il retro di un gusto, a grandezza reale (fronte 150 × 100 mm, retro 130 × 88 mm).', None),
  ('Sul retro ci sono 4 caselle da compilare: si clicca sullo spazio vuoto e si scrive.', Font(name='Arial', size=10, bold=True)),
  ('   • INGREDIENTI – sotto la scritta "Ingredienti": elenco in ordine decrescente di peso; allergeni in grassetto', None),
  ('     (selezionare la parola e premere Ctrl+G o Ctrl+B); in fondo eventuali "Può contenere tracce di ...".', None),
  ('   • PREPARAZIONE – sotto la scritta "Preparazione": modalità di cottura.', None),
  ('   • PESO NETTO – nel riquadro in alto, prima della "g": solo il numero dei grammi.', None),
  ('   • IMBALLAGGIO – accanto al simbolo del riciclo: componente, materiale e codice (es. Sacchetto: Plastica PP 5).', None),
  ('Non spostare le immagini delle etichette. Se il testo è troppo lungo per la casella, la parte in eccesso non viene stampata:', None),
  ('in quel caso accorciare il testo. Non ridurre il carattere sotto 7 punti: è il minimo di leggibilità previsto dalla legge.', None),
  ('Capienza indicativa della casella ingredienti a 7 punti: circa 350 caratteri (9 righe).', None),
  ('', None),
  ('STAMPA', Font(name='Arial', size=10, bold=True)),
  ('   • Formato A4 verticale, scala 100% (non "adatta alla pagina"), su carta adesiva adatta ai surgelati (−18 °C).', None),
  ('   • Per la tipografia ci sono anche i PDF vettoriali nella cartella di ogni gusto (qualità massima, codice a barre in solo nero).', None),
  ('', None),
  ('Codici a barre: Margherita 8052675470048 · Ortolana 8052675470055 · Diavola 8052675470062.', None),
]
for i, (t, f) in enumerate(righe, 1):
    ist.cell(row=i, column=1, value=t).font = f or Font(name='Arial', size=10)
ist.column_dimensions['A'].width = 140
ist.sheet_view.showGridLines = False
ist.page_setup.paperSize = ist.PAPERSIZE_A4; ist.page_setup.orientation = 'landscape'
ist.sheet_properties.pageSetUpPr.fitToPage = True; ist.page_setup.fitToWidth = 1; ist.page_setup.fitToHeight = 0

caselle = {}
for g in cfg['gusti']:
    ws = wb.create_sheet(g['nome'])
    ws.sheet_view.showGridLines = False
    # griglia neutra: righe in punti (assolute), 10 colonne larghe ~16 mm -> area di stampa ~160 x 200 mm
    for c in 'ABCDEFGHIJ': ws.column_dimensions[c].width = 8.43
    for r in range(1, 42): ws.row_dimensions[r].height = 14.4   # 41 x 5,08 mm = 208 mm
    rt = Image.open(g['retro']); rt.load()
    sx, sy = rt.width / 130.0, rt.height / 88.0
    for nome_png, (x, y, w, h) in ((g['fronte'], FRONTE), (g['retro'], RETRO)):
        # fronte in JPEG (nessun codice a barre, file piu' leggero); retro in PNG (codice a barre nitido)
        if nome_png == g['fronte']:
            f = os.path.join(TMP, 'xl_' + os.path.basename(nome_png)[:-4] + '.jpg')
            Image.open(nome_png).convert('RGB').save(f, 'JPEG', quality=93, dpi=(600, 600))
        else:
            f = os.path.join(TMP, 'xl_' + os.path.basename(nome_png))
            Image.open(nome_png).convert('RGB').save(f, 'PNG', optimize=True)
        ws.add_image(ancora(XLImage(f), x, y, w, h))
    lista = []
    for i, (k, v) in enumerate(g['campi'].items()):
        x, y, w, h = v['x'], v['y'], v['w'], v['h']
        media = rt.crop((int(x*sx), int(y*sy), int((x+w)*sx), int((y+h)*sy))).convert('RGB').resize((1, 1), Image.BOX).getpixel((0, 0))
        pt, al, an = STILE[k]
        lista.append(casella(1000 + i, k, RETRO[0]+x, RETRO[1]+y, w, h, '%02X%02X%02X' % media, pt, al, an, PROVA.get(k)))
    caselle[g['nome']] = lista
    ws.page_setup.paperSize = ws.PAPERSIZE_A4; ws.page_setup.orientation = 'portrait'; ws.page_setup.scale = 100
    ws.sheet_properties.pageSetUpPr.fitToPage = False
    ws.page_margins = PageMargins(left=0.79, right=0.39, top=0.39, bottom=0.39, header=0, footer=0)
    ws.print_area = 'A1:J41'
    print(f"{g['nome']}: EAN {g['ean']}, caselle {list(g['campi'])}")
wb.save(OUT)

# ---- aggiunge le caselle di testo nei disegni di ciascun foglio
tmp = OUT + '.tmp'
inserite = []
with zipfile.ZipFile(OUT) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
    wbx = zin.read('xl/workbook.xml').decode()
    rels = zin.read('xl/_rels/workbook.xml.rels').decode()
    foglio_file = {}
    for nome, rid in re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wbx):
        target = re.search(rf'Id="{rid}"[^>]*Target="([^"]+)"', rels) or re.search(rf'Target="([^"]+)"[^>]*Id="{rid}"', rels)
        foglio_file[nome] = 'xl/' + target.group(1).lstrip('/').replace('xl/', '')
    disegno = {}
    for nome, f in foglio_file.items():
        rf = f.replace('worksheets/', 'worksheets/_rels/') + '.rels'
        if rf in zin.namelist():
            m = re.search(r'Target="[^"]*drawings/(drawing\d+\.xml)"', zin.read(rf).decode())
            if m: disegno['xl/drawings/' + m.group(1)] = nome
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename in disegno and disegno[item.filename] in caselle:
            xml = data.decode()
            radice = re.search(r'<(\w+:)?wsDr\b[^>]*>', xml).group(0)
            if 'xmlns:xdr=' not in radice or 'xmlns:a=' not in radice:
                nuova = radice[:-1] + ' xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                xml = xml.replace(radice, nuova, 1)
            chiusura = re.findall(r'</(?:\w+:)?wsDr>', xml)[-1]
            n_prima = xml.count('<xdr:sp ')
            xml = xml[:xml.rindex(chiusura)] + ''.join(caselle[disegno[item.filename]]) + chiusura
            assert xml.count('<xdr:sp ') == n_prima + len(caselle[disegno[item.filename]]), 'caselle non inserite'
            data = xml.encode()
            inserite.append(disegno[item.filename])
        zout.writestr(item, data)
shutil.move(tmp, OUT)
assert sorted(inserite) == sorted(caselle), f'caselle mancanti: {set(caselle) - set(inserite)}'
print('caselle di testo inserite nei fogli:', ', '.join(inserite))
print('salvato', OUT, round(os.path.getsize(OUT)/1e6, 1), 'MB')
