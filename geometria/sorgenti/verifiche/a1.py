from sympy import *
x,y,z,k,h,t,s=symbols('x y z k h t s')
print("=== EX1")
A=Matrix([[2,1,1],[2,k,1],[2,1,k]]); B=Matrix([2,1+h,2*h**2])
print("det",factor(A.det()))
for hv in [1,-1,Rational(-1,2),3]:
    Ak=A.subs(k,1); Ab=Ak.row_join(B.subs(h,hv)); print("k=1 h=",hv,"rkA",Ak.rank(),"rkAB",Ab.rank())
print(linsolve((A.subs(k,2),B.subs(h,-2)),x,y,z))
print("generic sol", simplify(A.LUsolve(B)))
print("=== EX2")
u=Matrix([1,-1,2]); v=Matrix([2,1,1]); n=u.cross(v); print("n",n.T, u.norm(), v.norm(), (u+v).T,(u-v).T)
print("angle cos", u.dot(v)/(u.norm()*v.norm()))
print("=== EX3")
V=Matrix([[2,1,1],[0,0,1],[1,1,0]]); print("detV",V.det())
b1=Matrix([0,2,-2]); b2=Matrix([2,-2,2]); b3=Matrix([0,2,0])
print(b1+2*b2+b3, b2+b3, b1+b2+b3, "detb",Matrix.hstack(b1,b2,b3).det())
print("=== EX4")
P=3*(x+y+1)**2+(x-y-3); print(expand(P))
F=Matrix([Rational(23,24),Rational(-47,24)])
X,Y=symbols('X Y')
# param point on parabola: check focus-directrix
d2F=(x-F[0])**2+(y-F[1])**2; d2D=(12*x-12*y-37)**2/288
print("focus-dir check:", simplify(expand(d2F-d2D)) , "vs P*const:", factor(expand(d2F-d2D)))
sub={x:(X-Y)/sqrt(2)-2, y:(X+Y)/sqrt(2)-1}
# inverse of X=(x+y+1)/sqrt2, Y=(-x+y+3)/sqrt2: x+y=sqrt2 X-1, -x+y=sqrt2 Y-3
xs=((sqrt(2)*X-1)-(sqrt(2)*Y-3))/2; ys=((sqrt(2)*X-1)+(sqrt(2)*Y-3))/2
print("xs,ys",simplify(xs),simplify(ys))
print("normal form:", expand(P.subs({x:xs,y:ys})))
print("=== EX5")
A=Matrix([[3,-4],[2,-3]]); b=Matrix([8,-4]); print(A.det(),A.eigenvects(), A**2, (A+eye(2))*b)
print(solve([3*x-4*y+8-x,2*x-3*y-4-y],[x,y]))
p=A*Matrix([8,0])+b; print("f(8,0)",p.T)
c=symbols('c'); xp=3*x-4*y+8; yp=2*x-3*y-4
print("x-2y ->",expand(xp-2*yp)," x-y ->",expand(xp-yp))
