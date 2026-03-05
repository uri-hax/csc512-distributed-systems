#Generate all prime numbers up to n
#using the sieve of Eratosthenes algothrithm

def GetAllPrimesUsingSieveOfE(n):
    #Generate a list of n numbers
    numberList = list(range(2,n))
    #Generate a second list to keep track of whether a number is prime or not
    isPrime = [True] * (n-2)
    #Go through and set the list isPrime to be true if the number is prime
    for i in range(0, len(numberList)):
        if isPrime[i]:
            #Set all multiples of the number to be false
            for j in range(i + numberList[i], len(numberList), numberList[i]):
                isPrime[j] = False
    #Go through and create a filtered list of numbers based on who is prime or not
    primeNumberList = []
    for i in range(0, len(numberList)):
        if isPrime[i]:
            primeNumberList.append(numberList[i])
    return primeNumberList

def main():
    n = 30
    primes = GetAllPrimesUsingSieveOfE(n)
    print(primes)

if __name__ == "__main__":
    main()
