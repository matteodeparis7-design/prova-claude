from sympy import *
x,y,z,w,k,h,t,X,Y=symbols('x y z w k h t X Y')
print("=== EX1")
A=Matrix([[2*k**2,k,0],[2*k,1,0],[1,k,1]]); B=Matrix([h,k,h]); print(A.det(), [A.subs(k,kv).rank() for kv in [0,1,2,-1]])
for kv,hv in [(2,4),(2,3),(0,0),(0,1),(-1,1),(-1,2)]:
  print(kv,hv,A.subs(k,kv).row_join(B.subs({k:kv,h:hv})).rank(), linsolve((A.subs(k,kv),B.subs({k:kv,h:hv})),x,y,z))
print("=== EX2")
V=Matrix([0,0,2]); print("V on r", V[0]+1, (V[1]+3)/3, V[2]-1, " V in alpha", V[1]+V[2]-2)
Cone=x**2+4*y**2-4*(z-2)**2; print("cone on alpha:", expand(Cone.subs(z,2-y)), " z=1:", expand(Cone.subs(z,1)))
print("=== EX3")
n1=Matrix([1,-1,-1,1]); n2=Matrix([1,0,1,0]); v=Matrix([4,0,8,0]); P=n1*n1.T/4+n2*n2.T/2
print(n1.dot(n2), (P*v).T, (v-P*v).T, P*4, P*P==P)
print([ (n1.dot(b),n2.dot(b)) for b in [Matrix([0,1,0,1]),Matrix([-1,0,1,2])]])
print("=== EX4")
H=(x-sqrt(3)*y)*(x-sqrt(3))-3; print(expand(H), H.subs({x:0,y:1}))
u=Matrix([-sqrt(3)/2,Rational(1,2)]); v=Matrix([-Rational(1,2),-sqrt(3)/2]); C=Matrix([sqrt(3),1])
print("det",Matrix.hstack(u,v).det())
sub={x:C[0]+X*u[0]+Y*v[0], y:C[1]+X*u[1]+Y*v[1]}; print("normal", expand(simplify(expand(H.subs(sub)))))
c=2*sqrt(2); F1=C+c*u; F2=C-c*u; print("F",F1.T,F2.T)
p=Matrix([0,1]); print("|PF1-PF2|",N(abs((p-F1).norm()-(p-F2).norm())), N(2*sqrt(2)))
print("=== EX5")
f=lambda p:(p[1]+4,p[0]+6)
print([f(q) for q in [(0,0),(1,0),(1,1),(0,1),(3,5)]])
# reflection check: midpoint of P and refl(P) on axis, segment perpendicular
