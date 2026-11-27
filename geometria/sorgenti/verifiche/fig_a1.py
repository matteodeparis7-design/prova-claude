import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family":"DejaVu Serif","font.size":10,"mathtext.fontset":"cm"})
out="/tmp/claude-0/-home-user-prova-claude/28117a8a-5f58-5be6-8483-71bef30eda1b/scratchpad/build/fig/"
def grid(ax,xl,yl):
    ax.set_xlim(*xl); ax.set_ylim(*yl); ax.set_aspect("equal")
    ax.grid(True,color="#d9d9d9",lw=0.6); ax.axhline(0,color="k",lw=0.9); ax.axvline(0,color="k",lw=0.9)
    for s in ax.spines.values(): s.set_visible(False)
    ax.text(xl[1],0.15,"x",ha="right"); ax.text(0.15,yl[1],"y",va="top")
teal="#2a8c86"
# parabola 3(x+y+1)^2+(x-y-3)=0 ; param X in R: x=(X-Y)/sqrt2+1, y=(X+Y)/sqrt2-2, Y=3sqrt2 X^2
fig,ax=plt.subplots(figsize=(3.6,3.6))
grid(ax,(-3,4),(-4,3))
X=np.linspace(-1.2,1.2,400); Y=3*np.sqrt(2)*X**2
ax.plot((X-Y)/np.sqrt(2)+1,(X+Y)/np.sqrt(2)-2,color=teal,lw=2)
t=np.linspace(-5,5,2); ax.plot(t,-t-1,"--",color="#888",lw=1)        # axis x+y+1=0
ax.plot(t,t-37/12,":",color="#c0392b",lw=1.3)                           # directrix
for (px,py,l,c,o) in [(1,-2,"V","k",(-14,-3)),(0,0,"O","k",(-12,4)),(23/24,-47/24,"F","#1f4e9c",(-4,7))]:
    ax.plot(px,py,"o",color=c,ms=4.5); ax.annotate(l,(px,py),xytext=o,textcoords="offset points")
ax.text(-2.8,2.2,"asse",color="#666",fontsize=9); ax.text(2.4,-1.45,"direttrice",color="#c0392b",fontsize=9,rotation=45)
fig.savefig(out+"a1_parabola.svg",bbox_inches="tight"); print("ok")
