#Fermats theorum for testing prime numbers
#Function to take in an integer q such that q>3 and k a set of integers to test between 2 and q-2
#Return composite if the number is composite, otherwise return prime

def FermatTestForPrime(q, k):
    for i in k:
        if (i ** (q-1)) % q != 1:
            return False
    return True

def main():
    q = 221
    k = [38]
    result = FermatTestForPrime(q, k)
    if result:
        print(q, 'is a prime number')
    else:
        print(q, 'is a composite number')

if __name__ == "__main__":
    main()
        