# Non recursive Fibonacci function
import numpy as np


def FibonacciFunctionNR(num):
    An = ((1 + np.sqrt(5)) / 2) ** num
    Bn = ((1 - np.sqrt(5)) / 2) ** num
    result = (An - Bn) / np.sqrt(5)
    return int(result)

def main():
    n = 40
    result = FibonacciFunctionNR(n)
    print(result)

if __name__ == "__main__":
    main()