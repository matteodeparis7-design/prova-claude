# Genera le illustrazioni vettoriali (stile incisione seppia) usate nelle etichette:
#   assets/skyline_roma.svg  -> Colosseo con pini e cupola di San Pietro
#   assets/alloro_sx.svg     -> ramo d'alloro (quello destro e' lo specchio)
import math, random
random.seed(4)
C_FILL, C_SHADE, C_LINE, C_FAR = '#E3CFAC', '#B38E61', '#6E5133', '#EADBC0'
f = lambda v: f'{v:.2f}'

def arco(a, b, base, top, ry, fill, line, sw=.12):
    rx = (b - a)/2; spring = top + ry
    return (f'<path d="M{f(a)},{f(base)} L{f(a)},{f(spring)} A{f(rx)},{f(ry)} 0 0 1 {f(b)},{f(spring)} L{f(b)},{f(base)} Z" '
            f'fill="{fill}" stroke="{line}" stroke-width="{sw}"/>')

def colosseo(cx, ground, R):
    out = []
    tiers = [6.0, 5.5, 5.3]; attic = 4.6
    tops = [ground - sum(tiers[:i+1]) for i in range(3)]
    top_attic = tops[2] - attic
    N = 24
    th = [math.radians(-82 + 164*i/N) for i in range(N+1)]
    xs = [cx + R*math.sin(t) for t in th]
    rk = 6                                   # campate crollate dell'anello esterno (lato sinistro)
    # --- anello interno, visibile nella parte crollata
    xi0, xi1 = xs[0] + 2.2, xs[rk] + 1.0
    it = tops[2] + 0.8
    prof_in = [(xi0, ground), (xi0, tops[1] + 1.0), (xi0 + 1.6, tops[1] - .4), (xi0 + 2.6, tops[2] + 2.6),
               (xi0 + 5.0, tops[2] + 1.9), (xi0 + 6.2, it), (xi1, it), (xi1, ground)]
    out.append('<path d="M' + ' L'.join(f'{f(x)},{f(y)}' for x, y in prof_in) + f' Z" fill="#D2B78E" stroke="{C_LINE}" stroke-width=".18"/>')
    ni = 7
    for i in range(ni):
        a = xi0 + (xi1 - xi0)*i/ni + .45; b = xi0 + (xi1 - xi0)*(i+1)/ni - .45
        if i >= 1:
            out.append(arco(a, b, tops[1] - .6, tops[2] + 3.0 if i >= 3 else tops[1] - 2.2, .9, C_SHADE, C_LINE, .08))
    # --- sagoma dell'anello esterno: gradoni della rovina, contrafforte, poi integra
    prof = [(xs[0], ground), (xs[0], tops[0] + .2), (xs[1] - .4, tops[0] - .5), (xs[1] + .3, tops[1] + 2.4),
            (xs[2] - .2, tops[1] + 1.5), (xs[3] + .4, tops[1] + .2), (xs[4], tops[1]), (xs[rk] - 2.6, tops[1]),
            (xs[rk] - .3, top_attic), (xs[-1], top_attic), (xs[-1], ground)]
    d = 'M' + ' L'.join(f'{f(x)},{f(y)}' for x, y in prof) + ' Z'
    out.append(f'<path d="{d}" fill="{C_FILL}"/>')
    # cornici
    for k, y in enumerate(tops):
        x0 = xs[0] if k == 0 else (xs[3] if k == 1 else xs[rk] - .9)
        out.append(f'<line x1="{f(x0)}" y1="{f(y)}" x2="{f(xs[-1])}" y2="{f(y)}" stroke="{C_LINE}" stroke-width=".3"/>')
        out.append(f'<line x1="{f(x0)}" y1="{f(y+.5)}" x2="{f(xs[-1])}" y2="{f(y+.5)}" stroke="{C_LINE}" stroke-width=".1"/>')
    out.append(f'<line x1="{f(xs[rk]-.2)}" y1="{f(top_attic+.55)}" x2="{f(xs[-1])}" y2="{f(top_attic+.55)}" stroke="{C_LINE}" stroke-width=".12"/>')
    for i in range(N):
        cosv = math.cos((th[i] + th[i+1])/2)
        pw = .55*cosv + .18
        a, b = xs[i] + pw/2, xs[i+1] - pw/2
        m = (a + b)/2
        for k in range(3):
            if k == 2 and i < rk: continue
            if k == 1 and i < 1: continue
            if k == 1 and i < 3:
                continue
            base = ground if k == 0 else tops[k-1] - .75
            out.append(arco(a, b, base, tops[k] + .85, 1.25, C_SHADE, C_LINE))
            if cosv > .3:      # luce nell'arco: si intravede il fornice successivo
                w = (b - a)
                out.append(arco(m + w*.08, b - w*.12, base, tops[k] + 2.6, .8, C_FILL, 'none', 0).replace('/>', ' opacity=".5"/>'))
            if k > 0:
                out.append(f'<line x1="{f(a)}" y1="{f(base-.75)}" x2="{f(b)}" y2="{f(base-.75)}" stroke="{C_LINE}" stroke-width=".08"/>')
        for k in range(3):
            if k == 2 and i < rk: continue
            if k == 1 and i < 3: continue
            y0 = ground if k == 0 else tops[k-1]
            out.append(f'<line x1="{f(xs[i])}" y1="{f(y0)}" x2="{f(xs[i])}" y2="{f(tops[k]+.5)}" stroke="{C_LINE}" stroke-width="{f(.12+.12*cosv)}"/>')
        if i >= rk:
            out.append(f'<line x1="{f(xs[i])}" y1="{f(tops[2])}" x2="{f(xs[i])}" y2="{f(top_attic+.55)}" stroke="{C_LINE}" stroke-width=".11"/>')
            if i % 2 == 1:
                w = (b - a)*.4
                out.append(f'<rect x="{f(m-w/2)}" y="{f(tops[2]-2.9)}" width="{f(w)}" height="1.5" fill="{C_SHADE}" stroke="{C_LINE}" stroke-width=".08"/>')
            for s in (.3, .7):
                x = xs[i] + (xs[i+1]-xs[i])*s
                out.append(f'<line x1="{f(x)}" y1="{f(top_attic+.9)}" x2="{f(x)}" y2="{f(top_attic+1.5)}" stroke="{C_LINE}" stroke-width=".1"/>')
    # rotondita': ombra graduale verso i bordi del cilindro
    out.insert(0, '<defs><linearGradient id="cil" x1="0" x2="1"><stop offset="0" stop-color="#5a4128" stop-opacity=".30"/>'
               '<stop offset=".22" stop-color="#5a4128" stop-opacity="0"/><stop offset=".7" stop-color="#5a4128" stop-opacity="0"/>'
               '<stop offset="1" stop-color="#5a4128" stop-opacity=".38"/></linearGradient></defs>')
    out.append(f'<path d="{d}" fill="url(#cil)"/>')
    out.append(f'<path d="{d}" fill="none" stroke="{C_LINE}" stroke-width=".3" stroke-linejoin="round"/>')
    return out

