import sys; sys.path.insert(0,"/tmp/claude-0/-home-user-prova-claude/28117a8a-5f58-5be6-8483-71bef30eda1b/scratchpad/verify")
from figlib import *
s10=np.sqrt(10); u=(1/s10,-3/s10); s6=np.sqrt(6)
fig,ax=setup((-5,5),(-7,3))
for m in [(3-2*s6)/5,(3+2*s6)/5]: line(ax,(0,-2),(1,m),"--","#c0392b")
line(ax,(0,-2),(1,-3),"-.","#888"); line(ax,(0,-2),(3,1),"-.","#888")
conic(ax,0,-2,u,"iperbole",2,s6,rng=1.6)
pt(ax,(0,-2),"C",(5,-4)); pt(ax,(-1,1),r"$F_1$",(5,2),"#1f4e9c"); pt(ax,(1,-5),r"$F_2$",(5,-6),"#1f4e9c")
save(fig,"a4_iperbole.svg"); print("ok")
