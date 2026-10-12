# Calcola gli ingombri reali dei pixel e le distanze (mm) per controllo_spazi.js
import json, sys
import numpy as np
from PIL import Image
SOGLIA = 2.0
ACCOSTAMENTI_VOLUTI = {('nastro artigianale', 'panorama'), ('fregio inferiore', 'panorama'), ('cornice', 'logo')}
dati = json.load(open(sys.argv[1]))
for pag, lista in dati.items():
    W, H = (150, 100) if pag == 'fronte' else (130, 88)
    box = {}
    for nome, f in lista:
        a = np.asarray(Image.open(f))[..., 3]
        ys, xs = np.nonzero(a > 40)
        if len(xs) == 0: continue
        sx, sy = W / a.shape[1], H / a.shape[0]
        box[nome] = (xs.min()*sx, ys.min()*sy, (xs.max()+1)*sx, (ys.max()+1)*sy, a > 40, sx)
    print(f'\n=== {pag.upper()} ({W} × {H} mm) – misure sull\'inchiostro reale ===')
    nomi = list(box)
    def gap(n1, n2):
        x0, y0, x1, y1, m1, s = box[n1]; X0, Y0, X1, Y1, m2, _ = box[n2]
        dx = max(X0 - x1, x0 - X1); dy = max(Y0 - y1, y0 - Y1)
        if dx >= 0 or dy >= 0: return max(dx, dy)
        # rettangoli sovrapposti: verifica l'inchiostro reale (distanza minima tra pixel)
        if (m1 & m2).any(): return -0.01
        from scipy.ndimage import distance_transform_edt
        d = distance_transform_edt(~m1)
        return float(d[m2].min()) * s
    problemi = 0
    for i, a in enumerate(nomi):
        x0, y0, x1, y1, _, _ = box[a]
        if a not in ('cornice', 'fregio superiore', 'fregio inferiore', 'panorama'):
            bordo = min(x0, y0, W - x1, H - y1)
            print(f"{'⚠️ ' if bordo < 3 else '✅ '}{a}: distanza dal bordo di taglio {bordo:.2f} mm (zona di sicurezza 3 mm)")
        for b in nomi[i+1:]:
            g = gap(a, b)
            if g > 6: continue
            if (a, b) in ACCOSTAMENTI_VOLUTI or (b, a) in ACCOSTAMENTI_VOLUTI:
                print(f'ℹ️  {a} ↔ {b}: {g:.2f} mm (accostamento voluto)'); continue
            ok = g >= SOGLIA
            problemi += not ok
            print(f"{'✅ ' if ok else '⚠️ '}{a} ↔ {b}: {g:.2f} mm")
    print(f'--> {problemi} accostamenti sotto {SOGLIA} mm')
