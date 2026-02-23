import math

def GetAllPrimesUsingWilsonTest(n):
    #Generate a list of n numbers
    numberList = list(range(2,n))
    #Generate a second list to keep track of whether a number is prime or not
    isPrime = [True] * (n-2)
    for i in range(0, len(numberList)):
        #Use Wilson's theorem to check if the number is prime (n-1)! + 1 % n == 0
        if (math.factorial(numberList[i] - 1) + 1) % numberList[i] != 0:
            isPrime[i] = False
    primeNumberList = []
    for i in range(0, len(numberList)):
        if isPrime[i]:
            primeNumberList.append(numberList[i])
    return primeNumberList

def main():
    n = 30
    primes = GetAllPrimesUsingWilsonTest(n)
    print(primes)

if __name__ == "__main__":
    main()