"""VM execution kernel for resolved expression trees.

:class:`VMKernel` evaluates a resolved expr tree — one where ``{"name": ...}``
leaves have been replaced by ``{"slot": "root.fn.x"}`` by ``matrix.py`` —
against a frame dict that maps scoped slot names to their current values.

The kernel is designed to be swappable:

- ``VMKernel``            — returns computed Python values (int, float, …).
- *(future)* LaTeXKernel  — returns LaTeX strings.
- *(future)* NumpyKernel  — returns NumPy expressions.

Usage::

    kernel = VMKernel()
    result = kernel.eval(expr_node, frame)

The frame is a plain dict: ``{"root.fn.x": 3, "root.fn.y": 4, ...}``.
Arrays are stored as lists: ``{"root.fn.u": [1, 2, 3]}``.

Raises:
    NameError: On unresolved ``{"name": ...}`` nodes.
    KeyError: When a slot is not present in the frame.
    ZeroDivisionError: On division or modulo by zero.
"""

import math


_MATH_BUILTINS: dict = {
    "exp":   lambda x: math.exp(x),
    "log":   lambda x: math.log(x),
    "log10": lambda x: math.log10(x),
    "sqrt":  lambda x: math.sqrt(x),
    "fabs":  lambda x: abs(x),
    "abs":   lambda x: abs(x),
    "pow":   lambda x, y: math.pow(x, y),
    "sin":   lambda x: math.sin(x),
    "cos":   lambda x: math.cos(x),
    "tan":   lambda x: math.tan(x),
    "floor": lambda x: math.floor(x),
    "ceil":  lambda x: math.ceil(x),
    "fmin":  lambda x, y: min(x, y),
    "fmax":  lambda x, y: max(x, y),
}


