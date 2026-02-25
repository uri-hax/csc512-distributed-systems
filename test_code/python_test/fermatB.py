import math

# Return False if x^n + y^n = z^n and x, y, and z are integers
#Otherwise return True

def FermatTheorumFunction(x, y, n):
    for i in range(1, 101):
        for j in range(1, 101):
            for k in range(3, 6):
                sum = math.pow(i, k) + math.pow(j, k)
                z = sum ** (1/k)
                if z.is_integer():
                    return True
    return False

def main(): 
    #print True if there exists x, y, and n that make Fermat's last theorum wrong
    #otherwise print False
    x = 5
    y = 3
    n = 2
    solution = FermatTheorumFunction(x, y, n)
    print('Fermats last theorum returned: ', solution)

if __name__ == "__main__":
    main()