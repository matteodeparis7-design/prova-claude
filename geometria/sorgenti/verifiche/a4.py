from sympy import *
x,y,z,k,h,l,X,Y=symbols('x y z k h lambda X Y')
print("=== EX1")
A=Matrix([[k**2,1],[1,1],[1,k]]); B=Matrix([1,h,h]); AB=A.row_join(B)
print("detAB",factor(AB.det())); print("minors",[factor(A.extract([i,j],[0,1]).det()) for i,j in [(0,1),(0,2),(1,2)]])
for kv in [1,-1]:
  for hv in [0,1,Rational(1,2),2]:
    print(kv,hv,A.subs(k,kv).rank(),AB.subs({k:kv,h:hv}).rank(),linsolve((A.subs(k,kv),B.subs(h,hv)),x,y))
print("k=2,h=1/4:",linsolve((A.subs(k,2),B.subs(h,Rational(1,4))),x,y), "rank",AB.subs({k:2,h:Rational(1,4)}).rank())
print("solve detAB=0 for h:",solve(AB.det(),h))
print("=== EX2")
C=Matrix([1,2,3]); n=Matrix([2,1,-2]); d=(n.dot(C)+3)/n.norm(); print("R",d, "T", (C-(n.dot(C)+3)/9*n).T)
print("=== EX3")
b1,b2,b3=Matrix([1,0,1]),Matrix([0,0,1]),Matrix([0,1,0]); Bm=Matrix.hstack(b1,b2,b3); print("detB",Bm.det())
Ab=Matrix([[0,0,0],[1,-1,0],[1,1,5]]); A=Bm*Ab*Bm.inv(); print("A canon",A)
print("check",(A*(b1+b2)).T,(2*b3).T,(A*(b1-b2)).T,(2*b2).T,(A*b3).T,(5*b3).T)
print("eig",A.eigenvects()); print("ker",A.nullspace(),"rank",A.rank(),"colspace",A.columnspace())
print("=== EX4")
F1=Matrix([-1,1]); F2=Matrix([1,-5]); P=Matrix([x,y])
H=expand(((P-F1).norm()**2 - (P-F2).norm()**2 )**2 - 32*((P-F1).norm()**2+(P-F2).norm()**2) + 256)
H=expand(H.subs({conjugate(x):x,conjugate(y):y})); 
H2=expand((( (x+1)**2+(y-1)**2)-((x-1)**2+(y+5)**2))**2 - 2*16*(((x+1)**2+(y-1)**2)+((x-1)**2+(y+5)**2)) + 16**2)
print("eq*?",factor(H2))
u=Matrix([1,-3])/sqrt(10); v=Matrix([3,1])/sqrt(10)
sub={x:X*u[0]+Y*v[0], y:-2+X*u[1]+Y*v[1]}
print("normal", simplify(expand(H2.subs(sub))))
print("=== EX5")
A=Matrix([[1,2],[2,-1]]); Bv=Matrix([2*sqrt(5),5-sqrt(5)]); print(A.det(),A.eigenvects())
sol=solve(list(A*Matrix([x,y])+Bv-Matrix([x,y])),[x,y]); print(sol)
