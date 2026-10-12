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

# ---------------------------------------------------------------- nuovi soggetti
def colline(W, ground):
    pts = [(0, ground)]
    for i in range(0, 61):
        x = W*i/60
        y = ground - 3.2 - 1.6*math.sin(x*.09 + .6) - 1.0*math.sin(x*.23 + 1.7) - .5*math.sin(x*.55)
        pts.append((x, y))
    pts.append((W, ground))
    d = 'M' + ' L'.join(f'{f(x)},{f(y)}' for x, y in pts) + 'Z'
    return [f'<path d="{d}" fill="#EFE2C8"/>',
            '<path d="' + 'M' + ' L'.join(f'{f(x)},{f(y)}' for x, y in pts[1:-1]) + f'" fill="none" stroke="{C_FAR}" stroke-width=".25"/>']

def acquedotto(x0, x1, ground, h0, h1, n=11, rotte=(3,)):
    """Acquedotto romano (tipo Aqua Claudia) che si allontana in prospettiva da sinistra a destra.
    Muro continuo con fornici alti e stretti, canale in sommita', una campata crollata."""
    o = []
    q = (h1/h0)**(1/n)
    span0 = (x1 - x0)*(1 - q)/(1 - q**n)
    xs = [x0]; sp = span0
    for i in range(n):
        xs.append(xs[-1] + sp); sp *= q
    H = lambda x: h0 + (h1 - h0)*(x - x0)/(x1 - x0)          # altezza lineare: prospettiva
    hh = [H(x) for x in xs]
    pw = [(xs[min(i+1, n)] - xs[max(i-1, 0)])/2*.30 for i in range(n+1)]   # spessore piloni
    top = lambda x: ground - H(x)
    ch = lambda x: H(x)*.12
    # ---- sagoma esterna (con la campata crollata)
    P = [(xs[0]-pw[0]/2, ground), (xs[0]-pw[0]/2, top(xs[0]-pw[0]/2))]
    for i in range(n):
        a_, b_ = xs[i], xs[i+1]
        if i in rotte:
            ra = a_ + pw[i]/2; rb = b_ - pw[i+1]/2
            P += [(ra, top(ra) + ch(ra)*1.4), (ra + .15, top(ra) + ch(ra)*2.6), (ra - .05, top(ra) + H(ra)*.36), (ra + .25, top(ra) + H(ra)*.5),
                  (ra, ground), (rb, ground), (rb - .2, top(rb) + H(rb)*.42), (rb + .1, top(rb) + H(rb)*.3),
                  (rb - .1, top(rb) + ch(rb)*1.9), (rb + .2, top(rb) + ch(rb)*.8)]
        P.append((b_ + (pw[i+1]/2 if i == n-1 else 0), top(b_ + (pw[i+1]/2 if i == n-1 else 0))))
    P.append((xs[n] + pw[n]/2, ground))
    outer = 'M' + ' L'.join(f'{f(x)},{f(y)}' for x, y in P) + 'Z'
    holes = []; shade = []
    for i in range(n):
        if i in rotte: continue
        a_, b_ = xs[i] + pw[i]/2, xs[i+1] - pw[i+1]/2
        rx = (b_ - a_)/2; mx = (a_ + b_)/2
        crown = top(mx) + ch(mx)*1.7
        spring = crown + rx
        holes.append(f'M{f(a_)},{f(ground)} L{f(a_)},{f(spring)} A{f(rx)},{f(rx)} 0 0 1 {f(b_)},{f(spring)} L{f(b_)},{f(ground)}Z')
        # faccia interna del pilone di destra (si vede per la fuga prospettica) e intradosso
        t = rx*.55
        shade.append(f'<path d="M{f(b_-t)},{f(ground)} L{f(b_-t)},{f(spring+rx*.15)} Q{f(b_-t*.3)},{f(spring-rx*.55)} {f(b_)},{f(spring-.05)} L{f(b_)},{f(ground)}Z" fill="{C_SHADE}" opacity=".85"/>')
        shade.append(f'<path d="M{f(a_)},{f(spring)} A{f(rx)},{f(rx)} 0 0 1 {f(b_)},{f(spring)} L{f(b_-t)},{f(spring+rx*.15)} A{f(rx-t*.5)},{f(rx*.82)} 0 0 0 {f(a_+.05)},{f(spring+.05)}Z" fill="{C_SHADE}" opacity=".55"/>')
    o.append(f'<path d="{outer} {" ".join(holes)}" fill="{C_FILL}" fill-rule="evenodd"/>')
    o += shade
    # corsi dei blocchi sui piloni vicini
    for i in range(n+1):
        x = xs[i]; h = H(x)
        if h < 11: continue
        for k in range(1, 9):
            yy = ground - h*.62*k/9
            o.append(f'<line x1="{f(x-pw[i]/2)}" y1="{f(yy)}" x2="{f(x+pw[i]/2)}" y2="{f(yy)}" stroke="{C_LINE}" stroke-width=".06" opacity=".6"/>')
    # cornice del canale (specus)
    segs = []
    for i in range(n):
        if i in rotte: continue
        xa = xs[i] - (pw[i]/2 if i == 0 or (i-1) in rotte else 0); xb = xs[i+1] + (pw[i+1]/2 if i == n-1 or (i+1) in rotte else 0)
        if i in [r+1 for r in rotte]: xa = xs[i] - pw[i]/2
        if i in [r-1 for r in rotte]: xb = xs[i+1] + pw[i+1]/2
        segs.append(f'M{f(xa)},{f(top(xa)+ch(xa))} L{f(xb)},{f(top(xb)+ch(xb))}')
    o.append(f'<path d="{" ".join(segs)}" stroke="{C_LINE}" stroke-width=".12" fill="none"/>')
    o.append(f'<path d="{outer} {" ".join(holes)}" fill="none" stroke="{C_LINE}" stroke-width=".24" stroke-linejoin="round"/>')
    # ciuffi d'erba sul rudere
    for r in rotte:
        for x in (xs[r] + pw[r]/2 - .1, xs[r+1] - pw[r+1]/2 + .1):
            y = top(x) + ch(x)*1.2
            o.append(f'<path d="M{f(x-.7)},{f(y)} q.3,-1.1 .6,0 q.3,-1.3 .6,0 q.3,-1 .6,0" stroke="#7E6A3C" stroke-width=".13" fill="none"/>')
    return o

