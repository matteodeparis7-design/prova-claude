import sys; sys.path.insert(0,"/tmp/claude-0/-home-user-prova-claude/28117a8a-5f58-5be6-8483-71bef30eda1b/scratchpad/verify")
from figlib import *
r2=np.sqrt(2)
fig,ax=setup((-3,5),(-6,2))
X=np.linspace(-2.6,2.6,400); Y=X**2/(6*r2)
# x = (-X+Y)/sqrt2 + 1 ; y = (-X-Y)/sqrt2 - 2
ax.plot((-X+Y)/r2+1,(-X-Y)/r2-2,color=TEAL,lw=2)
line(ax,(0,0),(1,1),":","#c0392b",1.3); line(ax,(1,-2),(1,-1),"--","#888")
pt(ax,(1,-2),"V",(-14,-4)); pt(ax,(2.5,-3.5),"F",(5,2),"#1f4e9c"); pt(ax,(-0.5,-0.5),"D",(-14,2),"#c0392b")
ax.text(1.2,1.5,"direttrice y = x",color="#c0392b",fontsize=8.5,rotation=45); ax.text(3.4,-4.2,"asse",color="#666",fontsize=9)
save(fig,"a3_parabola.svg"); print("ok")
