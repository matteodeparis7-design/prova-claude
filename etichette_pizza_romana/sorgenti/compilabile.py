# Aggiunge i campi compilabili (modulo PDF standard AcroForm) al PDF di un gusto, sul retro (pagina 2).
#   python3 compilabile.py <pdf> <campi.json> <uscita.pdf> <abbondanza mm> [prova]
# Campi: peso netto, scadenza, lotto, codice del materiale della busta (menu), eventuali valori nutrizionali mancanti.
import sys, json
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (DictionaryObject, NameObject, TextStringObject, NumberObject, ArrayObject, FloatObject, BooleanObject)
MM = 72 / 25.4
src, campi_json, out, bleed = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
PROVA = len(sys.argv) > 5
campi = json.load(open(campi_json))
r = PdfReader(src); w = PdfWriter(); w.append(r)
retro = w.pages[1]
mb = retro.mediabox; x0, ytop = float(mb.left) + bleed*MM, float(mb.top) - bleed*MM

font = lambda base: DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                                       NameObject('/BaseFont'): NameObject(base), NameObject('/Encoding'): NameObject('/WinAnsiEncoding')})
helv, hebo = w._add_object(font('/Helvetica')), w._add_object(font('/Helvetica-Bold'))
DONOTSCROLL, DONOTSPELL, COMBO, EDIT = 1 << 23, 1 << 22, 1 << 17, 1 << 18
ESEMPI = {'Peso netto (g)': '350', 'Da consumarsi entro': '31/12/2027', 'Lotto': 'L24335', 'Codice materiale busta': 'PP 5'}

annots = retro.get('/Annots') or ArrayObject()
campi_pdf = ArrayObject()
for c in campi:
    x, y, wd, h = c['x'], c['y'], c['w'], c['h']
    if c['tipo'] == 'peso':
        pt, f, q = 16, '/HeBo', 2
        cy = c['base'] - 0.255 * pt * 25.4 / 72     # i lettori centrano la riga: centro di Helvetica-Bold 1,44 mm sopra la linea di base
        y, h = cy - 3.2, 6.4
    else:
        pt, f, q = c['pt'], '/HeBo' if c.get('grassetto') else '/Helv', 2 if c['tipo'] == 'nutri' else 0
    rect = [x0 + x*MM, ytop - (y+h)*MM, x0 + (x+wd)*MM, ytop - y*MM]
    a = DictionaryObject({
        NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Widget'),
        NameObject('/T'): TextStringObject(c['nome']), NameObject('/TU'): TextStringObject(c['aiuto']),
        NameObject('/Rect'): ArrayObject([FloatObject(v) for v in rect]), NameObject('/F'): NumberObject(4),
        NameObject('/Q'): NumberObject(q), NameObject('/DA'): TextStringObject(f'{f} {pt} Tf 0 g'),
        NameObject('/MK'): DictionaryObject(), NameObject('/P'): retro.indirect_reference,
    })
    if c['tipo'] == 'scelta':
        a[NameObject('/FT')] = NameObject('/Ch')
        a[NameObject('/Ff')] = NumberObject(COMBO | EDIT | DONOTSPELL)
        a[NameObject('/Opt')] = ArrayObject([TextStringObject(o) for o in c['opzioni']])
    else:
        a[NameObject('/FT')] = NameObject('/Tx')
        a[NameObject('/Ff')] = NumberObject(DONOTSCROLL | DONOTSPELL)
        if c['tipo'] == 'peso': a[NameObject('/MaxLen')] = NumberObject(5)
    if PROVA:
        v = ESEMPI.get(c['nome'], '1036 kJ / 248 kcal' if 'Energia' in c['nome'] else '8,0 g')
        a[NameObject('/V')] = TextStringObject(v)
    ref = w._add_object(a); annots.append(ref); campi_pdf.append(ref)
retro[NameObject('/Annots')] = annots
w._root_object[NameObject('/AcroForm')] = DictionaryObject({
    NameObject('/Fields'): campi_pdf, NameObject('/NeedAppearances'): BooleanObject(True),
    NameObject('/DA'): TextStringObject('/Helv 7 Tf 0 g'),
    NameObject('/DR'): DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/Helv'): helv, NameObject('/HeBo'): hebo})}),
})
w.add_metadata(r.metadata or {})
with open(out, 'wb') as fh: w.write(fh)