def tempio_castori(x, ground, h=20.5):
    """Le tre colonne corinzie del Tempio dei Castori al Foro Romano, su rudere del podio."""
    o = []
    pod = 4.2; ent = 2.6; colh = h - pod - ent
    # podio in rovina (opus caementicium)
    pts = [(x-1.2, ground), (x-1.4, ground-pod+.6), (x+1.5, ground-pod), (x+9.5, ground-pod), (x+11.2, ground-pod+.8), (x+11.6, ground)]
    o.append('<path d="M' + ' L'.join(f'{f(a)},{f(b)}' for a, b in pts) + f'Z" fill="{C_SHADE}" opacity=".85" stroke="{C_LINE}" stroke-width=".18"/>')
    for k in range(4):
        yy = ground - pod*(k+.5)/4
        o.append(f'<path d="M{f(x-1)},{f(yy)} h{f(random.uniform(2,4))} m1,0 h{f(random.uniform(2,4))}" stroke="{C_LINE}" stroke-width=".07" opacity=".7"/>')
    base = ground - pod
    cx = [x+1.6, x+5.1, x+8.6]
    for c in cx:
        w0, w1 = 1.55, 1.3
        o.append(f'<path d="M{f(c-w0/2)},{f(base-.5)} L{f(c-w1/2)},{f(base-colh+1.6)} L{f(c+w1/2)},{f(base-colh+1.6)} L{f(c+w0/2)},{f(base-.5)}Z" fill="{C_FILL}" stroke="{C_LINE}" stroke-width=".14"/>')
        for k in (-.25, 0, .25):
            o.append(f'<line x1="{f(c+k*w0)}" y1="{f(base-.7)}" x2="{f(c+k*w1)}" y2="{f(base-colh+1.8)}" stroke="{C_LINE}" stroke-width=".06"/>')
        o.append(f'<path d="M{f(c-w0/2-.35)},{f(base)} h{f(w0+.7)} v-.5 h{f(-w0-.7)}Z" fill="{C_FILL}" stroke="{C_LINE}" stroke-width=".1"/>')
        # capitello corinzio
        yc = base - colh + 1.6
        o.append(f'<path d="M{f(c-w1/2)},{f(yc)} C{f(c-w1/2-.2)},{f(yc-.8)} {f(c-1.3)},{f(yc-1.3)} {f(c-1.45)},{f(yc-1.6)} H{f(c+1.45)} C{f(c+1.3)},{f(yc-1.3)} {f(c+w1/2+.2)},{f(yc-.8)} {f(c+w1/2)},{f(yc)}Z" fill="{C_FILL}" stroke="{C_LINE}" stroke-width=".12"/>')
        for k in (-.8, -.3, .3, .8):
            o.append(f'<path d="M{f(c+k*.7)},{f(yc)} q{f(k*.3)},-.6 {f(k*.8)},-1.1" stroke="{C_LINE}" stroke-width=".06" fill="none"/>')
    # trabeazione spezzata
    ye = base - colh
    o.append(f'<path d="M{f(x-.3)},{f(ye)} H{f(x+10.4)} L{f(x+10.0)},{f(ye-ent*.55)} L{f(x+10.6)},{f(ye-ent)} H{f(x-.6)} Z" fill="{C_FILL}" stroke="{C_LINE}" stroke-width=".16"/>')
    for t in (.3, .55):
        o.append(f'<line x1="{f(x-.4)}" y1="{f(ye-ent*t)}" x2="{f(x+10.2)}" y2="{f(ye-ent*t)}" stroke="{C_LINE}" stroke-width=".07"/>')
    for k in range(14):
        xx = x - .2 + k*.76
        o.append(f'<line x1="{f(xx)}" y1="{f(ye-ent)}" x2="{f(xx)}" y2="{f(ye-ent+.35)}" stroke="{C_LINE}" stroke-width=".07"/>')
    return o

