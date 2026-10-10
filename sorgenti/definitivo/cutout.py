import pymupdf, numpy as np, cv2, sys
from PIL import Image
doc=pymupdf.open('/root/.claude/uploads/f3a91526-5260-545e-8804-83615d42bc0d/a7027054-volantino_super_freddo.pdf')
def get_rgb(xref):
    pix=pymupdf.Pixmap(doc,xref)
    if pix.alpha: pix=pymupdf.Pixmap(pix,0)
    if pix.colorspace and pix.colorspace.n!=3: pix=pymupdf.Pixmap(pymupdf.csRGB,pix)
    return np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,pix.n)[...,:3].copy()
def cutout(rgb, up=2, shadow=0.6, strict=False):
    h, w = rgb.shape[:2]
    img = cv2.resize(rgb.astype(np.float32), (w*up, h*up), interpolation=cv2.INTER_LANCZOS4)
    img = np.clip(img, 0, 255); h, w = img.shape[:2]
    mx = img.max(2); mn = img.min(2); lum = img.mean(2)
    neutral = ((((mx - mn) < 26) & (mn > 150)) | ((mn > 212) & ((mx - mn) < 48))) if not strict else (((mn > 236) & ((mx - mn) < 12)) | (((mx - mn) < 20) & (mn > 150) & (mn <= 236)))
    num, lab = cv2.connectedComponents(neutral.astype(np.uint8), connectivity=4)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border)).astype(np.float32)
    bg = cv2.morphologyEx(bg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # soften region boundary (anti-alias)
    bg = cv2.dilate(bg, np.ones((3, 3), np.uint8))
    bgs = cv2.GaussianBlur(bg, (0, 0), 1.0 * up)
    # inside bg: shadow alpha from darkness, colour black
    sh_a = np.clip((255 - lum) / 255 * 1.1 * shadow, 0, 0.42)
    sh_a = np.where(sh_a < 0.03, 0, sh_a)
    sh_a = cv2.GaussianBlur(sh_a.astype(np.float32), (0, 0), 2.5 * up)
    alpha = (1 - bgs) * 1.0 + bgs * sh_a
    colour = img * (1 - bgs[..., None]) + 0 * bgs[..., None]
    # premultiplied -> straight
    pa = (1 - bgs)[..., None]
    F = np.where(alpha[..., None] > 1e-3, img * pa / np.maximum(alpha[..., None], 1e-3), 0)
    # drop specks
    n2, l2, st, _ = cv2.connectedComponentsWithStats((alpha > 0.5).astype(np.uint8))
    keep = np.zeros((h, w), np.float32)
    for i in range(1, n2):
        if st[i, 4] > 0.003 * h * w: keep[l2 == i] = 1
    keep = cv2.dilate(keep, np.ones((int(40 * up) | 1,) * 2, np.uint8))
    alpha *= cv2.GaussianBlur(keep, (0, 0), 6)
    bl = cv2.GaussianBlur(F, (0, 0), 1.1); F = np.clip(F + (F - bl) * 0.45, 0, 255)
    out = np.dstack([F, np.clip(alpha, 0, 1) * 255]).astype(np.uint8)
    im = Image.fromarray(out, 'RGBA'); bb = im.getchannel('A').point(lambda v: 255 if v > 6 else 0).getbbox()
    return im.crop(bb)

if __name__=='__main__':
    for arg in sys.argv[1:]:
        x=int(arg.split(':')[0]); im=cutout(get_rgb(x), strict=arg.endswith(':strict')); im.save(f'cut/x{x}.png')
        bg=Image.new('RGBA',im.size,(30,90,160,255)); bg.alpha_composite(im); bg.convert('RGB').save(f'cut/chk{x}.jpg')
        print(x,im.size)