def pino(x, ground, h, w, lean, col):
    out = []
    tx = x + lean
    top = ground - h
    trunk = (f'M{f(x-.55)},{f(ground)} C{f(x-.4)},{f(ground-h*.45)} {f(tx-.6)},{f(top+h*.25)} {f(tx-.25)},{f(top+1.2)} '
             f'L{f(tx+.25)},{f(top+1.2)} C{f(tx+.1)},{f(top+h*.25)} {f(x+.45)},{f(ground-h*.45)} {f(x+.6)},{f(ground)} Z')
    out.append(f'<path d="{trunk}" fill="{col}"/>')
    # rami
    out.append(f'<path d="M{f(tx-.1)},{f(top+1.8)} q{f(-w*.18)},-0.6 {f(-w*.3)},-1.2 M{f(tx)},{f(top+1.6)} q{f(w*.2)},-0.5 {f(w*.32)},-1.3" stroke="{col}" stroke-width=".35" fill="none" stroke-linecap="round"/>')
    blobs = []
    for k in range(14):
        u = -1 + 2*k/13
        bx = tx + u*w/2
        by = top - 0.4 - (1 - u*u)*1.3 + random.uniform(-.25, .25)
        rx = random.uniform(1.5, 2.2); ry = random.uniform(.85, 1.2)
        blobs.append(f'<ellipse cx="{f(bx)}" cy="{f(by)}" rx="{f(rx)}" ry="{f(ry)}"/>')
    out.append(f'<g fill="{col}">' + ''.join(blobs) + '</g>')
    # luce sulle chiome
    for k in range(9):
        u = -0.9 + 1.8*k/8
        bx = tx + u*w/2; by = top + .55 - (1-u*u)*1.2
        out.append(f'<ellipse cx="{f(bx)}" cy="{f(by)}" rx="1.5" ry=".45" fill="#6E5133" opacity=".55"/>')
    for k in range(6):
        u = -0.75 + 1.5*k/5
        bx = tx + u*w/2; by = top - .95 - (1-u*u)*1.25
        out.append(f'<path d="M{f(bx-.9)},{f(by)} q.9,-.55 1.8,0" stroke="#B89A72" stroke-width=".16" fill="none"/>')
    return out

