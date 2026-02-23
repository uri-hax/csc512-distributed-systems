import math


# Return False if x^n + y^n = z^n and x, y, and z are integers
#Otherwise return True

def FermatTheorumFunction(x, y, n):
    sum = math.pow(x, n) + math.pow(y, n)
    z = sum ** (1/n)
    print(z)

    if z.is_integer():
        return True
    else:
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