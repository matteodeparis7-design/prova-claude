# Versioni bianco/nero (solo nero pieno) delle illustrazioni, per la stampante termica.
# Ogni colore diventa nero o bianco in base alla luminosita' (soglia 0,62, la stessa usata nell'etichetta);
# sfumature e trasparenze leggere vengono tolte perche' in termica diventerebbero puntinate.
import re, sys
def lum(hexc):
    hexc = hexc.lstrip('#')
    if len(hexc) == 3: hexc = ''.join(c*2 for c in hexc)
    r, g, b = (int(hexc[i:i+2], 16) for i in (0, 2, 4))
    return (0.2126*r + 0.7152*g + 0.0722*b) / 255
def rgbpct(m):
    r, g, b = (float(v)/100*255 for v in m.groups())
    return '#%02x%02x%02x' % (round(r), round(g), round(b))
def bn(svg, tutto_nero=False):
    svg = re.sub(r'rgb\(([\d.]+)%,\s*([\d.]+)%,\s*([\d.]+)%\)', rgbpct, svg)
    svg = re.sub(r'(fill|stroke|stop-color)="(#[0-9A-Fa-f]{3,6})"',
                 lambda m: f'{m.group(1)}="{"#000" if tutto_nero or lum(m.group(2)) < 0.62 else "#fff"}"', svg)
    # elementi molto trasparenti (riflessi, ombre sfumate): via; gli altri a piena opacita'
    svg = re.sub(r'<(path|ellipse|circle|rect|line)\b([^>]*?)\sopacity="([\d.]+)"([^>]*)/>',
                 lambda m: '' if float(m.group(3)) < 0.5 else f'<{m.group(1)}{m.group(2)}{m.group(4)}/>', svg)
    svg = re.sub(r'stop-opacity="[\d.]+"', 'stop-opacity="0"', svg)          # gradienti d'ombra del Colosseo: tolti
    return svg
for nome, nero in (('logo_gustoso', True), ('panorama_roma', False), ('alloro', False)):
    s = open(f'assets/{nome}.svg').read()
    open(f'assets/bn/{nome}.svg', 'w').write(bn(s, nero))
    print(nome, 'ok')
