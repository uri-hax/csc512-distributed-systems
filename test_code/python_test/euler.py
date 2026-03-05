import math
#Let a^4+b^4+c^4 = d^4, given a, b, and c solve for d.
#Return true if d is an integer, otherwise return false.

def EulersABCDTheorum(a, b, c):
    #solve for d and check if it is an integer
    d = (math.pow(a, 4) + math.pow(b, 4) + math.pow(c, 4)) ** (1/4)
    print(d)
    if d.is_integer():  
        return True
    else:
        return FalseHHeath
    
def main():
    a = 95800
    b = 217519
    c = 414560
    solution = EulersABCDTheorum(a, b, c)
    print(solution)

if __name__ == "__main__":
    main()