from sympy import *
x,y,z,w,k,h,t,X,Y=symbols('x y z w k h t X Y')
print("=== EX1")
A=Matrix([[2*k**2,k],[2*k,1],[2,k]]); B=Matrix([h,k+1,h]); AB=A.row_join(B)
print("det(A|B)=",factor(AB.det()))
for kv in [0,1,-1,Rational(1,2),2]:
    print("k=",kv,"rkA",A.subs(k,kv).rank(), "minors", [factor(A.subs(k,kv).extract([i,j],[0,1]).det()) for i,j in [(0,1),(0,2),(1,2)]])
print("2x2 minors general:",[factor(A.extract([i,j],[0,1]).det()) for i,j in [(0,1),(0,2),(1,2)]])
for kv in [0,1,-1]:
    for hv in [h]:
        M=AB.subs(k,kv); print("k=",kv," AB=",M.tolist(), "rank generic h", M.rank())
for kv,hv in [(1,2),(-1,0),(0,0),(0,1),(1,1),(-1,1)]:
    M=AB.subs({k:kv,h:hv}); print(kv,hv,"rkA",A.subs(k,kv).rank(),"rkAB",M.rank(), linsolve((A.subs(k,kv),B.subs({k:kv,h:hv})),x,y))
# k generic not in {0,1,-1}: compatible iff det(A|B)=0
print(solve(AB.det(),h))
kv=symbols('kv')
print("sol generic when h solves:", simplify(linsolve((A,B.subs(h,solve(AB.det(),h)[0])),x,y)))
print("=== EX2")
C=lambda t: Matrix([t,t,1+2*t])
for tv in [Rational(5,3),Rational(-5,17)]:
    c=C(tv); dA=abs(2*c[0]+2*c[1]+c[2]-1)/3; dB=abs(3*c[0]+4*c[1]+5)/5; print(tv,c.T,dA,dB)
print("=== EX3")
n1=Matrix([1,1,-1,1]); n2=Matrix([1,-1,0,0]); v=Matrix([0,2,2,4])
P=n1*n1.T/4+n2*n2.T/2; print(P*4, (P*v).T, (v-P*v).T, P*P==P, P.T==P)
print("W basis check",[ (n1.dot(b),n2.dot(b)) for b in [Matrix([1,1,2,0]),Matrix([0,0,1,1])]])
print("=== EX4")
H=y*(sqrt(3)*x-y+sqrt(3))-Rational(2,3); print(expand(H))
print("P on H:",simplify(H.subs({x:0,y:1/sqrt(3)})))
xs=-1+sqrt(3)/2*X-Rational(1,2)*Y; ys=Rational(1,2)*X+sqrt(3)/2*Y
print("normal:", simplify(expand(H.subs({x:xs,y:ys}))))
c=Rational(4,3); F1=Matrix([-1+c*sqrt(3)/2, c/2]); F2=Matrix([-1-c*sqrt(3)/2,-c/2])
pt=Matrix([0,1/sqrt(3)]); print("|PF1-PF2|=",simplify(abs((pt-F1).norm()-(pt-F2).norm())), "2a=",4/sqrt(3))
print("=== EX5")
A=Matrix([[-1,2],[4,1]])/3; Bv=Matrix([-2,2])/3
f=lambda p: A*p+Bv
print(f(Matrix([0,1])).T,f(Matrix([1,3])).T,f(Matrix([1,0])).T,A.det(),A.eigenvects(),A*A)
print(solve(list(A*Matrix([x,y])+Bv-Matrix([x,y])),[x,y]))
xp,yp=(A*Matrix([x,y])+Bv)
print("x+y->",simplify(xp+yp),"  2x-y->",simplify(2*xp-yp))