def arco_trionfo(x, ground, w=12.5, h=13.5):
    """Arco trionfale a un fornice (tipo Arco di Tito)."""
    o = []
    att = h*.27
    body_top = ground - h + att
    o.append(f'<path d="M{f(x+w-.1)},{f(ground)} V{f(ground-h+.4)} l1.0,.6 V{f(ground)}Z" fill="{C_SHADE}" opacity=".7"/>')
    o.append(f'<rect x="{f(x)}" y="{f(body_top)}" width="{f(w)}" height="{f(ground-body_top)}" fill="{C_FILL}" stroke="{C_LINE}" stroke-width=".18"/>')
    o.append(f'<rect x="{f(x+.3)}" y="{f(ground-h)}" width="{f(w-.6)}" height="{f(att)}" fill="{C_FILL}" stroke="{C_LINE}" stroke-width=".18"/>')
    # iscrizione nell'attico
    for k in range(3):
        yy = ground - h + att*(.3 + k*.2)
        o.append(f'<line x1="{f(x+2.4)}" y1="{f(yy)}" x2="{f(x+w-2.4)}" y2="{f(yy)}" stroke="{C_LINE}" stroke-width=".18" stroke-dasharray=".35 .2"/>')
    o.append(f'<line x1="{f(x-.3)}" y1="{f(body_top)}" x2="{f(x+w+.3)}" y2="{f(body_top)}" stroke="{C_LINE}" stroke-width=".28"/>')
    # fornice
    rx = w*.22; mx = x + w/2; spring = ground - (h-att)*.62
    o.append(f'<path d="M{f(mx-rx)},{f(ground)} V{f(spring)} A{f(rx)},{f(rx)} 0 0 1 {f(mx+rx)},{f(spring)} V{f(ground)}Z" fill="{C_SHADE}" stroke="{C_LINE}" stroke-width=".14"/>')
    o.append(f'<path d="M{f(mx+rx*.2)},{f(ground)} V{f(spring+.4)} A{f(rx*.8)},{f(rx*.8)} 0 0 1 {f(mx+rx-.1)},{f(spring+.8)} V{f(ground)}Z" fill="{C_FILL}" opacity=".45"/>')
    # semicolonne e cornici
    for cxx in (x+1.1, x+w*.27, x+w*.73, x+w-1.1):
        o.append(f'<line x1="{f(cxx)}" y1="{f(ground-.6)}" x2="{f(cxx)}" y2="{f(body_top+.6)}" stroke="{C_LINE}" stroke-width=".22"/>')
    o.append(f'<line x1="{f(x)}" y1="{f(spring)}" x2="{f(mx-rx)}" y2="{f(spring)}" stroke="{C_LINE}" stroke-width=".1"/>')
    o.append(f'<line x1="{f(mx+rx)}" y1="{f(spring)}" x2="{f(x+w)}" y2="{f(spring)}" stroke="{C_LINE}" stroke-width=".1"/>')
    # vittorie alate nei pennacchi (accenni)
    for sx in (-1, 1):
        o.append(f'<path d="M{f(mx+sx*(rx+.6))},{f(spring-rx-.3)} q{f(sx*1.2)},-.6 {f(sx*2.0)},.2" stroke="{C_LINE}" stroke-width=".09" fill="none"/>')
    return o

