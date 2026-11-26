# Aggiunge i campi compilabili (modulo PDF standard, AcroForm) al PDF di un gusto:
# ingredienti, preparazione, peso netto, imballaggio, posizionati sugli spazi vuoti del retro.
#   python3 compilabile.py <pdf a misura (fronte+retro)> <campi.json> <uscita.pdf> [prova]
import sys, json
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (DictionaryObject, NameObject, TextStringObject, NumberObject, ArrayObject,
                           FloatObject, BooleanObject)
MM = 72 / 25.4
src, campi_json, out = sys.argv[1:4]
PROVA = len(sys.argv) > 4
campi = json.load(open(campi_json))
r = PdfReader(src); w = PdfWriter(); w.append(r)
retro = w.pages[1]
mb = retro.mediabox; x0, ytop = float(mb.left), float(mb.top)

font = lambda base: DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                                       NameObject('/BaseFont'): NameObject(base), NameObject('/Encoding'): NameObject('/WinAnsiEncoding')})
helv, hebo = w._add_object(font('/Helvetica')), w._add_object(font('/Helvetica-Bold'))

MULTILINE, DONOTSCROLL, DONOTSPELL = 1 << 12, 1 << 23, 1 << 22
# nome, testo d'aiuto (tooltip), carattere, corpo, allineamento (0 sx, 2 dx), multilinea
DEF = {
  'ingredienti': ('Ingredienti', "Ingredienti in ordine decrescente di peso. Allergeni in MAIUSCOLO (es. farina di GRANO, MOZZARELLA (LATTE)). In fondo: Può contenere tracce di ...", '/Helv', 7, 0, True),
  'preparazione': ('Preparazione', 'Modalità di cottura, es. Cuocere senza scongelare in forno statico preriscaldato a 250 °C per 6-8 minuti.', '/Helv', 7, 0, True),
  'peso': ('Peso netto (g)', 'Solo il numero dei grammi, es. 350 (la g e il simbolo e sono già stampati).', '/HeBo', 16, 2, False),
  'imballaggio': ('Imballaggio', 'Componente, materiale e codice, es. Sacchetto: Plastica PP 5 - Raccolta plastica. Verifica le disposizioni del tuo Comune.', '/Helv', 7, 0, True),
}
ESEMPI = {
  'ingredienti': 'Farina di GRANO tenero tipo 0, polpa di pomodoro (32%), MOZZARELLA (LATTE, sale, caglio) (20%), acqua, semola rimacinata di GRANO duro, salame piccante 12% (carne di suino, sale, peperoncino, destrosio, spezie, aromi naturali, antiossidante: ascorbato di sodio; conservante: nitrito di sodio), farina di SOIA, olio extravergine di oliva, sale, lievito naturale, origano. Può contenere tracce di FRUTTA A GUSCIO e SESAMO.',
  'preparazione': 'Cuocere senza scongelare in forno statico preriscaldato a 250 °C per 6-8 minuti, fino a doratura.',
  'peso': '350',
  'imballaggio': 'Sacchetto: Plastica PP 5 - Raccolta plastica. Verifica le disposizioni del tuo Comune.',
}
annots = retro.get('/Annots') or ArrayObject()
campi_pdf = ArrayObject()
for k, c in campi.items():
    nome, aiuto, f, pt, q, multi = DEF[k]
    x, y, wd, h = c['x'], c['y'], c['w'], c['h']
    if k == 'peso':
        # riga singola: i lettori PDF centrano il testo in verticale; centro di Helvetica-Bold = 1,44 mm sopra la linea di base
        cy = c['base'] - 0.255 * pt * 25.4 / 72
        y, h = cy - 3.2, 6.4
    rect = [x0 + x*MM, ytop - (y+h)*MM, x0 + (x+wd)*MM, ytop - y*MM]
    flags = DONOTSCROLL | DONOTSPELL | (MULTILINE if multi else 0)
    a = DictionaryObject({
        NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Widget'),
        NameObject('/FT'): NameObject('/Tx'), NameObject('/T'): TextStringObject(nome), NameObject('/TU'): TextStringObject(aiuto),
        NameObject('/Rect'): ArrayObject([FloatObject(v) for v in rect]), NameObject('/F'): NumberObject(4),
        NameObject('/Ff'): NumberObject(flags), NameObject('/Q'): NumberObject(q),
        NameObject('/DA'): TextStringObject(f'{f} {pt} Tf 0.137 0.122 0.125 rg'),
        NameObject('/MK'): DictionaryObject(), NameObject('/P'): retro.indirect_reference,
    })
    if k == 'peso': a[NameObject('/MaxLen')] = NumberObject(5)
    if PROVA: a[NameObject('/V')] = TextStringObject(ESEMPI[k])
    ref = w._add_object(a); annots.append(ref); campi_pdf.append(ref)
retro[NameObject('/Annots')] = annots
w._root_object[NameObject('/AcroForm')] = DictionaryObject({
    NameObject('/Fields'): campi_pdf, NameObject('/NeedAppearances'): BooleanObject(True),
    NameObject('/DA'): TextStringObject('/Helv 7 Tf 0 g'),
    NameObject('/DR'): DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/Helv'): helv, NameObject('/HeBo'): hebo})}),
})
w.add_metadata(r.metadata or {})
with open(out, 'wb') as fh: w.write(fh)
print('creato', out)
