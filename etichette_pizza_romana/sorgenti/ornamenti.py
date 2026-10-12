# Ornamenti vettoriali per le etichette:
#   assets/corona_alloro.svg  -> corona d'alloro aperta in alto (due rami che si incontrano in basso)
import math
f = lambda v: f'{v:.3f}'

def corona(out, foglia='#A97A36', foglia2='#C39552', ramo='#8A5F28', bacca='#7B2A1E', R=17.0, a0=100, a1=206, n=10, vb=None, leaf=1.0):
    W = 2*R + 12; H = R + 14
    cx, cy = W/2, 3.5            # centro del cerchio: la corona occupa la meta' inferiore + un po'
    o = []
    for lato in (-1, 1):
        def P(a):  # punto sul ramo; a in gradi, 90 = in basso
            r = math.radians(a)
            x = cx + lato*R*math.cos(r) * -1 if False else cx - lato*R*math.cos(math.radians(180-a))*-1
            return x, cy + R*math.sin(r)
        pts = []
        for k in range(41):
            a = a0 + (a1-a0)*k/40
            r = math.radians(a)
            x = cx + R*math.cos(r)*(1 if lato < 0 else -1)
            y = cy + R*math.sin(r)
            pts.append((x, y))
        # ramo: assottigliato verso la punta
        d = 'M' + ' L'.join(f'{f(x)},{f(y)}' for x, y in pts)
        o.append(f'<path d="{d}" fill="none" stroke="{ramo}" stroke-width=".42" stroke-linecap="round"/>')
        for k in range(n):
            t = (k + .6)/(n + .2)
            a = a0 + (a1-a0)*t
            r = math.radians(a)
            sx = (1 if lato < 0 else -1)
            x = cx + R*math.cos(r)*sx; y = cy + R*math.sin(r)
            # direzione di crescita
            tx, ty = -math.sin(r)*sx, math.cos(r)
            ang = math.degrees(math.atan2(ty, tx))
            s = 1.0 - .38*t
            L, Wd = 5.4*s*leaf, 1.75*s*leaf
            for verso, rot, col in ((1, -38, foglia), (-1, 34, foglia2)):
                # foglia esterna (verso il fuori del cerchio) e interna
                rr = rot if lato < 0 else -rot
                o.append(f'<g transform="translate({f(x)},{f(y)}) rotate({f(ang + rr)})">'
                         f'<path d="M0,0 C{f(L*.28)},{f(-Wd)} {f(L*.72)},{f(-Wd*.95)} {f(L)},0 C{f(L*.72)},{f(Wd*.95)} {f(L*.28)},{f(Wd)} 0,0Z" fill="{col}"/>'
                         f'<path d="M{f(L*.12)},0 L{f(L*.86)},0" stroke="#F4E8D0" stroke-width=".12" opacity=".75"/></g>')
            if k in (2, 5):
                bx, by = x + math.cos(r)*sx*1.5, y + math.sin(r)*1.5
                o.append(f'<circle cx="{f(bx)}" cy="{f(by)}" r=".72" fill="{bacca}"/>')
        # foglia di punta
        a = math.radians(a1); sx = (1 if lato < 0 else -1)
        x = cx + R*math.cos(a)*sx; y = cy + R*math.sin(a)
        ang = math.degrees(math.atan2(math.cos(a), -math.sin(a)*sx))
        o.append(f'<g transform="translate({f(x)},{f(y)}) rotate({f(ang)})"><path d="M0,0 C1.2,-1.1 3,-1 4,0 C3,1 1.2,1.1 0,0Z" fill="{foglia}"/></g>')
    # nastro che lega i rami
    bx, by = cx, cy + R + .3
    o.append(f'<path d="M{f(bx-.2)},{f(by)} C{f(bx-2.6)},{f(by-2.2)} {f(bx-4.4)},{f(by-.4)} {f(bx-3.2)},{f(by+.9)} C{f(bx-2.2)},{f(by+1.8)} {f(bx-.9)},{f(by+.7)} {f(bx-.2)},{f(by)}Z" fill="{bacca}"/>')
    o.append(f'<path d="M{f(bx+.2)},{f(by)} C{f(bx+2.6)},{f(by-2.2)} {f(bx+4.4)},{f(by-.4)} {f(bx+3.2)},{f(by+.9)} C{f(bx+2.2)},{f(by+1.8)} {f(bx+.9)},{f(by+.7)} {f(bx+.2)},{f(by)}Z" fill="{bacca}"/>')
    o.append(f'<path d="M{f(bx-.5)},{f(by+.4)} L{f(bx-2.6)},{f(by+4.4)} L{f(bx-1.6)},{f(by+4.0)} L{f(bx-1.2)},{f(by+5.0)} L{f(bx+.1)},{f(by+.8)}Z" fill="{bacca}"/>')
    o.append(f'<path d="M{f(bx+.5)},{f(by+.4)} L{f(bx+2.8)},{f(by+4.2)} L{f(bx+1.7)},{f(by+3.9)} L{f(bx+1.5)},{f(by+4.9)} L{f(bx-.1)},{f(by+.8)}Z" fill="{bacca}"/>')
    o.append(f'<ellipse cx="{f(bx)}" cy="{f(by+.25)}" rx=".95" ry=".8" fill="{bacca}"/>')
    # ritaglio: solo da y>=0
    x0, y0, vw, vh = vb if vb else (0, -9, W, H + 9)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{f(x0)} {f(y0)} {f(vw)} {f(vh)}" width="{f(vw)}mm" height="{f(vh)}mm">' + ''.join(o) + '</svg>'
    open(out, 'w').write(svg)
    return W, H + 9

corona('assets/corona_alloro.svg')
# ghirlanda ribassata da mettere sotto il nome del prodotto
corona('assets/ghirlanda.svg', R=38, a0=91.2, a1=140, n=9, vb=(5, 18.5, 78, 29.5), leaf=.92)
