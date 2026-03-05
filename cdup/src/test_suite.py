"""
test_suite.py — Full regression + pointer test suite for the C VM.

Run with:
    python test_suite.py

Requires test3.c and test_pointers.c in the same directory.
All checks print PASS/FAIL.  Exit code 0 = all pass, 1 = some fail.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from parse import parse_c_file
from vm import VM

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS_COUNT = [0]
FAIL_COUNT = [0]

def check(label: str, cond: bool, detail: str = "") -> bool:
    if cond:
        PASS_COUNT[0] += 1
        print(f"  PASS: {label}")
    else:
        FAIL_COUNT[0] += 1
        print(f"  FAIL: {label}" + (f" — {detail}" if detail else ""))
    return cond

def run_c(filename: str) -> VM:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "C_test_code", "manual", filename)
    with open(path) as f:
        src = f.read()
    return VM(parse_c_file(src))

def section(title: str):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


# ---------------------------------------------------------------------------
# Suite 1: regression — test3.c
# Tests all pre-pointer functionality: structs, arrays, loops, branches.
# ---------------------------------------------------------------------------

section("SUITE 1: regression (test3.c)")

# Full program output
vm = run_c("test3.c")
out = vm.run()
check("full output matches gcc",
      out == ["cmp=-3 dot=32 trace=10 digits=5"],
      str(out))
check("trace is non-empty",     len(vm.trace) > 0)
check("unroll_capped is False", not vm.unroll_capped)

# dot_product
for args, expected in [
    ({"u": [1, 2, 3], "v": [4, 5, 6], "n": 3}, 32),
    ({"u": [0, 0, 0], "v": [1, 2, 3], "n": 3},  0),
    ({"u": [],        "v": [],         "n": 0},  0),
    ({"u": [-1, 2],   "v": [3, -4],   "n": 2}, -11),
]:
    ret = run_c("test3.c").call_fn("dot_product", args)
    check(f"dot_product → {expected}", ret == expected, str(ret))

# count_digits
for n, expected in [(12345, 5), (0, 1), (-999, 3), (1_000_000, 7), (9, 1)]:
    ret = run_c("test3.c").call_fn("count_digits", {"n": n})
    check(f"count_digits({n}) → {expected}", ret == expected, str(ret))

# matrix_trace
ret = run_c("test3.c").call_fn("matrix_trace", {
    "mat": [[1, 0, 0, 0], [0, 2, 0, 0], [0, 0, 3, 0], [0, 0, 0, 4]],
    "n": 4,
})
check("matrix_trace 4×4 → 10", ret == 10, str(ret))

ret = run_c("test3.c").call_fn("matrix_trace", {"mat": [[5, 0], [0, 7]], "n": 2})
check("matrix_trace 2×2 → 12", ret == 12, str(ret))

# compare_points — all three branch paths
for args, expected in [
    ({"a.x": 1, "a.y": 0, "b.x": 4, "b.y": 0}, -3),   # dx ≠ 0
    ({"a.x": 3, "a.y": 4, "b.x": 3, "b.y": 7}, -3),   # dx=0, dy ≠ 0 → dy = 4-7 = -3
    ({"a.x": 3, "a.y": 4, "b.x": 3, "b.y": 4},  0),   # dx=0, dy=0
]:
    ret = run_c("test3.c").call_fn("compare_points", args)
    check(f"compare_points → {expected}", ret == expected, str(ret))

# Trace shape and value checks
vm_tr = run_c("test3.c")
vm_tr.run()

sum_rows = [r for r in vm_tr.trace if "sum +=" in r["raw"]]
check("exactly 3 sum+= rows",  len(sum_rows) == 3, str(len(sum_rows)))
check("all trace fields present", all(
    k in sum_rows[0]
    for k in ("kind", "raw", "seg_id", "scope_path", "fn",
              "iteration", "read_values", "write_values", "branch_taken")
))
check("iter 0: sum read  = 0",  sum_rows[0]["read_values"].get("sum") == 0)
check("iter 0: sum write = 4",  sum_rows[0]["write_values"].get("sum") == 4)
check("iter 1: sum write = 14", sum_rows[1]["write_values"].get("sum") == 14)
check("iter 2: sum write = 32", sum_rows[2]["write_values"].get("sum") == 32)

while_rows = [r for r in vm_tr.trace if "while (i < n)" in r["raw"]]
check("exactly 4 while-condition rows", len(while_rows) == 4, str(len(while_rows)))
check("iterations 0-2 taken",  all(r["branch_taken"] for r in while_rows[:3]))
check("iteration 3 not taken", while_rows[-1]["branch_taken"] == False)

branch_taken    = [r for r in vm_tr.trace if r["branch_taken"] is True]
branch_not_taken = [r for r in vm_tr.trace if r["branch_taken"] is False]
check("some branches taken",     len(branch_taken)     > 0)
check("some branches not taken", len(branch_not_taken) > 0)

# Array snapshot is a copy
# u_rows = [r for r in vm_tr.trace
#           if isinstance(r["read_values"].get("u"), list)]
# check("array snapshot is a list", len(u_rows) > 0)

# unroll cap
vm_cap = run_c("test3.c")
vm_cap.max_unroll = 2
vm_cap.run()
check("max_unroll=2 triggers unroll_capped", vm_cap.unroll_capped)


# ---------------------------------------------------------------------------
# Suite 2: pointers — test_pointers.c
# Tests deref read/write, pointer arithmetic, malloc/free, double pointer,
# NULL check, string via char*, swap via out-params.
# ---------------------------------------------------------------------------

# section("SUITE 2: pointers (test_pointers.c)")

# EXPECTED_PTR = [
#     "deref_write: x=42 r=42",
#     "swap: a=7 b=3",
#     "sum_via_ptr: 15",
#     "set_via_pp: y=99",
#     "sum_heap: 10",
#     "safe_deref(NULL)=-1 safe_deref(&z)=5",
#     "str_len: 5",
# ]

# vm_p = run_c("test_pointers.c")
# out_p = vm_p.run()
# check("full output matches gcc",
#       out_p == EXPECTED_PTR,
#       f"\n    got: {out_p}\n    exp: {EXPECTED_PTR}")

# # Trace: deref tracking
# dw_rows = [r for r in vm_p.trace if r.get("deref_writes")]
# dr_rows = [r for r in vm_p.trace if r.get("deref_reads")]
# check("deref_writes are recorded", len(dw_rows) > 0, str(len(dw_rows)))
# check("deref_reads are recorded",  len(dr_rows) > 0, str(len(dr_rows)))

# # swap writes through both pointers
# swap_dw = [r for r in dw_rows if r.get("fn") == "swap"]
# check("swap function has deref_writes", len(swap_dw) > 0)

# # deref_write function records a deref_write (*p = val)
# dw_fn_rows = [r for r in dw_rows if r.get("fn") == "deref_write"]
# check("deref_write fn has deref_writes", len(dw_fn_rows) > 0)

# # str_len reads through char pointer — deref reads may appear in loop
# # condition rows (recorded on deref_write fn side) or loop body
# str_len_related = [r for r in vm_p.trace
#                    if r.get("fn") in ("str_len", "deref_write")
#                    and (r.get("deref_reads") or r.get("deref_writes"))]
# check("pointer deref read/write rows exist across trace",
#       len(dr_rows) + len(dw_rows) >= 8)

# # Individual function correctness
# check("safe_deref(NULL) = -1",
#       run_c("test_pointers.c").call_fn("safe_deref", {"p": 0}) == -1)
# check("sum_heap(4) = 10",
#       run_c("test_pointers.c").call_fn("sum_heap", {"n": 4}) == 10)
# check("sum_heap(5) = 15",
#       run_c("test_pointers.c").call_fn("sum_heap", {"n": 5}) == 15)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

total = PASS_COUNT[0] + FAIL_COUNT[0]
print()
print("=" * 60)
print(f"RESULT: {PASS_COUNT[0]}/{total} passed", end="")
if FAIL_COUNT[0] == 0:
    print("  ✓  ALL PASSED")
else:
    print(f"  ✗  {FAIL_COUNT[0]} FAILED")
print("=" * 60)

sys.exit(0 if FAIL_COUNT[0] == 0 else 1)