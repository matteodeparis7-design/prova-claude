# Render procedurale di una base per pizza romana (pinsa) vista dall'alto, con ombra.
# Uscita: PNG RGBA ad alta risoluzione (~600 dpi alla dimensione di stampa).
import numpy as np, sys
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

def render(out, W=2700, H=1800, seed=21, mode='foto'):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W*0.5, H*0.47
    a, b = W*0.43, H*0.40                         # semiassi ovale
    u, v = (xx-cx)/a, (yy-cy)/b
    r = np.sqrt(u*u + v*v); th = np.arctan2(v, u)
    # bordo irregolare (impasto steso a mano)
    def per_noise(n, k, amp):
        c = rng.normal(0, 1, (k,)); s = rng.normal(0, 1, (k,))
        t = np.zeros_like(th)
        for i in range(1, k+1):
            t += (c[i-1]*np.cos(i*th) + s[i-1]*np.sin(i*th)) / i**1.25
        return t*amp
    edge = 1 + per_noise(0, 9, .018) + per_noise(0, 40, .004)
    # leggera forma "a pala": un lato un po' piu' dritto
    edge *= 1 - .03*np.cos(th)**8
    rr = r/edge
    def noise(scale, amp=1.0):
        n = rng.normal(0, 1, (H//scale + 3, W//scale + 3)).astype(np.float32)
        n = gaussian_filter(n, 1.0)
        z = map_coordinates(n, [yy/scale, xx/scale], order=3, mode='reflect')
        return z/ (z.std()+1e-6) * amp
    n_lo = noise(220); n_mid = noise(60); n_hi = noise(12); n_fine = noise(3)
    # ---- mappa delle altezze
    rim = np.exp(-((rr - .885)/.085)**2)
    rim *= 1 + .18*n_lo + .12*n_mid
    falloff = np.clip((1.0 - rr)/.06, 0, 1)**.6        # bordo arrotondato
    Hm = (.32 + .05*n_lo)*np.clip((1.0-rr)/.15, 0, 1)**.7 + .75*rim*falloff
    # bolle
    bub = np.zeros((H, W), np.float32); top = np.zeros((H, W), np.float32)
    def add_bubble(px, py, rad, hgt):
        x0, x1 = int(max(px-2*rad, 0)), int(min(px+2*rad, W)); y0, y1 = int(max(py-2*rad, 0)), int(min(py+2*rad, H))
        if x1 <= x0 or y1 <= y0: return
        gy, gx = np.mgrid[y0:y1, x0:x1]
        ex = rng.uniform(.75, 1.3)
        d2 = ((gx-px)/(rad*ex))**2 + ((gy-py)/(rad/ex))**2
        dome = np.clip(1 - d2, 0, None)**.75 * hgt
        bub[y0:y1, x0:x1] = np.maximum(bub[y0:y1, x0:x1], dome)
        top[y0:y1, x0:x1] = np.maximum(top[y0:y1, x0:x1], np.clip(1 - d2*2.2, 0, None) * hgt)
    for _ in range(170):                       # bolle del cornicione
        t = rng.uniform(-np.pi, np.pi); rrad = rng.normal(.885, .035)
        px = cx + a*rrad*np.cos(t); py = cy + b*rrad*np.sin(t)
        add_bubble(px, py, rng.uniform(.014, .045)*W, rng.uniform(.14, .40))
    for _ in range(42):                        # bolle sparse al centro (impasto ad alta idratazione)
        t = rng.uniform(-np.pi, np.pi); rrad = np.sqrt(rng.uniform(0, .68))
        px = cx + a*rrad*np.cos(t); py = cy + b*rrad*np.sin(t)
        add_bubble(px, py, rng.uniform(.010, .036)*W, rng.uniform(.06, .20))
    bub *= falloff; top *= falloff
    Hm = Hm + bub
    # fossette (pressione delle dita)
    for _ in range(26):
        t = rng.uniform(-np.pi, np.pi); rrad = np.sqrt(rng.uniform(0, .45))
        px = cx + a*rrad*np.cos(t); py = cy + b*rrad*np.sin(t); rad = rng.uniform(.018, .03)*W
        Hm -= .10*np.exp(-(((xx-px)/rad)**2 + ((yy-py)/(rad*.8))**2)) * (bub < .05)
    Hm += .0035*n_hi + .0012*n_fine + .02*n_mid*np.clip(1-rr, 0, 1)
    Hm = gaussian_filter(Hm, 1.2)
    # ---- illuminazione
    k = 250.0                                  # rilievo
    gy_, gx_ = np.gradient(Hm)
    nx, ny, nz = -gx_*k, -gy_*k, np.ones_like(Hm)
    nl = np.sqrt(nx*nx + ny*ny + nz*nz); nx, ny, nz = nx/nl, ny/nl, nz/nl
    L = np.array([-.45, -.55, .70]); L /= np.linalg.norm(L)
    diff = np.clip(nx*L[0] + ny*L[1] + nz*L[2], 0, 1)
    Hh = L + np.array([0, 0, 1]); Hh /= np.linalg.norm(Hh)
    spec = np.clip(nx*Hh[0] + ny*Hh[1] + nz*Hh[2], 0, 1)**38
    ao = np.clip(1 - (gaussian_filter(Hm, 18) - Hm)*1.8, .62, 1.05)
    # ---- colore (cottura)
    brown = np.clip(.16 + .62*rim + .85*top + .45*bub + .16*n_mid + .08*n_lo + .35*np.clip(rr-.93, 0, 1)/.07, 0, 1.6)
    stops = np.array([[248, 226, 168], [240, 196, 116], [220, 150, 64], [170, 92, 34], [86, 44, 20]], np.float32)
    pos = np.array([0, .35, .7, 1.05, 1.6])
    col = np.stack([np.interp(brown, pos, stops[:, c]) for c in range(3)], -1)
    # macchie di bruciatura "a leopardo" sulle bolle piu' alte
    char = np.clip((top - .30)/.14, 0, 1) * np.clip(.6 + .5*n_hi, 0, 1)
    spots = np.clip((noise(6) - 2.3)/.5, 0, 1) * rim * .65
    charm = np.clip(char + spots, 0, 1)[..., None]
    col = col*(1 - charm*.85) + np.array([48, 28, 18])*charm*.85
    # farina e semola sul bordo
    flour = np.clip((n_fine*.6 + noise(2)*.8 - 1.9), 0, 1) * (np.clip((rr-.8)/.2, 0, 1) + .15) * .45
    col = col*(1 - flour[..., None]) + np.array([248, 240, 222])*flour[..., None]
    shade = (.66 + .44*diff)*ao
    rgb = col*shade[..., None] + 255*spec[..., None]*.18*(1 - charm)
    # ---- alpha + ombra
    alpha = np.clip((1.0 - rr)/.004, 0, 1)
    sh = gaussian_filter(np.clip((1.0 - rr)/.004, 0, 1), 38)
    sh = np.roll(np.roll(sh, 26, 0), 16, 1) * .5
    sh2 = gaussian_filter(alpha, 7); sh2 = np.roll(sh2, 7, 0)*.35
    sha = np.clip(sh + sh2, 0, .62)
    shadow_col = np.array([70, 40, 22], np.float32)
    A = alpha + sha*(1 - alpha)
    out_rgb = (rgb*alpha[..., None] + shadow_col*(sha*(1-alpha))[..., None]) / np.maximum(A, 1e-4)[..., None]
    if mode == 'incisione':
        return incisione(out, rgb, alpha, Hm, rr, th, xx, yy, cx, cy, a, b, charm[..., 0], n_mid)
    img = np.dstack([np.clip(out_rgb, 0, 255), A*255]).astype(np.uint8)
    Image.fromarray(img, 'RGBA').save(out, optimize=True)


def incisione(out, rgb, alpha, Hm, rr, th, xx, yy, cx, cy, a, b, charm, n_mid, ink=(92, 36, 22)):
    """Trasforma il render in un'incisione a tratteggio (stile acquaforte)."""
    lum = (rgb[..., 0]*.3 + rgb[..., 1]*.55 + rgb[..., 2]*.15)/255.0
    tone = np.clip((0.86 - lum)/0.62, 0, 1)                 # 0 = carta, 1 = inchiostro pieno
    tone = np.clip(tone + .55*charm, 0, 1)**1.25
    # tratteggio 1: linee che seguono la forma (ellissi concentriche deformate dal rilievo)
    ph1 = (yy + .16*(xx-cx)**2/a - .10*(yy-cy)**2/b)/8.6 + Hm*3.2 + n_mid*.06
    d1 = np.abs((ph1 % 1) - .5)*2                            # 0 al centro della linea
    w1 = np.clip(tone*1.0, 0, .92)
    l1 = np.clip((w1 - d1)/.14 + .5, 0, 1)*(tone > .05)
    # tratteggio 2: incrociato nelle ombre (diagonale, piegato dal rilievo)
    ph2 = (xx*.62 - yy*.78)/9.4 + Hm*2.5
    d2 = np.abs((ph2 % 1) - .5)*2
    w2 = np.clip((tone - .58)*1.6, 0, .8)
    l2 = np.clip((w2 - d2)/.12 + .5, 0, 1)
    # puntinato nelle mezzetinte chiare
    rng = np.random.default_rng(3)
    dots = (rng.random(tone.shape) < np.clip(tone*.05, 0, .05)).astype(np.float32)
    # contorni: bordo della pinsa e profili delle bolle
    gy, gx = np.gradient(gaussian_filter(Hm, 1.6))
    edge = np.clip(np.hypot(gx, gy)*80 - .75, 0, 1)*np.clip((gx*.45 + gy*.55)*400 + .2, 0, 1)
    rim_line = np.clip(1 - np.abs(rr - .995)/.006, 0, 1)
    inkm = np.clip(np.maximum.reduce([l1, l2, dots*.8, edge*.85, rim_line]), 0, 1)*alpha
    # ombra portata a tratteggio orizzontale sotto la pinsa
    sh = gaussian_filter((rr < 1).astype(np.float32), 30); sh = np.roll(np.roll(sh, 30, 0), 18, 1)*(1 - alpha)
    ph3 = yy/10.0; d3 = np.abs((ph3 % 1) - .5)*2
    l3 = np.clip((np.clip(sh*.75, 0, .6) - d3)/.12 + .5, 0, 1)*(sh > .08)
    inkm = np.maximum(inkm, l3*.9)
    img = np.zeros(inkm.shape + (4,), np.uint8)
    img[..., 0], img[..., 1], img[..., 2] = ink
    img[..., 3] = np.clip(inkm*255, 0, 255).astype(np.uint8)
    Image.fromarray(img, 'RGBA').save(out, optimize=True)

modo = sys.argv[3] if len(sys.argv) > 3 else 'foto'
render(sys.argv[1], seed=int(sys.argv[2]) if len(sys.argv) > 2 else 21, mode=modo)
