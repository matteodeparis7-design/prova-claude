import sys; sys.path.insert(0,"/tmp/claude-0/-home-user-prova-claude/28117a8a-5f58-5be6-8483-71bef30eda1b/scratchpad/verify")
from figlib import *
s2=np.sqrt(2); s5=np.sqrt(5)
fig,ax=setup((-5,7),(-8,4),size=(3.7,3.7))
line(ax,(1,-2),(1,0),"--","#c0392b"); line(ax,(1,-2),(0,1),"--","#c0392b")
line(ax,(1,-2),(1,-1),"-.","#888"); line(ax,(1,-2),(1,1),"-.","#888")
conic(ax,1,-2,(1/s2,-1/s2),"iperbole",s5,s5,rng=1.7)
pt(ax,(1,-2),"C",(5,4)); pt(ax,(1+s5,-2-s5),r"$F_1$",(5,0),"#1f4e9c"); pt(ax,(1-s5,-2+s5),r"$F_2$",(-16,4),"#1f4e9c")
save(fig,"a7_iperbole.svg"); print("ok")