def rondini(pts):
    return [f'<path d="M{f(x-.9*s)},{f(y-.3*s)} q{f(.45*s)},{f(.1*s)} {f(.9*s)},{f(.35*s)} q{f(.45*s)},{f(-.25*s)} {f(.9*s)},{f(-.35*s)}" stroke="{C_LINE}" stroke-width=".14" fill="none" stroke-linecap="round"/>' for x, y, s in pts]

def panorama():
    W, H = 134, 27.5
    g = H - 1.2
    p = []
    p += colline(W, g)
    p += cupola(103.5, g, '#DCC6A1')
    p += acquedotto(2.2, 45.5, g, 19.0, 6.4, n=10, rotte=(2,))
    p += cipresso(46.4, g, 10.5, '#A3835B')
    p += colosseo(75, g, 26)
    p += tempio_castori(106.5, g)
    p += arco_trionfo(119.0, g)
    p += pino(51.5, g, 13.5, 11.5, -1.6, '#8C6B46')
    p += cipresso(117.6, g, 9.5, '#A3835B')
    p += pino(131.5, g, 15, 12.5, -2.2, '#8C6B46')
    p += rondini([(29, 7.6, 1.1), (33.2, 6.2, .85), (36.4, 8.4, .75), (101.6, 7.4, .9), (105, 6.3, .7)])
    gl = f'M0,{f(g)} ' + ' '.join(f'L{f(x)},{f(g + .25*math.sin(x*.7))}' for x in [i*1.5 for i in range(1, 91)])
    p.append(f'<path d="{gl} L{W},{H} L0,{H} Z" fill="{C_FILL}"/>')
    p.append(f'<path d="{gl}" stroke="{C_LINE}" stroke-width=".3" fill="none"/>')
    for i in range(55):
        x = random.uniform(1, W-1)
        p.append(f'<line x1="{f(x)}" y1="{f(g+.6+random.uniform(0,.4))}" x2="{f(x+random.uniform(1,2.5))}" y2="{f(g+.6+random.uniform(0,.4))}" stroke="{C_LINE}" stroke-width=".08" opacity=".6"/>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}mm" height="{H}mm">' + ''.join(p) + '</svg>'
    open('assets/panorama_roma.svg', 'w').write(svg)

alloro(); panorama()
