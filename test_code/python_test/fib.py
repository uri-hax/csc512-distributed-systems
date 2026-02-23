
def FibonacciFunction(n):
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        return FibonacciFunction(n-1) + FibonacciFunction(n-2)
    
def main():
    n = 40
    result = FibonacciFunction(n)
    print(result)

if __name__ == "__main__":
    main()