class VMKernel:
    """Evaluate a resolved expr tree against a frame (slot → value dict).

    All operator methods follow the C semantics: comparisons and logical
    operators return ``0`` or ``1``; integer division truncates toward zero;
    modulo sign follows the dividend.
    """

    def eval(self, node: dict, frame: dict):
        """
        Recursively evaluate an expr tree node.

        Args:
            node:  An expr tree node (resolved — contains "slot" not "name").
            frame: Dict mapping scoped slot names to current values.

        Returns:
            The computed value (int, float, list, etc.)
        """
        # Unresolved name — should not appear after matrix resolution
        if "name" in node:
            raise NameError(
                f"Unresolved identifier '{node['name']}' in expr tree. "
                "Run matrix._resolve_expr() before calling VMKernel.eval()."
            )

        # Resolved slot reference
        if "slot" in node:
            slot = node["slot"]
            if slot not in frame:
                raise KeyError(f"Slot '{slot}' not found in frame.")
            return frame[slot]

        # Literal constant
        if "const" in node:
            v = node["const"]
            t = node.get("type", "int")
            if t == "int":
                return int(v)
            if t == "float":
                return float(v)
            if t == "char":
                # Strip surrounding quotes if present, return ord
                s = str(v).strip("'")
                if s.startswith("\\"):
                    esc = {"\\n": 10, "\\t": 9, "\\r": 13, "\\0": 0,
                           "\\\\": 92, "\\'": 39}
                    return esc.get(s, 0)
                return ord(s) if len(s) == 1 else 0
            if t == "string":
                return str(v).strip('"')
            return v

        # Operation node
        op = node.get("op")
        if op is None:
            raise ValueError(f"Expr node has no 'op', 'slot', 'const', or 'name': {node}")

        args = node.get("args", [])

        # Dispatch
        method = getattr(self, f"op_{op}", None)
        if method is not None:
            evaled = [self.eval(a, frame) for a in args]
            # Pass extra fields for ops that need them (field name, cast type, fn name)
            extra = {}
            if op == "field":
                extra["field"] = node.get("field")
            if op == "cast":
                extra["type"] = node.get("type")
            if op == "call":
                extra["fn"]   = node.get("fn")
                extra["args_evaled"] = evaled
            return method(*evaled, **extra)

        raise ValueError(f"Unknown op '{op}' in expr tree.")

    # ── Arithmetic ────────────────────────────────────────────────────────────

    def op_add(self, a, b): return a + b
    def op_sub(self, a, b): return a - b
    def op_mul(self, a, b): return a * b

    def op_div(self, a, b):
        # C integer division truncates toward zero
        if b == 0:
            raise ZeroDivisionError("Division by zero in expr evaluation.")
        if isinstance(a, int) and isinstance(b, int):
            return int(a / b)   # truncate toward zero (Python // floors)
        return a / b

    def op_mod(self, a, b):
        if b == 0:
            raise ZeroDivisionError("Modulo by zero in expr evaluation.")
        # C modulo: result has same sign as dividend
        result = abs(a) % abs(b)
        return result if a >= 0 else -result

    def op_neg(self, a): return -a

    # ── Bitwise ───────────────────────────────────────────────────────────────

    def op_bit_and(self, a, b): return int(a) & int(b)
    def op_bit_or(self, a, b):  return int(a) | int(b)
    def op_bit_xor(self, a, b): return int(a) ^ int(b)
    def op_bit_not(self, a):    return ~int(a)
    def op_shl(self, a, b):     return int(a) << int(b)
    def op_shr(self, a, b):     return int(a) >> int(b)

    # ── Comparison (C-style: return 0 or 1) ──────────────────────────────────

    def op_cmp_eq(self, a, b): return int(a == b)
    def op_cmp_ne(self, a, b): return int(a != b)
    def op_cmp_lt(self, a, b): return int(a <  b)
    def op_cmp_le(self, a, b): return int(a <= b)
    def op_cmp_gt(self, a, b): return int(a >  b)
    def op_cmp_ge(self, a, b): return int(a >= b)

    # ── Logical (C-style: return 0 or 1) ─────────────────────────────────────

    def op_log_and(self, a, b): return int(bool(a) and bool(b))
    def op_log_or(self, a, b):  return int(bool(a) or  bool(b))
    def op_log_not(self, a):    return int(not bool(a))

    # ── Memory ────────────────────────────────────────────────────────────────

    def op_index(self, arr, idx):
        """arr[idx] — arr must be a list/tuple in the frame."""
        if not hasattr(arr, '__getitem__'):
            raise TypeError(f"Cannot index non-sequence value {arr!r}.")
        return arr[int(idx)]

    def op_field(self, obj, *, field):
        """
        obj.field — obj should be a dict in the frame (struct as dict).
        In practice, struct fields are stored as separate flat slots
        (root.fn.p1.x, root.fn.p1.y) so this op is rarely needed at VM level.
        Provided for completeness.
        """
        if isinstance(obj, dict):
            return obj[field]
        raise TypeError(f"Cannot access field '{field}' on {obj!r}.")

    # ── Type ops ──────────────────────────────────────────────────────────────

    def op_cast(self, a, *, type):
        """(type)a — numeric casts only."""
        if "int" in type or "long" in type or "short" in type or "char" in type:
            return int(a)
        if "float" in type or "double" in type:
            return float(a)
        return a  # unknown cast — pass through

    # ── Increment / decrement ─────────────────────────────────────────────────
    # These are handled at the statement level by the VM (they write back to
    # the frame), but the kernel implements them for completeness.

    def op_post_inc(self, a): return a      # value before increment
    def op_post_dec(self, a): return a      # value before decrement
    def op_pre_inc(self, a):  return a + 1
    def op_pre_dec(self, a):  return a - 1

    # ── Address / deref (stubs — not executable without memory model) ─────────

    def op_addr_of(self, a):
        raise NotImplementedError("Address-of operator not supported in VMKernel.")

    def op_deref(self, a):
        raise NotImplementedError("Pointer dereference not supported in VMKernel.")

    # ── Call ──────────────────────────────────────────────────────────────────

    def op_call(self, *_args, fn, args_evaled=None):
        """Evaluate an external C function call.

        A small set of C stdlib math functions are handled directly.
        Everything else raises :exc:`NotImplementedError`.  Override this
        method in a subclass to handle domain-specific or user-defined calls.

        Args:
            *_args: Positional evaluated arguments (used when ``args_evaled``
                is not provided).
            fn: Name of the C function being called.
            args_evaled: Pre-evaluated argument list (takes priority over
                ``*_args`` when provided).

        Returns:
            The computed result of the math function.

        Raises:
            NotImplementedError: If ``fn`` is not in the built-in math table.
        """
        evaled = args_evaled or list(_args)
        if fn in _MATH_BUILTINS:
            return _MATH_BUILTINS[fn](*evaled)
        raise NotImplementedError(
            f"External call '{fn}(...)' cannot be evaluated by VMKernel. "
            "Either provide source for this function or override op_call() "
            "in a subclass with a stub implementation."
        )

    # ── Sizeof (stub) ─────────────────────────────────────────────────────────

    def op_sizeof(self, **kwargs):
        """sizeof(type) — return a consistent unit size."""
        of = kwargs.get("of", "int")
        t = (of or "int").strip().rstrip("*").strip()
        if t == "char":   return 1
        if t == "short":  return 2
        if t in ("int", "unsigned", "long", "float"): return 4
        if t in ("double", "long long"):              return 8
        return 4