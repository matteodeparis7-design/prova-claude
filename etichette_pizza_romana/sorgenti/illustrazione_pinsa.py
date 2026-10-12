# Illustrazione vettoriale di una pinsa romana (margherita) vista dall'alto.
# Uscita: assets/pinsa_margherita.svg  (coordinate in mm, centro 0,0)
import math, random, sys
R = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
f = lambda v: f'{v:.2f}'

def smooth_closed(pts, t=.5):
    """Catmull-Rom chiuso -> path bezier."""
    n = len(pts); d = f'M{f(pts[0][0])},{f(pts[0][1])}'
    for i in range(n):
        p0, p1, p2, p3 = pts[i-1], pts[i], pts[(i+1) % n], pts[(i+2) % n]
        c1 = (p1[0] + (p2[0]-p0[0])*t/3, p1[1] + (p2[1]-p0[1])*t/3)
        c2 = (p2[0] - (p3[0]-p1[0])*t/3, p2[1] - (p3[1]-p1[1])*t/3)
        d += f' C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}'
    return d + 'Z'

def wobble(n, harm, amp):
    ph = [R.uniform(0, 6.28) for _ in range(harm)]; am = [R.uniform(.3, 1)*amp/(k+1)**.9 for k in range(harm)]
    return lambda a: sum(am[k]*math.sin((k+2)*a + ph[k]) for k in range(harm))

def blob(cx, cy, rx, ry, n=14, irr=.18, rot=0):
    w = wobble(n, 5, irr)
    pts = []
    for i in range(n):
        a = 2*math.pi*i/n
        r = 1 + w(a) + R.uniform(-irr*.25, irr*.25)
        x, y = rx*r*math.cos(a), ry*r*math.sin(a)
        c, s = math.cos(rot), math.sin(rot)
        pts.append((cx + x*c - y*s, cy + x*s + y*c))
    return smooth_closed(pts)

A, B = 62, 39                      # semiassi della pinsa (mm)
o = []
o.append('''<defs>
<radialGradient id="gOmbra" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(2.5,4.2) scale(68,45)">
  <stop offset=".80" stop-color="#4a2a14" stop-opacity=".42"/><stop offset=".92" stop-color="#4a2a14" stop-opacity=".14"/><stop offset="1" stop-color="#4a2a14" stop-opacity="0"/></radialGradient>
<radialGradient id="gCrosta" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(-6,-5) scale(66,44)">
  <stop offset="0" stop-color="#F3C67E"/><stop offset=".72" stop-color="#E7A95A"/><stop offset=".9" stop-color="#D08A3C"/><stop offset="1" stop-color="#A9652A"/></radialGradient>
<radialGradient id="gSugo" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(-5,-6) scale(54,34)">
  <stop offset="0" stop-color="#D2452A"/><stop offset=".65" stop-color="#BB3420"/><stop offset="1" stop-color="#93261A"/></radialGradient>
<radialGradient id="gMozz" cx=".38" cy=".32" r=".8">
  <stop offset="0" stop-color="#FFFDF7"/><stop offset=".6" stop-color="#FBF3E2"/><stop offset="1" stop-color="#EAD9B8"/></radialGradient>
<linearGradient id="gBasilico" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#5C9A3A"/><stop offset=".55" stop-color="#3F7B2B"/><stop offset="1" stop-color="#2B5A1F"/></linearGradient>
<linearGradient id="gLuce" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#FFE4AE" stop-opacity=".95"/><stop offset=".55" stop-color="#F6CB86" stop-opacity=".35"/><stop offset="1" stop-color="#B86E2E" stop-opacity=".5"/></linearGradient>
<radialGradient id="gBolla" cx=".4" cy=".35" r=".7">
  <stop offset="0" stop-color="#F8D9A0"/><stop offset=".6" stop-color="#E9AE62"/><stop offset="1" stop-color="#C47B35" stop-opacity="0"/></radialGradient>
</defs>''')
# ombra
o.append(f'<ellipse cx="2.5" cy="4.2" rx="68" ry="45" fill="url(#gOmbra)"/>')
# crosta: ovale irregolare, lato "a pala" leggermente squadrato
w = wobble(60, 7, .022)
pts = []
for i in range(72):
    a = 2*math.pi*i/72
    r = 1 + w(a) - .025*abs(math.cos(a))**8
    pts.append((A*r*math.cos(a), B*r*math.sin(a)))
