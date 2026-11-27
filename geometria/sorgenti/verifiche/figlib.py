import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family":"DejaVu Serif","font.size":10,"mathtext.fontset":"cm"})
OUT="/tmp/claude-0/-home-user-prova-claude/28117a8a-5f58-5be6-8483-71bef30eda1b/scratchpad/build/fig/"
TEAL="#2a8c86"
def setup(xl,yl,size=(3.6,3.6)):
    fig,ax=plt.subplots(figsize=size)
    ax.set_xlim(*xl); ax.set_ylim(*yl); ax.set_aspect("equal")
    ax.grid(True,color="#d9d9d9",lw=0.6); ax.axhline(0,color="k",lw=0.9); ax.axvline(0,color="k",lw=0.9)
    for s in ax.spines.values(): s.set_visible(False)
    ax.text(xl[1],0.08*(yl[1]-yl[0])/7,"x",ha="right"); ax.text(0.08*(xl[1]-xl[0])/7,yl[1],"y",va="top")
    return fig,ax
def line(ax,p,d,style="--",color="#888",lw=1,L=30):
    p=np.array(p,float); d=np.array(d,float); t=np.array([-L,L]); ax.plot(p[0]+t*d[0],p[1]+t*d[1],style,color=color,lw=lw)
def pt(ax,p,label,off=(5,4),color="k"):
    ax.plot(p[0],p[1],"o",color=color,ms=4.5); ax.annotate(label,p,xytext=off,textcoords="offset points",color=color)
def conic(ax,cx,cy,u,kind,a,b,rng=2.2,color=TEAL):
    """u = unit vector of the X axis; kind 'iperbole' X^2/a^2-Y^2/b^2=1, 'ellisse'"""
    u=np.array(u,float); v=np.array([-u[1],u[0]])
    if kind=="iperbole":
        s=np.linspace(-rng,rng,400)
        for sg in (1,-1):
            X=sg*a*np.cosh(s); Y=b*np.sinh(s)
            ax.plot(cx+X*u[0]+Y*v[0], cy+X*u[1]+Y*v[1], color=color, lw=2)
    else:
        s=np.linspace(0,2*np.pi,400); X=a*np.cos(s); Y=b*np.sin(s)
        ax.plot(cx+X*u[0]+Y*v[0], cy+X*u[1]+Y*v[1], color=color, lw=2)
def save(fig,name): fig.savefig(OUT+name,bbox_inches="tight"); plt.close(fig)
