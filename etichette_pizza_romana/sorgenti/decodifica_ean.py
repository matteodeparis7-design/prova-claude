# Decodifica EAN-13 dal PDF finale (pagina del retro), come farebbe uno scanner:
# rasterizza a 1200 dpi, legge una riga orizzontale attraverso le barre e decodifica.
import sys, subprocess, tempfile, os
from PIL import Image
L = {'0001101': 0, '0011001': 1, '0010011': 2, '0111101': 3, '0100011': 4, '0110001': 5, '0101111': 6, '0111011': 7, '0110111': 8, '0001011': 9}
G = {k.translate(str.maketrans('01', '10'))[::-1]: v for k, v in L.items()}
Rc = {k.translate(str.maketrans('01', '10')): v for k, v in L.items()}
PAR = {'LLLLLL': 0, 'LLGLGG': 1, 'LLGGLG': 2, 'LLGGGL': 3, 'LGLLGG': 4, 'LGGLLG': 5, 'LGGGLL': 6, 'LGLGLG': 7, 'LGLGGL': 8, 'LGGLGL': 9}
pdf, pagina = sys.argv[1], sys.argv[2]
d = tempfile.mkdtemp()
subprocess.run(['pdftoppm', '-r', '1200', '-f', pagina, '-l', pagina, '-gray', '-png', pdf, os.path.join(d, 'p')], check=True)
im = Image.open(os.path.join(d, os.listdir(d)[0])).convert('L')
W, H = im.size; px = im.load()
risultati = set()
for frac in [i/100 for i in range(55, 95)]:
    y = int(H*frac)
    row = [px[x, y] < 128 for x in range(W)]
    # run-length
    runs = []; cur = row[0]; n = 0
    for v in row:
        if v == cur: n += 1
        else: runs.append((cur, n)); cur = v; n = 1
    runs.append((cur, n))
    # cerca la sequenza: 59 elementi (3+24+5+24+3 barre/spazi) che inizia con una barra
    for i in range(len(runs) - 59):
        seg = runs[i:i+59]
        if not seg[0][0]: continue
        tot = sum(n for _, n in seg); mod = tot/95
        if mod < 3: continue
        bits = ''.join(('1' if b else '0')*max(1, round(n/mod)) for b, n in seg)
        if len(bits) != 95 or bits[:3] != '101' or bits[45:50] != '01010' or bits[-3:] != '101': continue
        try:
            sx, par = [], ''
            for k in range(6):
                c = bits[3+7*k:10+7*k]
                if c in L: sx.append(L[c]); par += 'L'
                else: sx.append(G[c]); par += 'G'
            dx = [Rc[bits[50+7*k:57+7*k]] for k in range(6)]
            codice = str(PAR[par]) + ''.join(map(str, sx + dx))
            risultati.add(codice)
        except KeyError:
            pass
print(','.join(sorted(risultati)) or 'NESSUNO')
