import pymupdf, numpy as np
from PIL import Image
PDF='/root/.claude/uploads/f3a91526-5260-545e-8804-83615d42bc0d/a7027054-volantino_super_freddo.pdf'
doc=pymupdf.open(PDF)
def render(pn,rect,z):
    pix=doc[pn].get_pixmap(matrix=pymupdf.Matrix(z,z),clip=pymupdf.Rect(*rect))
    return np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).astype(np.float32)
def unmix(img,bg):
    bg=np.array(bg,np.float32)
    d=img-bg
    denom=np.where(d>=0,255-bg,bg)
    a=np.clip(np.max(np.abs(d)/np.maximum(denom,1),axis=2),0,1)
    F=bg+d/np.maximum(a[...,None],1e-3)
    F=np.clip(F,0,255)
    out=np.dstack([F,a*255]).astype(np.uint8)
    im=Image.fromarray(out,'RGBA'); return im.crop(im.getbbox())
# sample navy
s=render(0,(280,5,300,25),2); bg=s.reshape(-1,3).mean(0); print('navy',bg)
unmix(render(0,(30,32,180,116),12),bg).save('assets/logo_deco20.png')
unmix(render(0,(8,116.5,256,192),12),bg).save('assets/logo_superfreddo.png')
unmix(render(0,(262,8,592,108),10),bg).save('assets/logo_concorso.png')
# white-bg deco logo from page footer
s=render(1,(8,758,58,795.5),12)
unmix(s,(255,255,255)).save('assets/logo_deco_footer.png')
