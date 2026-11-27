import sys; sys.path.insert(0,"/tmp/claude-0/-home-user-prova-claude/28117a8a-5f58-5be6-8483-71bef30eda1b/scratchpad/verify")
from figlib import *
s3=np.sqrt(3)
fig,ax=setup((-3.5,1.6),(-2.4,2.4))
line(ax,(-1,0),(1,0),"--","#c0392b"); line(ax,(-1,0),(1,s3),"--","#c0392b")
line(ax,(-1,0),(s3/2,0.5),"-.","#888"); line(ax,(-1,0),(-0.5,s3/2),"-.","#888")
conic(ax,-1,0,(s3/2,0.5),"iperbole",2/s3,2/3,rng=1.9)
pt(ax,(-1,0),"C",(-12,-12)); pt(ax,(0,1/s3),"P",(4,-12)); 
pt(ax,(-1+2*s3/3,2/3),r"$F_1$",(4,2),"#1f4e9c"); pt(ax,(-1-2*s3/3,-2/3),r"$F_2$",(-6,-14),"#1f4e9c")
save(fig,"a2_iperbole.svg"); print("ok")