crosta = smooth_closed(pts)
o.append(f'<path d="{crosta}" fill="url(#gCrosta)"/>')
o.append(f'<path d="{crosta}" fill="none" stroke="#8E5222" stroke-width=".35" opacity=".55"/>')
# volume del cornicione: banda di luce e ombra verso il sugo
def anello(k):
    return smooth_closed([(A*k*(1 + w(2*math.pi*i/72))*math.cos(2*math.pi*i/72), B*k*(1 + w(2*math.pi*i/72))*math.sin(2*math.pi*i/72)) for i in range(72)])
o.append(f'<path d="{anello(.915)}" fill="none" stroke="url(#gLuce)" stroke-width="4.2" opacity=".75"/>')
o.append(f'<path d="{anello(.94)}" fill="none" stroke="#FCE3AE" stroke-width="1.1" opacity=".35"/>')
# bolle e bruciature del cornicione
for i in range(30):
    a = R.uniform(0, 2*math.pi); k = R.uniform(.875, .94)
    x, y = A*k*math.cos(a), B*k*math.sin(a)
    rx = R.uniform(1.6, 3.8); ry = rx*R.uniform(.55, .8)
    rot = math.degrees(math.atan2(B*math.sin(a), A*math.cos(a))) + 90 + R.uniform(-15, 15)
    g = f'<g transform="translate({f(x)},{f(y)}) rotate({f(rot)})">'
    g += f'<ellipse rx="{f(rx)}" ry="{f(ry)}" fill="#F3CD8C" opacity=".7"/>'
    g += f'<ellipse cx="{f(-rx*.15)}" cy="{f(-ry*.2)}" rx="{f(rx*.55)}" ry="{f(ry*.45)}" fill="#FFF1D2" opacity=".55"/>'
    if R.random() < .6:
        g += (f'<path d="M{f(-rx*.8)},{f(ry*.3)} Q0,{f(ry*1.05)} {f(rx*.8)},{f(ry*.3)} Q0,{f(ry*.78)} {f(-rx*.8)},{f(ry*.3)}Z" '
              f'fill="#9A5422" opacity="{f(R.uniform(.35, .55))}"/>')
    o.append(g + '</g>')
for i in range(14):        # macchie di cottura a leopardo
    a = R.uniform(0, 2*math.pi); k = R.uniform(.86, .96)
    x, y = A*k*math.cos(a), B*k*math.sin(a)
    o.append(f'<path d="{blob(x, y, R.uniform(.5, 1.3), R.uniform(.4, .9), 9, .35, R.uniform(0, 3))}" fill="#4E2610" opacity="{f(R.uniform(.5, .8))}"/>')
for i in range(70):        # puntini di cottura
    a = R.uniform(0, 2*math.pi); k = R.uniform(.83, .98)
    x, y = A*k*math.cos(a), B*k*math.sin(a)
    o.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(R.uniform(.12, .38))}" fill="#6B3818" opacity="{f(R.uniform(.4, .8))}"/>')
for i in range(60):        # farina / semola
    a = R.uniform(0, 2*math.pi); k = R.uniform(.9, 1.0)
    x, y = A*k*math.cos(a), B*k*math.sin(a)
    o.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(R.uniform(.1, .28))}" fill="#FFF6E2" opacity="{f(R.uniform(.5, .9))}"/>')
# sugo
w2 = wobble(60, 9, .065)
pts = []
for i in range(80):
    a = 2*math.pi*i/80
    r = .80 + w2(a)*.9 + R.uniform(-.006, .006)
    pts.append((A*r*math.cos(a), B*r*math.sin(a)))
sugo = smooth_closed(pts)
o.append(f'<path d="{sugo}" fill="none" stroke="#8A4A1C" stroke-width="2.2" opacity=".28"/>')
o.append(f'<path d="{sugo}" fill="none" stroke="#7A3A14" stroke-width="1" opacity=".35"/>')
o.append(f'<path d="{sugo}" fill="url(#gSugo)"/>')
for i in range(140):       # polpa di pomodoro
    a = R.uniform(0, 2*math.pi); k = math.sqrt(R.uniform(0, .58))
    x, y = A*k*math.cos(a), B*k*math.sin(a)
    col = R.choice(['#E0583A', '#A92A1A', '#C93F25', '#8E2216'])
    o.append(f'<path d="{blob(x, y, R.uniform(.4, 1.3), R.uniform(.3, .9), 7, .35, R.uniform(0, 3))}" fill="{col}" opacity="{f(R.uniform(.35, .8))}"/>')
