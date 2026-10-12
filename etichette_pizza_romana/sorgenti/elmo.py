# Elmo romano (galea da centurione, vista laterale) con cresta rossa – vettoriale.
# Uscita: assets/elmo_romano.svg   (unita' in mm; centro calotta ~ 0,0)
import math, random
R = random.Random(5)
f = lambda v: f'{v:.2f}'
o = ['''<defs>
<linearGradient id="gMet" x1="0" y1="0" x2=".35" y2="1">
  <stop offset="0" stop-color="#F7E2A6"/><stop offset=".35" stop-color="#E2B866"/><stop offset=".75" stop-color="#B9873A"/><stop offset="1" stop-color="#8A5E22"/></linearGradient>
<linearGradient id="gMet2" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#EFCF86"/><stop offset=".6" stop-color="#C8954A"/><stop offset="1" stop-color="#8E6224"/></linearGradient>
<linearGradient id="gCresta" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#C83A26"/><stop offset=".7" stop-color="#9E2A1B"/><stop offset="1" stop-color="#6E1A10"/></linearGradient>
</defs>''']
LINE = '#5A3814'
# --- cresta: ventaglio di setole dalla fronte alla nuca
cr = 'M-8.4,-6.6 C-11.6,-15.2 -5.2,-22.4 2.4,-22.3 C10,-22.1 14.2,-15.2 11.0,-6.4 C7,-8.9 -4,-9.1 -8.4,-6.6Z'
o.append(f'<clipPath id="clCresta"><path d="{cr}"/></clipPath>')
o.append(f'<path d="{cr}" fill="url(#gCresta)"/>')
o.append('<g clip-path="url(#clCresta)">')
for i in range(46):
    t = i/45
    # setola: dalla base (sul supporto) verso il bordo esterno del ventaglio
    bx = -8.6 + 20*t; by = -7.4 - 1.1*math.sin(math.pi*t)
    ang = math.radians(200 + 140*t)
    L = 14.6 - 3.5*abs(t - .45) + R.uniform(-.8, .5)
    ex, ey = 2.0 + L*math.cos(ang)*1.02, -8.2 + L*math.sin(ang)
    cx_, cy_ = (bx + ex)/2 + R.uniform(-.6, .6), (by + ey)/2 + R.uniform(-.6, .3)
    col = R.choice(['#7A1E12', '#B7321F', '#D24A30', '#8E2416'])
    o.append(f'<path d="M{f(bx)},{f(by)} Q{f(cx_)},{f(cy_)} {f(ex)},{f(ey)}" stroke="{col}" stroke-width="{f(R.uniform(.16, .32))}" fill="none" stroke-linecap="round" opacity=".85"/>')
o.append('</g>')
o.append(f'<path d="{cr}" fill="none" stroke="#5E160D" stroke-width=".3"/>')
# supporto della cresta
o.append(f'<path d="M-7.4,-6.9 C-3,-8.7 6.4,-8.6 9.8,-6.8 L9.4,-5.7 C6,-7.3 -3,-7.4 -7.0,-5.8Z" fill="url(#gMet2)" stroke="{LINE}" stroke-width=".2"/>')
# --- paranuca (svasato)
o.append(f'<path d="M8.6,-1.2 C10.6,2.4 13.4,4.6 17.2,5.4 C17.6,6.2 17.2,6.9 16.4,7.0 C12.2,7.4 8.2,6.6 5.4,5.0 Z" fill="url(#gMet2)" stroke="{LINE}" stroke-width=".25"/>')
o.append(f'<path d="M9.4,3.4 C11.6,5.0 14,5.8 16.6,6.1" stroke="#F3D896" stroke-width=".2" fill="none" opacity=".8"/>')
for x, y in ((11.2, 5.0), (13.6, 5.9)):
    o.append(f'<circle cx="{x}" cy="{y}" r=".32" fill="#F6DFA0" stroke="{LINE}" stroke-width=".1"/>')
# --- calotta
cal = 'M-10.4,2.6 C-11.2,-4.6 -6.4,-9.0 0.6,-9.2 C7.2,-9.2 11.2,-5.4 10.0,2.2 C6,3.6 -6,3.8 -10.4,2.6Z'
o.append(f'<path d="{cal}" fill="url(#gMet)" stroke="{LINE}" stroke-width=".3"/>')
# riflesso
o.append('<path d="M-7.2,-3.6 C-6.2,-6.8 -2.6,-8.0 1.2,-7.9" stroke="#FFF4D0" stroke-width=".7" fill="none" stroke-linecap="round" opacity=".8"/>')
# fascia decorativa e sopracciglia sbalzate
o.append(f'<path d="M-10.6,-.4 C-5,.8 5,.7 10.2,-.6" stroke="{LINE}" stroke-width=".22" fill="none"/>')
o.append(f'<path d="M-10.4,.6 C-5,1.9 5,1.8 10.1,.5" stroke="{LINE}" stroke-width=".14" fill="none"/>')
o.append(f'<path d="M-9.6,-1.9 C-8,-3.6 -5.4,-3.6 -3.8,-2.0 M-3.8,-2.0 C-2.2,-3.6 .4,-3.5 1.8,-1.9" stroke="{LINE}" stroke-width=".2" fill="none"/>')
# --- visiera frontale
o.append(f'<path d="M-12.6,1.4 C-10.6,2.6 -8,3.1 -5.6,3.0 L-5.6,4.0 C-8.4,4.2 -11,3.6 -13.0,2.4Z" fill="url(#gMet2)" stroke="{LINE}" stroke-width=".22"/>')
# --- guanciale
gu = 'M-7.2,3.0 C-8.0,7.0 -7.2,10.8 -4.6,13.0 C-2.6,13.4 -.6,11.8 .4,9.2 C1.2,6.8 1.0,4.6 .2,3.2 Z'
o.append(f'<path d="{gu}" fill="url(#gMet2)" stroke="{LINE}" stroke-width=".28"/>')
o.append(f'<path d="M-6.1,4.4 C-6.6,7.6 -6,10.2 -4.2,11.8 C-2.8,11.9 -1.3,10.6 -.7,8.8 C-.1,6.9 -.2,5.3 -.6,4.3Z" fill="none" stroke="{LINE}" stroke-width=".14"/>')
o.append('<path d="M-5.5,5.4 C-5.8,7.8 -5.4,9.6 -4.4,10.8" stroke="#FFF1C8" stroke-width=".35" fill="none" stroke-linecap="round" opacity=".75"/>')
for x, y in ((-6.5, 4.4), (-.4, 4.2), (-3.2, 8.4)):
    o.append(f'<circle cx="{x}" cy="{y}" r=".38" fill="#F6DFA0" stroke="{LINE}" stroke-width=".1"/>')
# cerniera
o.append(f'<path d="M2.4,3.6 C3.8,3.4 4.8,4.2 4.6,5.4" stroke="{LINE}" stroke-width=".3" fill="none" stroke-linecap="round"/>')
for x in (-8.6, -5.8, -3, -.2, 2.6, 5.4, 8.2):
    o.append(f'<circle cx="{x}" cy="{f(1.15 + .25*math.cos(x/6))}" r=".22" fill="#F6DFA0" stroke="{LINE}" stroke-width=".07"/>')
svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-14 -23.4 32 37.4" width="32mm" height="37.4mm">' + ''.join(o) + '</svg>'
open('assets/elmo_romano.svg', 'w').write(svg)
