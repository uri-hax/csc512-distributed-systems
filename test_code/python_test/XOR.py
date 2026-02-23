# Program a XOR function

def XOR(A,B):
    return A != B
    
A = [True, False]
B = [True, False]

for i in A:
    for j in B:
        output = XOR(i,j)
        print("A = ", i, "B = ", j, "Output = ", output)