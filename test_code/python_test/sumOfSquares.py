def sum_of_squares(numbers):
    if not numbers:
        return 0
    first, *rest = numbers
    return (first * first if first >= 0 else 0) + sum_of_squares(rest)

    
def read_test_case(N):
    if N == 0:
        return []
    X = int(input())
    numbers = list(map(int, input().split()))
    result = sum_of_squares(numbers)
    return [result] + read_test_case(N - 1)
    
def print_results(results, N):
    if N == 0:
        return
    print(results[0])
    print_results(results[1:], N - 1)
        

def main():
    N = int(input())
    results = read_test_case(N)
    print_results(results, N)

main()
