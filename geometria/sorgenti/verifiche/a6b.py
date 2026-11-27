from sympy import *
x,y,X,Y,t=symbols('x y X Y t')
print("=== EX4")
Cn=x**2+2*sqrt(3)*x*y+3*y**2-8*y+5
M=Matrix([[1,sqrt(3)],[sqrt(3),3]]); print(M.eigenvects())
# rotation: X along (sqrt3/2,-1/2)?  use u=(-sqrt3,1)/2 (null dir), v=(1,sqrt3)/2
u=Matrix([-sqrt(3),1])/2; v=Matrix([1,sqrt(3)])/2
sub={x:X*u[0]+Y*v[0], y:X*u[1]+Y*v[1]}; R=expand(Cn.subs(sub)); print("rotated:",R)
# vertex: complete square
print(factor(R))
