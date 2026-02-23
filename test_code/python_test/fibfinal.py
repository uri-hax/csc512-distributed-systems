from sympy import *

A = Symbol('A')
B = Symbol('B')
k = Symbol('k')

F = (A**(k-1)*(1+A)-B**(k-1)*(1+B))
F = expand(F)

print(F)