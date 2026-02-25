P = False
Q = False

def arrow(A, B):
    solution = ((not A) and (not B)) or ((not A) and B) or (A and B)
    return solution

A = P 
B = Q
X = arrow(A, B)
print(X)