# Genera la texture "carta antica" ad alta risoluzione (300 dpi) per le etichette.
import numpy as np, sys
from PIL import Image, ImageFilter
def make(w_mm, h_mm, out, seed, dpi=300):
    rng = np.random.default_rng(seed)
    W, H = int(w_mm/25.4*dpi), int(h_mm/25.4*dpi)
    def blur_noise(scale, amp):
        sw, sh = max(2, W//scale), max(2, H//scale)
        n = Image.fromarray((rng.random((sh, sw))*255).astype('uint8')).resize((W, H), Image.BICUBIC)
        n = n.filter(ImageFilter.GaussianBlur(scale/3))
        a = np.asarray(n, dtype=np.float32)/255.0
        return (a - a.mean()) * amp
    base = np.array([246, 235, 212], dtype=np.float32)          # pergamena
    tone = blur_noise(180, 1.0)*0.55 + blur_noise(60, 1.0)*0.35 + blur_noise(14, 1.0)*0.18
    grain = (rng.random((H, W)).astype(np.float32) - 0.5) * 0.07
    # fibre sottili
    fib = Image.fromarray((rng.random((H//3, W//1))*255).astype('uint8')).resize((W, H)).filter(ImageFilter.GaussianBlur(1.2))
    fib = (np.asarray(fib, np.float32)/255 - 0.5) * 0.10
    yy, xx = np.mgrid[0:H, 0:W]
    dx, dy = (xx/W - 0.5)*2, (yy/H - 0.5)*2
    vign = np.clip((dx**2*0.8 + dy**2) - 0.45, 0, None) * 0.07
    shade = tone*0.12 + grain*0.8 + fib*0.8 - vign
    warm = np.array([1.0, 0.93, 0.80], dtype=np.float32)       # le macchie virano al bruno
    img = base[None, None, :] * (1 + shade[..., None] * warm[None, None, :])
    Image.fromarray(np.clip(img, 0, 255).astype('uint8')).save(out, quality=92, dpi=(dpi, dpi))
make(float(sys.argv[1]), float(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