for i in range(12):        # riflessi d'olio
    a = R.uniform(0, 2*math.pi); k = math.sqrt(R.uniform(0, .55))
    x, y = A*k*math.cos(a), B*k*math.sin(a); L = R.uniform(1.2, 3.2)
    o.append(f'<path d="M{f(x)},{f(y)} q{f(L*.5)},{f(-L*.25)} {f(L)},0" stroke="#FFD9B8" stroke-width="{f(R.uniform(.2, .35))}" fill="none" stroke-linecap="round" opacity="{f(R.uniform(.25, .45))}"/>')
# mozzarella
mozz = [(-34, -9, 11, 7.5), (-16, 12, 10, 7), (3, -14, 11.5, 7.2), (22, 8, 10.5, 7.5), (38, -10, 9, 6.2), (-38, 14, 7.5, 5.2), (8, 19, 7, 4.8), (-8, -2, 6.5, 4.5), (44, 15, 6.5, 4.6)]
for (x, y, rx, ry) in mozz:
    rot = R.uniform(-.5, .5)
    d = blob(x, y, rx, ry, 18, .2, rot)
    o.append(f'<path d="{d}" fill="#6E1A10" opacity=".28" transform="translate(.5,.7)"/>')
    o.append(f'<path d="{d}" fill="url(#gMozz)"/>')
    for j in range(R.randint(1, 3)):   # gratinatura
        bx, by = x + R.uniform(-rx*.5, rx*.5), y + R.uniform(-ry*.5, ry*.5)
        o.append(f'<path d="{blob(bx, by, R.uniform(.6, 1.4), R.uniform(.4, 1.0), 9, .35)}" fill="#E2B677" opacity="{f(R.uniform(.18, .32))}"/>')
    o.append(f'<path d="M{f(x-rx*.45)},{f(y-ry*.35)} q{f(rx*.3)},{f(-ry*.3)} {f(rx*.65)},{f(-ry*.1)}" stroke="#FFFFFF" stroke-width=".55" fill="none" stroke-linecap="round" opacity=".85"/>')
# basilico
def foglia(x, y, L, rot):
    W = L*.42
    d = (f'M0,0 C{f(L*.18)},{f(-W*.95)} {f(L*.72)},{f(-W*.85)} {f(L)},0 C{f(L*.72)},{f(W*.85)} {f(L*.18)},{f(W*.95)} 0,0Z')
    v = f'M{f(L*.05)},0 Q{f(L*.5)},{f(-W*.08)} {f(L*.93)},0'
    ven = ''.join(f'M{f(L*t)},{f(-W*.02)} q{f(L*.1)},{f(-W*.35)} {f(L*.2)},{f(-W*.55)} M{f(L*t)},{f(W*.02)} q{f(L*.1)},{f(W*.35)} {f(L*.2)},{f(W*.55)} ' for t in (.25, .45, .65))
    return (f'<g transform="translate({f(x)},{f(y)}) rotate({f(rot)})">'
            f'<path d="{d}" fill="#4A1006" opacity=".45" transform="translate(.4,.55)"/>'
            f'<path d="{d}" fill="url(#gBasilico)"/>'
            f'<path d="{v}" stroke="#A8D07A" stroke-width=".28" fill="none" opacity=".9"/>'
            f'<path d="{ven}" stroke="#86B85A" stroke-width=".14" fill="none" opacity=".75"/>'
            f'<path d="M{f(L*.2)},{f(-W*.45)} q{f(L*.25)},{f(-W*.3)} {f(L*.5)},{f(-W*.25)}" stroke="#CFE8A8" stroke-width=".3" fill="none" opacity=".45" stroke-linecap="round"/></g>')
for (x, y, L, rot) in [(-22, -3, 12, -35), (-21, -2, 10, 70), (12, 2, 13, 160), (13, 3, 10.5, 245), (31, -2, 9.5, -80), (-46, 1, 9, 20), (0, -26, 8.5, 190), (-3, 26, 9, -10)]:
    o.append(foglia(x, y, L, rot))
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-70 -46 142 96" width="142mm" height="96mm">' + ''.join(o) + '</svg>')
open('assets/pinsa_margherita.svg', 'w').write(svg)
