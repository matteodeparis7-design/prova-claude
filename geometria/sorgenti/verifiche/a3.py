from sympy import *
x,y,z,k,h,t,l=symbols('x y z k h t lambda')
print("=== EX1")
A=Matrix([[k,1,1],[1,k,1],[1,1,k]]); B=Matrix([1,h,k**2]); print(factor(A.det()))
for kv in [1,-2]:
  for hv in [1,-5,0]:
    print(kv,hv,A.subs(k,kv).rank(),A.subs(k,kv).row_join(B.subs({k:kv,h:hv})).rank())
print(linsolve((A.subs(k,2),B.subs({k:2,h:-2})),x,y,z)); print("generic",simplify(A.LUsolve(B)))
print(linsolve((A.subs(k,-2),B.subs({k:-2,h:-5})),x,y,z))
print("=== EX2")
u=Matrix([2,1,0]).cross(Matrix([0,1,1])); print("u",u.T)
P=Matrix([0,1,3])
for sg in [1,-1]:
  d=Matrix([12+sg*sqrt(6),3-sg*2*sqrt(6),-3+sg*2*sqrt(6)])
  print("cos",simplify(abs(d.dot(u))/(d.norm()*u.norm())))
  # intersection with r
  Q=P+Rational(2,27)/2*d  # lambda=1/27 -> Q = P + d/27
  Q=P+d/27; print(" Q=",[nsimplify(simplify(c)) for c in Q], " on r:", simplify(2*Q[0]+Q[1]-3), simplify(Q[1]+Q[2]-4))
print(solve(243*t**2-432*t+184,t))
print("=== EX3")
W=Matrix.hstack(Matrix([1,0,2]),Matrix([1,0,0]),Matrix([0,1,1])); print("detW",W.det())
b1,b2,b3=Matrix([2,0,1]),Matrix([1,0,1]),Matrix([1,1,0]); Bm=Matrix.hstack(b1,b2,b3)
TW=Matrix.hstack(2*b1,3*b2,2*b3); Ac=TW*W.inv(); print("A canon",Ac); Ab=Bm.inv()*Ac*Bm; print("A_b",Ab)
print("charpoly",factor(Ac.charpoly(l).as_expr())); print(Ac.eigenvects()); print("diag?",Ac.is_diagonalizable())
print("W coords in b:", [ (Bm.inv()*W[:,i]).T for i in range(3)])
print("=== EX4")
Pb=x**2+2*x*y+y**2-10*x+14*y+37
print("focus-dir:",expand(2*((x-Rational(5,2))**2+(y+Rational(7,2))**2)-(x-y)**2-Pb))
X,Y=symbols('X Y'); # X=(-x-y-1)/sqrt2, Y=(x-y-3)/sqrt2 -> x+y=-sqrt2 X-1, x-y=sqrt2 Y+3
xs=((-sqrt(2)*X-1)+(sqrt(2)*Y+3))/2; ys=((-sqrt(2)*X-1)-(sqrt(2)*Y+3))/2
print(xs,ys, expand(Pb.subs({x:xs,y:ys})))
print("=== EX5")
A=Matrix([[1,-2],[2,1]]); print(A.det(),A.eigenvals(), solve([x-2*y+4-x,2*x+y+2-y],[x,y]), N(atan(2)*180/pi))
