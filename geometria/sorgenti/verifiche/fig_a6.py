import sys; sys.path.insert(0,"/tmp/claude-0/-home-user-prova-claude/28117a8a-5f58-5be6-8483-71bef30eda1b/scratchpad/verify")
from figlib import *
s3=np.sqrt(3)
fig,ax=setup((-5,2),(-1.5,4.5),size=(3.8,3.3))
Yt=np.linspace(-2.2,2.2,400); Xt=Yt**2
ax.plot(-s3/2*Xt-Yt/2, Xt/2-s3/2*Yt+1, color=TEAL, lw=2)
line(ax,(0,1),(-s3,1),"--","#888")                       # asse
line(ax,(0,0.5),(1,s3),":","#c0392b",1.3)                # direttrice 2sqrt3 x-2y+1=0 -> y=sqrt3 x+1/2
pt(ax,(0,1),"V",(5,-10)); pt(ax,(-s3/8,9/8),"F",(-4,6),"#1f4e9c")
ax.text(-4.8,3.3,"asse",color="#666",fontsize=9); ax.text(0.15,2.6,"direttrice",color="#c0392b",fontsize=8.5,rotation=60)
save(fig,"a6_parabola.svg"); print("ok")
