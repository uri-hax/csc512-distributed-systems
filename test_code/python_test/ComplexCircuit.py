# Build a complex circuit in Python

# function for a three input and gate
def And3(A,B,C):
    return A and B and C
    
# function for a three input nand gate
def Nand3(A,B,C):
    return not (A and B and C)
    
# function for the XOR gate
def XOR(A,B):
    return A != B
    
# function to create the circuit
def ComplexCircuit(A,B):
    #Circuit will take two inputs A and B and produce outputs C,D,E,F,G,H,J, and K.
    # No if or case statements allowed
    C = not B
    D = not (A and B)
    E = A or C
    F = not (A and B)
    G = XOR(D, E)
    H = Nand3(E, F, G)
    J = XOR(D, G)
    K = And3(E, H, J)
    return C, D, E, F, G, H, J, K


A = [True, False]
B = [True, False]
for i in A:
    for j in B:
        print("Value of A=", i)
        print("Value of B=", j)
        C, D, E, F, G, H, J, K = ComplexCircuit(i, j)
        print("Value of C=", C)
        print("Value of D=", D)
        print("Value of E=", E)
        print("Value of F=", F)
        print("Value of G=", G)
        print("Value of H=", H)
        print("Value of J=", J)
        print("Value of K=", K)
        print("=====================================")

