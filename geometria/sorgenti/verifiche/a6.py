from sympy import *
x,y,z,w,k,h,t,s,X,Y,l=symbols('x y z w k h t s X Y lambda')
print("=== EX1")
A=Matrix([[k**2,k,1],[k,k**2,1],[1,1,k]]); B=Matrix([2,1+h,2*h**2]); print("det",factor(A.det()))
for kv in [0,1,-2]:
  Ak=A.subs(k,kv); print("k",kv,"rkA",Ak.rank(), "AB rank generic", Ak.row_join(B).rank())
  M=Ak.row_join(B); print("  minors3 of AB:",[factor(M.extract([0,1,2],c).det()) for c in [[0,1,3],[0,2,3],[1,2,3]]])
print(linsolve((A.subs(k,2),B.subs(h,-2)),x,y,z))
for kv,hv in [(0,1),(0,-Rational(1,2)),(1,1),(1,-1),(-2,1),(-2,-Rational(1,2)),(-2,0)]:
  print(kv,hv,A.subs(k,kv).rank(),A.subs(k,kv).row_join(B.subs(h,hv)).rank(),linsolve((A.subs(k,kv),B.subs(h,hv)),x,y,z))
print("=== EX2")
P=Matrix([1,2,0]); u=Matrix([1,-1,2]); Q=Matrix([2,2,1]); v=Matrix([-1,1,1])
print("mixed",Matrix.hstack(Q-P,u,v).det(), "n",u.cross(v).T)
n=u.cross(v); print("alpha d:", -n.dot(P), "beta d:", -n.dot(Q), "dist", abs(n.dot(Q-P))/n.norm())
sol=solve([ (P+t*u-Q-s*v).dot(u), (P+t*u-Q-s*v).dot(v)],[t,s]); print(sol, (P+sol[t]*u).T,(Q+sol[s]*v).T, ((P+sol[t]*u)-(Q+sol[s]*v)).norm())
print("=== EX3")
N=Matrix.hstack(Matrix([2,1,2,1]),Matrix([1,1,0,1]),Matrix([0,1,-2,1])); print("rank N",N.rank(), N.T.nullspace())
Mb=Matrix([[1,0,-1,0],[0,1,0,-1]]).nullspace(); print("M basis",[b.T for b in Mb])
S=Matrix.hstack(*Mb,N); print("rank M+N",S.rank(), "eq of M+N (left null):",[r.T for r in S.T.nullspace()])
# intersection: N vectors a*(2,1,2,1)+b*(1,1,0,1)+c*(0,1,-2,1) satisfying M equations
a,b,c=symbols('a b c'); vec=a*N[:,0]+b*N[:,1]+c*N[:,2]
print("M on N:", expand(vec[0]-vec[2]), expand(vec[1]-vec[3]))
ss=solve([vec[0]-vec[2]],[a],dict=True); print(ss, simplify(vec.subs(ss[0])).T)
