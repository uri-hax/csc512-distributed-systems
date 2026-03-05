from run_chaos import run_chaos_on_file

result = run_chaos_on_file("/Users/sofiamancini/Desktop/Documents/Spring2026/CSC512/csc512-distributed-systems/test_code/long_runner.c", "memory_squeeze", timeout=90)
rc, out, err = result.as_tuple() 
result.print_report()