def cipresso(x, ground, h, col):
    d = (f'M{f(x)},{f(ground-h)} C{f(x+1.3)},{f(ground-h*.7)} {f(x+1.5)},{f(ground-h*.25)} {f(x+.3)},{f(ground)} '
         f'L{f(x-.3)},{f(ground)} C{f(x-1.5)},{f(ground-h*.25)} {f(x-1.3)},{f(ground-h*.7)} {f(x)},{f(ground-h)} Z')
    return [f'<path d="{d}" fill="{col}"/>']

def cupola(x, ground, col):
    o = []
    o.append(f'<rect x="{f(x-6)}" y="{f(ground-4)}" width="12" height="4" fill="{col}"/>')
    o.append(f'<rect x="{f(x-4.2)}" y="{f(ground-7)}" width="8.4" height="3.2" fill="{col}"/>')
    for k in range(7):
        xx = x - 3.6 + k*1.2
        o.append(f'<rect x="{f(xx-.25)}" y="{f(ground-6.6)}" width=".5" height="2.2" fill="{C_FILL}" opacity=".8"/>')
    o.append(f'<path d="M{f(x-4)},{f(ground-7)} C{f(x-4)},{f(ground-12)} {f(x+4)},{f(ground-12)} {f(x+4)},{f(ground-7)} Z" fill="{col}"/>')
    for k in (-2.4, -1.2, 0, 1.2, 2.4):
        o.append(f'<path d="M{f(x+k)},{f(ground-7)} Q{f(x+k*.8)},{f(ground-10.5)} {f(x)},{f(ground-10.9)}" stroke="{C_FILL}" stroke-width=".12" fill="none"/>')
    o.append(f'<rect x="{f(x-.8)}" y="{f(ground-12.6)}" width="1.6" height="1.8" fill="{col}"/>')
    o.append(f'<path d="M{f(x-.7)},{f(ground-12.6)} Q{f(x)},{f(ground-13.6)} {f(x+.7)},{f(ground-12.6)} Z" fill="{col}"/>')
    o.append(f'<line x1="{f(x)}" y1="{f(ground-13.4)}" x2="{f(x)}" y2="{f(ground-15)}" stroke="{col}" stroke-width=".25"/>')
    o.append(f'<line x1="{f(x-.5)}" y1="{f(ground-14.5)}" x2="{f(x+.5)}" y2="{f(ground-14.5)}" stroke="{col}" stroke-width=".2"/>')
    return o

