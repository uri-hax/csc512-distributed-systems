import numpy

def BanditArmA(n):
    out = numpy.random.randint(0,n)
    return out

def BanditArmB(n):
    out = numpy.random.randint(0,n)
    if out > (n/2):
        out = n/2
    else:
        out = 0
    return out

def BanditArmC(n):
    h = 0
    for i in range(n):
        if round(numpy.random.binomial(1,0.5)) == 1:
            h += 1
        v = 0
        if round(numpy.random.binomial(1,0.3)) == 1:
            v += 1
    out = h + v
    return out

numTrials = 100
bestResult = numpy.zeros(3)
for i in range(numTrials):
    n = 50
    A = BanditArmA(n)
    B = BanditArmB(n)
    C = BanditArmC(n)
    results = [A,B,C]
    bestResult[numpy.argmax(results)] += 1

best = numpy.argmax(bestResult)
if best == 0:
    print('A')
elif best == 1:
    print('B')
else:
    print('C')
    



# def main():
#     n = 50
#     print(BanditArmA(n))
#     print(BanditArmB(n))
#     print(BanditArmC(n))

# if __name__ == "__main__":
#     main()