from sympy import *
x,y,z,k,h,t,s,X,Y,l=symbols('x y z k h t s X Y lambda')
print("=== EX1")
A=Matrix([[k,1,0],[1,k,0],[k,1,1]]); B=Matrix([2*h,k**2+1,h]); print("det",factor(A.det()))
for kv in [1,-1]:
  for hv in [1,-1,0,2]:
    print(kv,hv,A.subs(k,kv).rank(),A.subs(k,kv).row_join(B.subs({k:kv,h:hv})).rank(),linsolve((A.subs(k,kv),B.subs({k:kv,h:hv})),x,y,z))
print("k=2,h=0",linsolve((A.subs(k,2),B.subs({k:2,h:0})),x,y,z)); print("generic",simplify(A.LUsolve(B)))
print("=== EX2")
u=Matrix([-1,1,0]); v=Matrix([1,0,1]); P0=Matrix([1,0,0]); print("n",u.cross(v).T, "A in plane?", u.cross(v).dot(Matrix([0,1,0])-P0))