def skyline():
    W, H = 112, 27
    g = H - 1.2
    parts = []
    parts += cupola(95, g, '#DCC6A1')
    parts += cipresso(22.5, g, 12.5, '#A3835B')
    parts += cipresso(104, g, 10.5, '#A3835B')
    parts += colosseo(56.5, g, 34)
    parts += pino(7.5, g, 15.5, 15, 2.0, '#8C6B46')
    parts += pino(17, g, 9.5, 9, -1.0, '#A3835B')
    parts += pino(106, g, 14, 12.5, -2.2, '#8C6B46')
    # terreno
    gl = f'M0,{f(g)} ' + ' '.join(f'L{f(x)},{f(g + .25*math.sin(x*.7))}' for x in [i*1.5 for i in range(1, 76)])
    parts.append(f'<path d="{gl} L{W},{H} L0,{H} Z" fill="{C_FILL}"/>')
    parts.append(f'<path d="{gl}" stroke="{C_LINE}" stroke-width=".3" fill="none"/>')
    for i in range(40):
        x = random.uniform(1, W-1)
        parts.append(f'<line x1="{f(x)}" y1="{f(g+.6+random.uniform(0,.4))}" x2="{f(x+random.uniform(1,2.5))}" y2="{f(g+.6+random.uniform(0,.4))}" stroke="{C_LINE}" stroke-width=".08" opacity=".6"/>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}mm" height="{H}mm">' + ''.join(parts) + '</svg>'
    open('assets/skyline_roma.svg', 'w').write(svg)

def alloro():
    # ramo che cresce verso destra, foglie a coppie
    W, H = 30, 12
    o = []
    stem = 'M1,8.5 Q12,9.6 28.5,5.2'
    o.append(f'<path d="{stem}" stroke="#7E5E3B" stroke-width=".35" fill="none" stroke-linecap="round"/>')
    def q(t):
        x = (1-t)**2*1 + 2*(1-t)*t*12 + t*t*28.5
        y = (1-t)**2*8.5 + 2*(1-t)*t*9.6 + t*t*5.2
        dx = 2*(1-t)*(12-1) + 2*t*(28.5-12); dy = 2*(1-t)*(9.6-8.5) + 2*t*(5.2-9.6)
        return x, y, math.degrees(math.atan2(dy, dx))
    n = 8
    for k in range(n):
        t = 0.1 + 0.85*k/(n-1)
        x, y, a = q(t)
        s = 1.0 - 0.45*t
        for side, rot in ((1, -42), (-1, 38)):
            L, Wd = 4.6*s, 1.5*s
            col = '#8C6B46' if side > 0 else '#A3835B'
            o.append(f'<g transform="translate({f(x)},{f(y)}) rotate({f(a+rot)})">'
                     f'<path d="M0,0 C{f(L*.3)},{f(-Wd)} {f(L*.75)},{f(-Wd*.9)} {f(L)},0 C{f(L*.75)},{f(Wd*.9)} {f(L*.3)},{f(Wd)} 0,0 Z" fill="{col}"/>'
                     f'<line x1="{f(L*.1)}" y1="0" x2="{f(L*.85)}" y2="0" stroke="#EADBC0" stroke-width=".1"/></g>')
    x, y, a = q(1.0)
    o.append(f'<g transform="translate({f(x)},{f(y)}) rotate({f(a)})"><path d="M0,0 C1.2,-1 2.8,-.9 3.6,0 C2.8,.9 1.2,1 0,0 Z" fill="#8C6B46"/></g>')
    for t in (.3, .58):
        bx, by, _ = q(t)
        o.append(f'<circle cx="{f(bx+.4)}" cy="{f(by+1.1)}" r=".62" fill="#8E3A26"/>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}mm" height="{H}mm">' + ''.join(o) + '</svg>'
    open('assets/alloro.svg', 'w').write(svg)

skyline(); alloro()
