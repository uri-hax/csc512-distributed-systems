"""Tree-walking interpreter for parsed C/Java IR code.

Frame model
───────────
Each slot in a frame is a descriptor dict:
    {"addr": int, "value": any, "type": str}

  addr:  unique integer address assigned at slot creation.
         Stack slots get addresses from a per-call counter.
         Heap slots get addresses from the global heap counter.
  value: the Python value held by this slot (int, float, list, str, or an
         address integer for pointer-typed slots).
  type:  C type string — "int", "float", "int*", "char*", "struct Point", etc.
         Used by pointer arithmetic (sizeof) and by the trace.

Public API (unchanged from before the refactor):
    vm = VM(parsed_json_str)
    vm = VM(parsed_json_str, max_unroll=1000)
    output = vm.run()               # execute main(), return output lines
    val    = vm.call_fn("fn", {})   # bare-value arg dict — wrapped internally
    trace  = vm.trace
    capped = vm.unroll_capped

call_fn still accepts bare values {"n": 3, "u": [1,2,3]} — it wraps them
into descriptors internally so callers don't need to know about the frame
structure.

Pointer model
─────────────
  &x          → frame["x"]["addr"]      (an integer)
  *p          → heap/frame lookup by address
  p + n       → p_addr + n * _sizeof(pointee_type)
  malloc(n)   → allocates n * sizeof(T) bytes in heap, returns base address
  free(p)     → marks heap region free (no-op in practice — GC'd by Python)

Heap:
    self._heap      : addr → value   (byte-addressed, but we store slot-sized values)
    self._heap_meta : addr → type    (type of the value at that address)
    self._addr_map  : addr → (frame_dict, slot_name)  for stack slots

Trace additions:
    "deref_reads":  {addr: value, ...}   — addresses read through *p
    "deref_writes": {addr: value, ...}   — addresses written through *p
"""

import re
import json

try:
    from .kernel import VMKernel
    from .expr   import parse_expr, build_assign_expr
except ImportError:
    from kernel import VMKernel
    from expr   import parse_expr, build_assign_expr


# ---------------------------------------------------------------------------
# Control-flow exceptions
# ---------------------------------------------------------------------------

class _Return(Exception):
    """Raised to implement a ``return`` statement inside the interpreter."""

    def __init__(self, value):
        self.value = value


class _Break(Exception):
    """Raised to implement a ``break`` statement inside the interpreter."""


class _Continue(Exception):
    """Raised to implement a ``continue`` statement inside the interpreter."""


# ---------------------------------------------------------------------------
# Sentinel for NULL
# ---------------------------------------------------------------------------
NULL = 0   # NULL pointer is address 0; heap starts at 1


# ---------------------------------------------------------------------------
# Initialiser parser  (unchanged)
# ---------------------------------------------------------------------------

def _parse_initializer(raw_rhs: str):
    """Parse a C initialiser RHS string into a Python value.

    Handles integer literals, float literals, quoted strings, and brace-list
    initialisers (delegated to :func:`_parse_brace`).

    Args:
        raw_rhs: The right-hand-side text of a declaration, e.g. ``"42"``,
            ``"3.14"``, ``"{1, 2, 3}"``, or ``'"hello"'``.

    Returns:
        An ``int``, ``float``, ``str``, or ``list`` value.
    """
    s = raw_rhs.strip()
    if s.startswith("{"):
        return _parse_brace(s)
    try:
        return int(s, 0)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if s.startswith('"'):
        return s[1:-1]   # strip quotes, keep content
    return s

def _parse_brace(s: str) -> list:
    """Parse a C brace-list initialiser into a nested Python list.

    Handles nested brace lists (2-D arrays, struct initialisers).

    Args:
        s: A brace-delimited initialiser string, e.g. ``"{1, {2, 3}, 4}"``.

    Returns:
        A (possibly nested) list of ``int``, ``float``, or ``str`` values.
    """
    s = s.strip()
    if not s.startswith("{"):
        return _parse_initializer(s)
    inner = s[1:-1].strip()
    if not inner:
        return []
    elements, depth, current = [], 0, ""
    for ch in inner:
        if ch == "{":   depth += 1; current += ch
        elif ch == "}": depth -= 1; current += ch
        elif ch == "," and depth == 0:
            elements.append(current.strip()); current = ""
        else:
            current += ch
    if current.strip():
        elements.append(current.strip())
    result = []
    for elem in elements:
        elem = elem.strip()
        if elem.startswith("{"):
            result.append(_parse_brace(elem))
        else:
            try:    result.append(int(elem, 0))
            except ValueError:
                try:    result.append(float(elem))
                except ValueError: result.append(elem)
    return result

def _extract_rhs(raw: str):
    """Extract the right-hand side of an assignment or declaration statement.

    Args:
        raw: A raw statement string such as ``"int x = 42;"`` or ``"x = y + 1;"``.

    Returns:
        The substring after the ``=`` sign, stripped of whitespace, or
        ``None`` if no ``=`` is found.
    """
    s = raw.strip().rstrip(";").replace("{}", "").strip()
    eq = s.find("=")
    return s[eq + 1:].strip() if eq >= 0 else None

def _extract_for_update(raw: str):
    """Extract the update clause from a ``for`` loop header string.

    Args:
        raw: A raw loop-head statement such as
            ``"for (int i = 0; i < n; i++) {}"``.

    Returns:
        The update clause string (e.g. ``"i++"``) or ``None`` if the
        statement is not a ``for`` loop or has fewer than three clauses.
    """
    s = raw.strip()
    if not s.startswith("for"):
        return None
    try:
        start = s.index("(") + 1
        depth, i = 1, start
        while i < len(s) and depth > 0:
            if s[i] == "(": depth += 1
            elif s[i] == ")": depth -= 1
            i += 1
        parts = s[start:i-1].split(";", 2)
        return parts[2].strip() if len(parts) == 3 else None
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Scope helpers  (unchanged)
# ---------------------------------------------------------------------------

def _strip_scope(scoped: str, scope_prefix: str) -> str:
    """Remove a scope prefix from a scoped slot name.

    Args:
        scoped: Fully-qualified slot name, e.g. ``"root.fn.x"``.
        scope_prefix: Prefix to strip, e.g. ``"root.fn"``.

    Returns:
        The bare name (e.g. ``"x"``), or ``scoped`` unchanged if the prefix
        does not match.
    """
    prefix = scope_prefix + "."
    return scoped[len(prefix):] if scoped.startswith(prefix) else scoped


# ---------------------------------------------------------------------------
# sizeof helper
# ---------------------------------------------------------------------------

def _sizeof(type_str: str) -> int:
    """Return a consistent unit size for pointer arithmetic."""
    t = (type_str or "int").strip().rstrip("*").strip()
    if t == "char":  return 1
    if t == "short": return 2
    if t in ("int", "unsigned", "long", "float"): return 4
    if t in ("double", "long long"): return 8
    return 4   # default for unknown types / structs


def _pointee_type(ptr_type: str) -> str:
    """'int*' -> 'int',  'char**' -> 'char*'"""
    s = ptr_type.strip()
    if s.endswith("*"):
        return s[:-1].strip()
    return "int"


def _is_pointer_type(type_str: str) -> bool:
    """Return ``True`` if ``type_str`` denotes a pointer type (ends with ``*``).

    Args:
        type_str: A C type string such as ``"int*"`` or ``"char**"``.

    Returns:
        ``True`` if the type ends with ``*``, ``False`` otherwise.
    """
    return type_str is not None and type_str.strip().endswith("*")


# ---------------------------------------------------------------------------
# Frame helpers
# ---------------------------------------------------------------------------

def _fget(frame: dict, name: str):
    """Return the current value of a named slot in a frame.

    Args:
        frame: The active variable frame mapping slot name to descriptor dict.
        name: The slot name to look up.

    Returns:
        The Python value stored in the slot.

    Raises:
        KeyError: If ``name`` is not present in ``frame``.
    """
    return frame[name]["value"]

def _fset(frame: dict, name: str, value, addr_counter=None,
          type_str: str = "int"):
    """
    Set a named slot. Creates the descriptor if it doesn't exist yet.
    addr_counter: a list [n] used as a mutable counter for address assignment.
    """
    if name in frame:
        frame[name]["value"] = value
        if type_str and type_str != "int":
            frame[name]["type"] = type_str
    else:
        addr = addr_counter[0] if addr_counter else 0
        if addr_counter:
            addr_counter[0] += 1
        frame[name] = {"addr": addr, "value": value, "type": type_str}

def _fget_type(frame: dict, name: str) -> str:
    """Return the C type string of a named slot, defaulting to ``"int"``.

    Args:
        frame: The active variable frame.
        name: The slot name to look up.

    Returns:
        The type string, or ``"int"`` if the slot is absent or untyped.
    """
    return frame.get(name, {}).get("type", "int")

def _faddr(frame: dict, name: str) -> int:
    """Return the virtual address of a named slot in a frame.

    Args:
        frame: The active variable frame.
        name: The slot name to look up.

    Returns:
        The integer address assigned to the slot.

    Raises:
        KeyError: If ``name`` is not present in ``frame``.
    """
    return frame[name]["addr"]


# ---------------------------------------------------------------------------
# Snapshot helpers  (updated for descriptor frames)
# ---------------------------------------------------------------------------

def _snap_reads(names: list, frame: dict) -> dict:
    """Snapshot the current values of a list of slot names (read side).

    Args:
        names: List of scoped slot names to snapshot.
        frame: The active variable frame.

    Returns:
        Dict mapping each present slot name to a copy of its current value
        (lists are shallow-copied to avoid aliasing in the trace).
    """
    snap = {}
    for n in names:
        if n in frame:
            v = frame[n]["value"]
            snap[n] = list(v) if isinstance(v, list) else v
    return snap

def _snap_writes(names: list, frame: dict) -> dict:
    """Snapshot the current values of a list of slot names (write side).

    Semantically identical to :func:`_snap_reads`; kept as a separate function
    for clarity in call sites where we record post-write state.

    Args:
        names: List of scoped slot names to snapshot.
        frame: The active variable frame.

    Returns:
        Dict mapping each present slot name to a copy of its current value.
    """
    snap = {}
    for n in names:
        if n in frame:
            v = frame[n]["value"]
            snap[n] = list(v) if isinstance(v, list) else v
    return snap


# ---------------------------------------------------------------------------
# VM
# ---------------------------------------------------------------------------

class VM:
    """Tree-walking interpreter over parsed C/Java IR JSON.

    Attributes:
        segments: List of segment dicts from the parsed IR.
        kernel: :class:`VMKernel` instance used for expression evaluation.
        max_unroll: Maximum loop iterations before capping.
        output: Accumulated ``printf`` output lines from execution.
        trace: List of trace event dicts recorded during execution.
        unroll_capped: ``True`` if any loop hit the ``max_unroll`` limit.

    Note:
        :meth:`call_fn` accepts bare-value arg dicts for backwards
        compatibility (``{"u": [1,2,3], "n": 3}``). Internally all frame
        slots are stored as descriptor dicts
        ``{"addr": int, "value": any, "type": str}``.
    """

    def __init__(self, parsed_json_str: str, max_unroll: int = 10_000):
        data = json.loads(parsed_json_str)
        self.segments      = data["segments"]
        self.kernel        = VMKernel()
        self.max_unroll    = max_unroll
        self.output        = []
        self.trace         = []
        self.unroll_capped = False

        self._seg_by_id  = {s["id"]: s for s in self.segments}
        self._fn_by_name = {s["name"]: s for s in self.segments
                            if s["type"] == "function"}
        self._struct_fields = {
            s["name"]: [m["name"] for m in s.get("memory", [])]
            for s in self.segments if s["type"] == "struct"
        }
        # struct field types: struct_name -> {field_name -> type_str}
        self._struct_field_types = {
            s["name"]: {m["name"]: m.get("type","int")
                        for m in s.get("memory", [])}
            for s in self.segments if s["type"] == "struct"
        }
        self._children = {}
        for seg in self.segments:
            pid, sid = seg["parent"], seg["id"]
            if sid != pid:
                self._children.setdefault(pid, []).append(sid)
        for pid in self._children:
            self._children[pid].sort()

        self._seg_fn = {seg["id"]: self._owning_fn(seg) for seg in self.segments}

        # ── Virtual address space ─────────────────────────────────────────
        # Stack addresses start at 0x1000, heap at 0x8000_0000.
        # We use simple counters — no real layout needed.
        self._stack_counter = [0x1000]
        self._heap_counter  = [0x8000_0000]
        # heap: addr -> {"value": v, "type": t}
        self._heap          = {}
        # reverse map: addr -> (frame_dict, slot_name) for stack slots
        self._addr_map      = {}

    def _owning_fn(self, seg: dict) -> str:
        """Walk up the segment tree to find the enclosing function name.

        Args:
            seg: A segment dict from the parsed IR.

        Returns:
            The name of the nearest ancestor ``function`` segment, or
            ``"root"`` if no such ancestor exists.
        """
        s = seg
        while True:
            if s["type"] == "function":
                return s.get("name", "unknown")
            pid = s["parent"]
            if pid == s["id"]:
                return "root"
            s = self._seg_by_id[pid]

    # ── Address space helpers ─────────────────────────────────────────────────

    def _alloc_stack_slot(self, frame: dict, name: str, value, type_str: str):
        """Create a new named stack slot with a unique address."""
        addr = self._stack_counter[0]
        self._stack_counter[0] += 1
        frame[name] = {"addr": addr, "value": value, "type": type_str}
        self._addr_map[addr] = (frame, name)

    def _write_slot(self, frame: dict, name: str, value):
        """Write to an existing named slot (doesn't change addr or type)."""
        frame[name]["value"] = value

    def _alloc_heap(self, n_bytes: int, elem_type: str = "int") -> int:
        """
        Allocate n_bytes on the heap. Returns base address.
        We store one value per sizeof(elem_type) bytes — i.e. n_bytes/sizeof
        elements. For simplicity we always allocate n_elements = n_bytes
        (treating each 'byte' as one addressable slot).
        """
        base = self._heap_counter[0]
        sz = _sizeof(elem_type)
        n_elems = max(1, n_bytes // sz)
        for i in range(n_elems):
            addr = base + i
            self._heap[addr] = {"value": 0, "type": elem_type}
        self._heap_counter[0] = base + n_elems
        return base

    def _heap_read(self, addr):
        """Read a value from the heap at addr."""
        # String passed as char* — intern it first
        if isinstance(addr, str):
            addr = self._intern_string(addr)
        addr = int(addr)
        if addr == NULL:
            raise RuntimeError("Null pointer dereference")
        if addr in self._heap:
            return self._heap[addr]["value"]
        # Check stack via addr_map
        if addr in self._addr_map:
            frame, name = self._addr_map[addr]
            return frame[name]["value"]
        raise RuntimeError(f"Invalid read at address 0x{addr:x}")

    def _heap_write(self, addr: int, value):
        """Write a value to the heap or stack at addr."""
        if addr == NULL:
            raise RuntimeError("Null pointer dereference")
        if addr in self._heap:
            self._heap[addr]["value"] = value
            return
        if addr in self._addr_map:
            frame, name = self._addr_map[addr]
            frame[name]["value"] = value
            return
        raise RuntimeError(f"Invalid write at address 0x{addr:x}")

    def _addr_type(self, addr: int) -> str:
        if addr in self._heap:
            return self._heap[addr].get("type", "int")
        if addr in self._addr_map:
            frame, name = self._addr_map[addr]
            return frame[name].get("type", "int")
        return "int"

    def _intern_string(self, s: str) -> int:
        """
        Store a string in the heap as null-terminated char values.
        Returns the base address (a char* value).
        """
        base = self._heap_counter[0]
        for i, ch in enumerate(s):
            addr = base + i
            self._heap[addr] = {"value": ord(ch), "type": "char"}
        # null terminator
        self._heap[base + len(s)] = {"value": 0, "type": "char"}
        self._heap_counter[0] = base + len(s) + 1
        return base

    def _list_to_heap(self, lst: list, elem_type: str = "int") -> int:
        """
        Copy a Python list into the heap as contiguous slots.
        Returns the base address. Handles nested lists (2D arrays) by
        storing sub-lists recursively and storing their base addresses.
        """
        base = self._heap_counter[0]
        for i, item in enumerate(lst):
            addr = base + i
            if isinstance(item, list):
                # 2D array row: store as a sub-array, keep pointer to it
                sub_base = self._list_to_heap(item, elem_type)
                self._heap[addr] = {"value": sub_base, "type": elem_type + "*"}
            else:
                self._heap[addr] = {"value": item, "type": elem_type}
        self._heap_counter[0] = base + len(lst)
        return base

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> list:
        """Execute main(), return captured output lines."""
        self.output = []; self.trace = []; self.unroll_capped = False
        self._stack_counter[0] = 0x1000
        self._heap_counter[0]  = 0x8000_0000
        self._heap.clear()
        self._addr_map.clear()
        self.call_fn("main", {})
        return self.output

    def call_fn(self, fn_name: str, arg_frame: dict):
        """
        Call a named function with a bare-value arg dict.
        Wraps bare values into frame descriptors internally.
        Returns the function's return value or None.
        """
        seg = self._fn_by_name.get(fn_name)
        if seg is None:
            raise NameError(f"Function '{fn_name}' not found.")
        # Wrap bare values into descriptors
        frame = {}
        for k, v in arg_frame.items():
            type_str = self._infer_type(v)
            self._alloc_stack_slot(frame, k, v, type_str)
        try:
            self._exec_seg(seg, frame, iteration=None)
        except _Return as r:
            return r.value
        return None

    def _infer_type(self, value) -> str:
        """Infer a C type string from a Python runtime value.

        Args:
            value: A Python value (``int``, ``float``, ``str``, ``list``, …).

        Returns:
            A C type string such as ``"int"``, ``"float"``, ``"char*"``,
            or ``"int*"`` for lists.
        """
        """Infer a type string from a Python value."""
        if isinstance(value, float):  return "float"
        if isinstance(value, list):   return "int*"
        if isinstance(value, str):    return "char*"
        return "int"

    # ── Segment execution ─────────────────────────────────────────────────────

    def _exec_seg(self, seg: dict, frame: dict, iteration) -> None:
        """Execute all statements in a segment, dispatching by kind.

        Args:
            seg: The segment dict to execute.
            frame: The active variable frame for the current call.
            iteration: The current loop-iteration counter (``None`` outside loops).
        """
        child_iter = iter(self._children.get(seg["id"], []))
        for stmt in seg.get("stmts", []):
            self._exec_stmt(stmt, frame, seg["scope_path"], seg, child_iter, iteration)

    def _exec_stmt(self, stmt, frame, scope, seg, child_iter, iteration) -> None:
        """Dispatch a single classified statement to its handler.

        Args:
            stmt: A classified statement dict.
            frame: The active variable frame.
            scope: The scope path string of the enclosing segment.
            seg: The enclosing segment dict.
            child_iter: Iterator over child segment IDs (consumed by branch/loop).
            iteration: Current loop-iteration counter.
        """
        kind = stmt["kind"]
        if kind in ("decl", "assign"):
            self._exec_decl_assign(stmt, frame, scope, seg, iteration)
        elif kind == "control":
            self._exec_control(stmt, frame, scope, seg, iteration)
        elif kind == "call":
            self._exec_call_stmt(stmt, frame, scope, seg, iteration)
        elif kind == "loop_head":
            child_seg = self._seg_by_id[next(child_iter)]
            self._exec_loop(stmt, child_seg, frame, scope, seg)
        elif kind == "branch":
            self._exec_branch_stmt(stmt, frame, scope, seg, child_iter, iteration)
        elif kind == "expr":
            self._exec_expr_stmt(stmt, frame, scope, seg, iteration)

    # ── Trace helper ─────────────────────────────────────────────────────────

    def _record(self, stmt, seg, iteration, read_snap, write_snap,
                branch_taken=None, deref_reads=None, deref_writes=None) -> None:
        """Append a trace event for the current statement execution.

        Args:
            stmt: The classified statement dict being executed.
            seg: The enclosing segment dict.
            iteration: Current loop-iteration counter.
            read_snap: Dict of slot names → values captured before execution.
            write_snap: Dict of slot names → values captured after execution.
            branch_taken: ``True``/``False`` for branch/loop-head stmts,
                ``None`` for others.
            deref_reads: Dict of ``{addr: value}`` for pointer reads, or ``None``.
            deref_writes: Dict of ``{addr: value}`` for pointer writes, or ``None``.
        """
        row = {
            "kind":         stmt["kind"],
            "raw":          stmt["raw"],
            "seg_id":       seg["id"],
            "scope_path":   seg["scope_path"],
            "fn":           self._seg_fn.get(seg["id"], "unknown"),
            "iteration":    iteration,
            "read_values":  read_snap,
            "write_values": write_snap,
            "branch_taken": branch_taken,
        }
        if deref_reads:  row["deref_reads"]  = deref_reads
        if deref_writes: row["deref_writes"] = deref_writes
        self.trace.append(row)

    # ── Decl / Assign ─────────────────────────────────────────────────────────

    def _exec_decl_assign(self, stmt, frame, scope, seg, iteration) -> None:
        """Execute a ``decl`` or ``assign`` statement, updating the frame.

        Handles struct initialisation, array allocation, pointer assignments,
        compound assignments, and plain scalar writes.

        Args:
            stmt: A classified statement dict with ``kind`` of ``"decl"``
                or ``"assign"``.
            frame: The active variable frame.
            scope: The scope path string of the enclosing segment.
            seg: The enclosing segment dict.
            iteration: Current loop-iteration counter.
        """
        raw    = stmt["raw"]
        l_name = stmt.get("l_name")
        expr   = stmt.get("expr")
        if l_name is None:
            return

        r_names   = [n for n in stmt.get("r_names", []) if n in frame]
        read_snap = _snap_reads(r_names, frame)
        type_str  = stmt.get("type", "int") or "int"

        # --- Struct brace init: Point p1 = {3, 4} ---
        decl_type = stmt.get("type", "")
        if decl_type in self._struct_fields and "{" in raw:
            rhs = _extract_rhs(raw)
            if rhs and rhs.startswith("{"):
                vals   = _parse_brace(rhs)
                fields = self._struct_fields[decl_type]
                ftypes = self._struct_field_types.get(decl_type, {})
                written = []
                for i, field in enumerate(fields):
                    key      = f"{l_name}.{field}"
                    ftype    = ftypes.get(field, "int")
                    fval     = vals[i] if i < len(vals) else 0
                    self._alloc_stack_slot(frame, key, fval, ftype)
                    written.append(key)
                self._record(stmt, seg, iteration, read_snap,
                             _snap_writes(written, frame))
                return

        # --- Array brace init: int u[3] = {1, 2, 3} ---
        if "[" in raw and "=" in raw and "{" in raw:
            base = l_name.split("[")[0]
            rhs  = _extract_rhs(raw)
            if rhs and rhs.startswith("{"):
                vals = _parse_brace(rhs)
                # 1D flat arrays: promote immediately to heap so the slot holds
                # a heap address. This matches C/Java array semantics where the
                # array name IS a pointer. Writes inside callees persist in the
                # heap and are visible to the caller after the call returns.
                # 2D arrays (list-of-lists): keep as Python list so the index
                # op can handle them via __getitem__ on the outer dimension.
                is_2d = isinstance(vals, list) and vals and isinstance(vals[0], list)
                if not is_2d:
                    heap_addr = self._list_to_heap(vals, _pointee_type(type_str))
                    self._alloc_stack_slot(frame, base, heap_addr, type_str + "*")
                else:
                    self._alloc_stack_slot(frame, base, vals, type_str)
                self._record(stmt, seg, iteration, read_snap,
                             _snap_writes([base], frame))
            return

        # --- Increment / decrement ---
        if expr and expr.get("op") in ("post_inc","post_dec","pre_inc","pre_dec"):
            # Could be *p++ — check if l_name is a deref target
            if l_name.startswith("*"):
                inner_name = l_name[1:].strip()
                if inner_name in frame:
                    addr = _fget(frame, inner_name)
                    cur  = self._heap_read(addr)
                    new_val = cur + (1 if expr["op"] in ("post_inc","pre_inc") else -1)
                    self._heap_write(addr, new_val)
                    dw = {addr: new_val}
                    self._record(stmt, seg, iteration,
                                 {inner_name: addr}, {}, deref_writes=dw)
                    return
            if l_name in frame:
                cur = _fget(frame, l_name)
            else:
                cur = 0
            new_val = cur + (1 if expr["op"] in ("post_inc","pre_inc") else -1)
            read_snap_inc = {l_name: cur}
            if l_name in frame:
                self._write_slot(frame, l_name, new_val)
            else:
                self._alloc_stack_slot(frame, l_name, new_val, "int")
            self._record(stmt, seg, iteration,
                         read_snap_inc, {l_name: new_val})
            return

        # --- Deref write: *p = expr ---
        if expr is not None and l_name.startswith("*"):
            inner_name = l_name[1:].strip()
            val = self._eval(expr, frame, scope)
            dr, dw = {}, {}
            if inner_name in frame:
                addr = _fget(frame, inner_name)
                self._heap_write(addr, val)
                dw = {addr: val}
            self._record(stmt, seg, iteration, read_snap, {}, deref_writes=dw)
            return

        # --- Double deref write: **pp = expr ---
        if expr is not None and l_name.startswith("**"):
            inner_name = l_name[2:].strip()
            val = self._eval(expr, frame, scope)
            dw = {}
            if inner_name in frame:
                pp_addr = _fget(frame, inner_name)
                p_addr  = self._heap_read(pp_addr)
                self._heap_write(p_addr, val)
                dw = {p_addr: val}
            self._record(stmt, seg, iteration, read_snap, {}, deref_writes=dw)
            return

        # --- Normal expr ---
        if expr is not None:
            val, dr, dw = self._eval_traced(expr, frame, scope)
            # Promote list to heap address when assigning to a pointer slot.
            # Use both the parsed type_str AND the raw declaration (parser
            # doesn't always emit "int*" — it may emit "int" for "int *p").
            is_ptr_decl = (
                _is_pointer_type(type_str)
                or ("*" in raw.split("=")[0] if "=" in raw else "*" in raw)
            )
            if isinstance(val, list) and is_ptr_decl:
                val = self._list_to_heap(val, _pointee_type(type_str))
            # Intern string literals to heap so char* arithmetic works
            if isinstance(val, str) and is_ptr_decl:
                val = self._intern_string(val)
            if l_name in frame:
                self._write_slot(frame, l_name, val)
            else:
                self._alloc_stack_slot(frame, l_name, val, type_str)
            self._record(stmt, seg, iteration, read_snap,
                         _snap_writes([l_name], frame),
                         deref_reads=dr or None, deref_writes=dw or None)
            return

        # --- Decl with no initializer ---
        if stmt["kind"] == "decl" and "=" not in raw:
            init = NULL if _is_pointer_type(type_str) else 0
            self._alloc_stack_slot(frame, l_name, init, type_str)
            self._record(stmt, seg, iteration, {}, {l_name: frame[l_name]["value"]})

    # ── Control ───────────────────────────────────────────────────────────────

    def _exec_control(self, stmt, frame, scope, seg, iteration):
        """Execute a ``control`` statement (``return``, ``break``, ``continue``).

        Args:
            stmt: A classified statement dict with ``kind == "control"``.
            frame: The active variable frame.
            scope: The scope path string of the enclosing segment.
            seg: The enclosing segment dict.
            iteration: Current loop-iteration counter.

        Raises:
            _Return: Always raised for ``return`` statements.
            _Break: Raised for ``break`` statements.
            _Continue: Raised for ``continue`` statements.
        """
        raw       = stmt["raw"].strip()
        expr      = stmt.get("expr")
        r_names   = [n for n in stmt.get("r_names", []) if n in frame]
        read_snap = _snap_reads(r_names, frame)
        self._record(stmt, seg, iteration, read_snap, {})
        if raw.startswith("return"):
            val = self._eval(expr, frame, scope) if expr is not None else None
            raise _Return(val)
        if raw.startswith("break"):
            raise _Break()
        if raw.startswith("continue"):
            raise _Continue()

    def _exec_call_stmt(self, stmt, frame, scope, seg, iteration) -> None:
        """Execute a standalone function-call statement (result discarded).

        Args:
            stmt: A classified statement dict with ``kind == "call"``.
            frame: The active variable frame.
            scope: The scope path string of the enclosing segment.
            seg: The enclosing segment dict.
            iteration: Current loop-iteration counter.
        """
        r_names   = [n for n in stmt.get("r_names", []) if n in frame]
        read_snap = _snap_reads(r_names, frame)
        expr = stmt.get("expr")
        dr, dw = {}, {}
        if expr and expr.get("op") == "call":
            self._eval_call(expr, frame, scope)
        self._record(stmt, seg, iteration, read_snap, {},
                     deref_reads=dr or None, deref_writes=dw or None)

    def _exec_expr_stmt(self, stmt, frame, scope, seg, iteration):
        """
        Handle statements the parser emits as kind='expr' — currently
        these are deref-write patterns like '*p = val' and '*(p+i) = val'
        that the matrix builder didn't attach a full expr tree to.
        We parse the raw string directly here.
        """
        raw = stmt["raw"].strip().rstrip(";").strip()

        # Pattern: **name = rhs  (double deref write)
        m2 = re.match(r'^\*\*([A-Za-z_]\w*)\s*=\s*(.+)$', raw)
        if m2:
            pp_name = m2.group(1).strip()
            rhs_src = m2.group(2).strip()
            try:
                from expr import parse_expr
                rhs_node = parse_expr(rhs_src)
                val = self._eval(rhs_node, frame, scope)
                r_names   = [n for n in stmt.get("r_names", []) if n in frame]
                read_snap = _snap_reads(r_names, frame)
                if pp_name in frame:
                    pp_addr = _fget(frame, pp_name)
                    p_addr  = self._heap_read(pp_addr)
                    self._heap_write(p_addr, val)
                    dw = {p_addr: val}
                    self._record(stmt, seg, iteration, read_snap, {},
                                 deref_writes=dw)
            except Exception:
                pass
            return

        # Pattern: *name = rhs  or  *(expr) = rhs
        m = re.match(r'^\*\((.+)\)\s*=\s*(.+)$', raw)
        if not m:
            m = re.match(r'^\*([A-Za-z_]\w*(?:\s*\+\s*\w+)?)\s*=\s*(.+)$', raw)
        if m:
            ptr_src = m.group(1).strip()
            rhs_src = m.group(2).strip()
            try:
                from expr import parse_expr, build_assign_expr
                ptr_node = parse_expr(ptr_src)
                rhs_node = parse_expr(rhs_src)
                addr = self._eval(ptr_node, frame, scope)
                val  = self._eval(rhs_node, frame, scope)
                r_names   = [n for n in stmt.get("r_names", []) if n in frame]
                read_snap = _snap_reads(r_names, frame)
                self._heap_write(addr, val)
                self._record(stmt, seg, iteration, read_snap, {},
                             deref_writes={addr: val})
            except Exception:
                pass
            return

        # Pattern: name[idx] = rhs  (array write via index)
        m = re.match(r'^([A-Za-z_]\w*)\[(.+)\]\s*=\s*(.+)$', raw)
        if m:
            arr_name = m.group(1).strip()
            idx_src  = m.group(2).strip()
            rhs_src  = m.group(3).strip()
            try:
                from expr import parse_expr
                idx_node = parse_expr(idx_src)
                rhs_node = parse_expr(rhs_src)
                idx = int(self._eval(idx_node, frame, scope))
                val = self._eval(rhs_node, frame, scope)
                r_names   = [n for n in stmt.get("r_names", []) if n in frame]
                read_snap = _snap_reads(r_names, frame)
                if arr_name in frame:
                    arr_val = _fget(frame, arr_name)
                    if isinstance(arr_val, list):
                        arr_val[idx] = val
                        self._record(stmt, seg, iteration, read_snap,
                                     {arr_name: list(arr_val)})
                    elif isinstance(arr_val, int):  # heap pointer
                        addr = arr_val + idx
                        self._heap_write(addr, val)
                        self._record(stmt, seg, iteration, read_snap, {},
                                     deref_writes={addr: val})
            except Exception:
                pass
            return

        # Unknown expr stmt — record it but take no action
        r_names   = [n for n in stmt.get("r_names", []) if n in frame]
        read_snap = _snap_reads(r_names, frame)
        self._record(stmt, seg, iteration, read_snap, {})

    # ── Branch ────────────────────────────────────────────────────────────────

    def _exec_branch_stmt(self, stmt, frame, scope, seg, child_iter, iteration) -> None:
        """Execute a ``branch`` statement (``if``/``else if``/``else``).

        Evaluates the condition, advances ``child_iter`` to the matching body
        segment, and executes the taken branch.

        Args:
            stmt: A classified statement dict with ``kind == "branch"``.
            frame: The active variable frame.
            scope: The scope path string of the enclosing segment.
            seg: The enclosing segment dict.
            child_iter: Iterator over child segment IDs.
            iteration: Current loop-iteration counter.
        """
        expr = stmt.get("expr")
        try:
            child_seg = self._seg_by_id[next(child_iter)]
        except StopIteration:
            return
        cond      = bool(self._eval(expr, frame, scope)) if expr is not None else True
        r_names   = [n for n in stmt.get("r_names", []) if n in frame]
        read_snap = _snap_reads(r_names, frame)
        self._record(stmt, seg, iteration, read_snap, {}, branch_taken=cond)
        if cond:
            self._exec_seg(child_seg, frame, iteration)

    # ── Loop ──────────────────────────────────────────────────────────────────

    def _exec_loop(self, loop_stmt, body_seg, frame, scope, parent_seg) -> None:
        """Execute a loop (``while``, ``do-while``, or ``for``).

        Args:
            loop_stmt: The ``loop_head`` statement dict that introduces the loop.
            body_seg: The child segment dict containing the loop body.
            frame: The active variable frame.
            scope: The scope path string of the enclosing segment.
            parent_seg: The segment dict that owns the loop statement.
        """
        raw    = loop_stmt["raw"].strip()
        expr   = loop_stmt.get("expr")
        l_name = loop_stmt.get("l_name")

        for_update_src = None
        if raw.startswith("for"):
            if l_name:
                init_val = self._parse_for_init(raw)
                type_str = loop_stmt.get("type", "int") or "int"
                if l_name in frame:
                    self._write_slot(frame, l_name, init_val)
                else:
                    self._alloc_stack_slot(frame, l_name, init_val, type_str)
            for_update_src = _extract_for_update(raw)

        is_do_while = raw.startswith("do")
        iters       = 0

        while True:
            if iters >= self.max_unroll:
                self.unroll_capped = True
                break

            if is_do_while:
                try:
                    self._exec_seg(body_seg, frame, iteration=iters)
                except _Break:
                    break
                except _Continue:
                    pass
                iters += 1
                r_names   = [n for n in loop_stmt.get("r_names", []) if n in frame]
                read_snap = _snap_reads(r_names, frame)
                cond      = bool(self._eval(expr, frame, scope)) if expr else False
                self._record(loop_stmt, parent_seg, iters - 1,
                             read_snap, {}, branch_taken=cond)
                if not cond:
                    break
                continue

            r_names   = [n for n in loop_stmt.get("r_names", []) if n in frame]
            read_snap = _snap_reads(r_names, frame)
            cond      = bool(self._eval(expr, frame, scope)) if expr else False
            self._record(loop_stmt, parent_seg, iters,
                         read_snap, {}, branch_taken=cond)
            if not cond:
                break

            try:
                self._exec_seg(body_seg, frame, iteration=iters)
            except _Break:
                break
            except _Continue:
                pass

            if for_update_src:
                self._exec_update(for_update_src, frame, scope)
            iters += 1

    def _parse_for_init(self, raw: str) -> int:
        """Parse and execute the initialisation clause of a ``for`` loop.

        Args:
            raw: The full ``for`` loop header string.

        Returns:
            The initial integer value of the loop iterator (or ``0`` on
            parse failure).
        """
        try:
            start = raw.index("(") + 1
            init_clause = raw[start:].split(";")[0].strip()
            if "=" in init_clause:
                return int(init_clause[init_clause.index("=") + 1:].strip())
        except (ValueError, IndexError):
            pass
        return 0

    def _exec_update(self, update_src: str, frame: dict, scope: str) -> None:
        """Execute a ``for`` loop update expression (e.g. ``i++``, ``i += 2``).

        Args:
            update_src: The update clause string extracted from the loop header.
            frame: The active variable frame.
            scope: The scope path string of the enclosing segment.
        """
        s = update_src.strip()
        m = re.fullmatch(r'([A-Za-z_]\w*)\s*(\+\+|--)', s)
        if m:
            name, op = m.group(1), m.group(2)
            cur = _fget(frame, name) if name in frame else 0
            new_val = cur + (1 if op == "++" else -1)
            if name in frame:
                self._write_slot(frame, name, new_val)
            else:
                self._alloc_stack_slot(frame, name, new_val, "int")
            return
        m = re.fullmatch(r'(\+\+|--)\s*([A-Za-z_]\w*)', s)
        if m:
            op, name = m.group(1), m.group(2)
            cur = _fget(frame, name) if name in frame else 0
            new_val = cur + (1 if op == "++" else -1)
            if name in frame:
                self._write_slot(frame, name, new_val)
            else:
                self._alloc_stack_slot(frame, name, new_val, "int")
            return
        # pointer increment: p++ where p is a pointer
        for cop in ("+=", "-=", "*=", "/=", "%="):
            idx = s.find(cop)
            if idx > 0:
                lhs  = s[:idx].strip()
                tree = build_assign_expr(lhs, cop, s[idx + len(cop):].strip())
                if tree:
                    val = self._eval(tree, frame, scope)
                    if lhs in frame:
                        self._write_slot(frame, lhs, val)
                    else:
                        self._alloc_stack_slot(frame, lhs, val, "int")
                return

    # ── Expression evaluation ─────────────────────────────────────────────────

    def _eval_traced(self, node: dict, frame: dict, scope: str):
        """
        Like _eval but also returns (value, deref_reads, deref_writes).
        deref_reads/deref_writes are dicts of {addr: value}.
        """
        dr, dw = {}, {}
        val = self._eval(node, frame, scope, _dr=dr, _dw=dw)
        return val, dr, dw

    def _eval(self, node: dict, frame: dict, scope: str,
              _dr: dict = None, _dw: dict = None):
        """Evaluate an expression node, returning its value."""
        if node is None:
            return None

        if "name" in node:
            name = node["name"]
            # NULL literal
            if name == "NULL":
                return NULL
            if name in frame:
                return _fget(frame, name)
            u = _strip_scope(name, scope)
            if u in frame:
                return _fget(frame, u)
            raise NameError(f"'{name}' not in frame")

        if "slot" in node:
            slot = node["slot"]
            u = _strip_scope(slot, scope)
            if u in frame:
                return _fget(frame, u)
            parts = slot.split(".")
            for d in range(len(parts) - 1, 0, -1):
                c = ".".join(parts[d:])
                if c in frame:
                    return _fget(frame, c)
            raise KeyError(f"Slot '{slot}' not in frame")

        if "const" in node:
            return self.kernel.eval(node, {})

        op = node.get("op")
        if op is None:
            raise ValueError(f"Malformed node: {node}")

        if op == "call":
            return self._eval_call(node, frame, scope)

        # ── addr_of: &x ───────────────────────────────────────────────────
        if op == "addr_of":
            arg = node["args"][0]
            name = arg.get("name") or arg.get("slot", "")
            name = _strip_scope(name, scope)
            if name in frame:
                return _faddr(frame, name)
            raise NameError(f"Cannot take address of '{name}': not in frame")

        # ── deref: *p ─────────────────────────────────────────────────────
        if op == "deref":
            addr = self._eval(node["args"][0], frame, scope, _dr=_dr, _dw=_dw)
            val  = self._heap_read(addr)
            if _dr is not None:
                _dr[addr] = val
            return val

        # ── index: arr[i] ─────────────────────────────────────────────────
        if op == "index":
            arr_node = node["args"][0]
            idx      = int(self._eval(node["args"][1], frame, scope, _dr=_dr, _dw=_dw))
            arr_val  = self._eval(arr_node, frame, scope, _dr=_dr, _dw=_dw)

            # If arr_val is a Python list (stack array), use direct indexing
            if isinstance(arr_val, list):
                return arr_val[idx]

            # If arr_val is an integer (pointer/address), use heap
            if isinstance(arr_val, int):
                addr = arr_val + idx  # pointer arithmetic: 1 unit per element
                val  = self._heap_read(addr)
                if _dr is not None:
                    _dr[addr] = val
                return val

            raise TypeError(f"Cannot index {arr_val!r}")

        # ── field: s.x ────────────────────────────────────────────────────
        if op == "field":
            obj  = node["args"][0]
            name = obj.get("name") or obj.get("slot", "")
            key  = f"{_strip_scope(name, scope)}.{node['field']}"
            if key in frame:
                return _fget(frame, key)
            raise KeyError(f"Field '{key}' not in frame")

        # ── increment / decrement (as expression) ─────────────────────────
        if op in ("post_inc", "post_dec", "pre_inc", "pre_dec"):
            # If the operand is a named slot, apply the inc/dec to it
            arg = node["args"][0]
            name = arg.get("name") or arg.get("slot", "")
            name = _strip_scope(name, scope) if name else ""
            if name and name in frame:
                cur = _fget(frame, name)
                delta = 1 if op in ("post_inc", "pre_inc") else -1
                # Pointer increment: step by 1 address unit
                new_val = cur + delta
                self._write_slot(frame, name, new_val)
                return cur if op in ("post_inc", "post_dec") else new_val
            return self._eval(arg, frame, scope, _dr=_dr, _dw=_dw)

        # ── pointer arithmetic: ptr + n, ptr - n ──────────────────────────
        if op in ("+", "-", "add", "sub") and len(node.get("args", [])) == 2:
            left  = self._eval(node["args"][0], frame, scope, _dr=_dr, _dw=_dw)
            right = self._eval(node["args"][1], frame, scope, _dr=_dr, _dw=_dw)
            # list + int: promote list to heap address first
            if isinstance(left, list) and isinstance(right, int):
                left = self._list_to_heap(left)
            if isinstance(right, list) and isinstance(left, int):
                right = self._list_to_heap(right)
            # If one side looks like an address, treat as pointer arithmetic
            if (isinstance(left, int) and isinstance(right, int)
                    and (left >= 0x1000 or right >= 0x1000)):
                delta = right if left >= 0x1000 else left
                base  = left  if left >= 0x1000 else right
                return base + delta if op in ("+", "add") else base - delta
            # Fall through to kernel for normal arithmetic

        # ── sizeof ────────────────────────────────────────────────────────
        if op == "sizeof":
            return _sizeof(node.get("of", "int"))

        # ── cast: discard type annotation, just evaluate inner expr ───────
        if op == "cast":
            inner = node.get("args", [None])[0]
            return self._eval(inner, frame, scope, _dr=_dr, _dw=_dw) if inner else 0

        # ── pointer comparison ────────────────────────────────────────────
        # Handled naturally by kernel since both sides are integers

        evaled = [self._eval(a, frame, scope, _dr=_dr, _dw=_dw)
                  for a in node.get("args", [])]
        knode  = {"op": op, "args": [
            {"const": v, "type": "int"}   if isinstance(v, int)
            else {"const": v, "type": "float"} if isinstance(v, float)
            else {"const": v, "type": "str"}
            for v in evaled
        ]}
        for k in ("field", "type", "fn", "of"):
            if k in node: knode[k] = node[k]
        return self.kernel.eval(knode, {})

    # ── Call evaluation ───────────────────────────────────────────────────────

    def _eval_call(self, node: dict, frame: dict, scope: str):
        """Evaluate a function-call expression node.

        Handles ``malloc``, ``free``, ``printf``, ``strlen``, ``strcmp``,
        calls to user-defined functions present in the IR, and delegates
        unknown calls to :meth:`VMKernel.op_call`.

        Args:
            node: A ``{"op": "call", "fn": ..., "args": [...]}`` expr node.
            frame: The active variable frame of the caller.
            scope: The scope path string of the call site.

        Returns:
            The return value of the called function, or ``0`` for ``void``
            functions and unknown calls that are suppressed.
        """
        fn   = node.get("fn", "")
        args = node.get("args", [])

        # ── printf ────────────────────────────────────────────────────────
        if fn == "printf":
            self._mock_printf([self._eval(a, frame, scope) for a in args])
            return 0

        # ── malloc ────────────────────────────────────────────────────────
        if fn == "malloc":
            n_bytes = int(self._eval(args[0], frame, scope)) if args else 0
            return self._alloc_heap(n_bytes)

        # ── calloc ────────────────────────────────────────────────────────
        if fn == "calloc":
            n     = int(self._eval(args[0], frame, scope)) if len(args) > 0 else 0
            size  = int(self._eval(args[1], frame, scope)) if len(args) > 1 else 1
            return self._alloc_heap(n * size)

        # ── realloc ───────────────────────────────────────────────────────
        if fn == "realloc":
            # Simplified: allocate new, old data lost (sufficient for tracing)
            n_bytes = int(self._eval(args[1], frame, scope)) if len(args) > 1 else 0
            return self._alloc_heap(n_bytes)

        # ── free ──────────────────────────────────────────────────────────
        if fn == "free":
            # No-op: Python GC handles memory; we just skip
            return 0

        # ── sizeof ────────────────────────────────────────────────────────
        if fn == "sizeof":
            # sizeof is typically in the expr as {"op":"sizeof","of":"int"}
            # but handle it here too
            type_arg = node.get("of", "int")
            return _sizeof(type_arg)

        # ── string builtins ───────────────────────────────────────────────
        if fn == "strlen":
            addr = int(self._eval(args[0], frame, scope)) if args else NULL
            # Walk heap until null terminator
            if isinstance(addr, str):
                return len(addr)
            length = 0
            while True:
                v = self._heap_read(addr + length)
                if v == 0:
                    break
                length += 1
                if length > 100_000:
                    break
            return length

        if fn == "strcpy":
            dst = int(self._eval(args[0], frame, scope))
            src = int(self._eval(args[1], frame, scope))
            i   = 0
            while True:
                v = self._heap_read(src + i)
                self._heap_write(dst + i, v)
                if v == 0:
                    break
                i += 1
            return dst

        if fn == "strcmp":
            a_addr = int(self._eval(args[0], frame, scope))
            b_addr = int(self._eval(args[1], frame, scope))
            i = 0
            while True:
                a_c = self._heap_read(a_addr + i)
                b_c = self._heap_read(b_addr + i)
                if a_c != b_c:
                    return a_c - b_c
                if a_c == 0:
                    return 0
                i += 1

        if fn == "memset":
            dst   = int(self._eval(args[0], frame, scope))
            val   = int(self._eval(args[1], frame, scope))
            n     = int(self._eval(args[2], frame, scope))
            for i in range(n):
                self._heap_write(dst + i, val)
            return dst

        if fn == "memcpy":
            dst = int(self._eval(args[0], frame, scope))
            src = int(self._eval(args[1], frame, scope))
            n   = int(self._eval(args[2], frame, scope))
            for i in range(n):
                self._heap_write(dst + i, self._heap_read(src + i))
            return dst

        # ── user-defined functions ─────────────────────────────────────────
        if fn in self._fn_by_name:
            target  = self._fn_by_name[fn]
            memory  = target.get("memory", [])
            params  = [m for m in memory if m.get("param")]

            seen, lparams = {}, []
            for p in params:
                parent = p.get("udt_parent")
                if parent:
                    if parent not in seen:
                        seen[parent] = True
                        fields = [m["name"] for m in params
                                  if m.get("udt_parent") == parent]
                        lparams.append(("udt", parent, fields))
                else:
                    lparams.append(("plain", p["name"],
                                    p.get("type", "int")))

            arg_frame = {}
            for i, lp in enumerate(lparams):
                if i >= len(args): break
                if lp[0] == "plain":
                    param_name = lp[1]
                    param_type = lp[2]
                    try:
                        val = self._eval(args[i], frame, scope)
                    except Exception:
                        val = NULL if _is_pointer_type(param_type) else 0
                    # Promote flat 1D lists to heap so pointer arithmetic
                    # works inside the callee.  2D lists (list-of-lists) are kept
                    # as Python lists — the index op handles them via __getitem__.
                    if isinstance(val, list) and val and not isinstance(val[0], list):
                        val = self._list_to_heap(val, _pointee_type(param_type))
                    # If a Python string is passed to any param, intern it to heap
                    if isinstance(val, str):
                        val = self._intern_string(val)
                    self._alloc_stack_slot(arg_frame, param_name, val, param_type)
                    # Register pointer in addr_map so derefs inside callee work
                    if _is_pointer_type(param_type) and isinstance(val, int):
                        pass  # addr already registered when &x was taken
                else:
                    caller_var = _strip_scope(
                        args[i].get("name") or args[i].get("slot", ""), scope)
                    for fs in lp[2]:
                        fn_part = fs.split(".", 1)[1]
                        src_key = f"{caller_var}.{fn_part}"
                        src_val = _fget(frame, src_key) if src_key in frame else 0
                        src_type = _fget_type(frame, src_key) if src_key in frame else "int"
                        self._alloc_stack_slot(arg_frame, fs, src_val, src_type)

            try:
                self._exec_seg(target, arg_frame, iteration=None)
            except _Return as r:
                return r.value
            return None

        # ── kernel fallback ───────────────────────────────────────────────
        try:
            evaled = [self._eval(a, frame, scope) for a in args]
            return self.kernel.op_call(*evaled, fn=fn)
        except NotImplementedError:
            raise NotImplementedError(f"Call to '{fn}' cannot be resolved.")

    # ── printf mock ───────────────────────────────────────────────────────────

    def _mock_printf(self, args: list) -> None:
        """Emulate C ``printf`` by formatting a string and appending to output.

        Supports ``%d``, ``%i``, ``%f``, ``%g``, ``%e``, ``%s``, ``%c``,
        ``%u``, ``%ld``, ``%li``, ``%lu``, ``%lf``, and ``%%``.

        Args:
            args: List of evaluated argument values where ``args[0]`` is the
                format string.
        """
        if not args: return
        fmt_arg = args[0]
        # fmt_arg could be a string, or an address (char* in heap)
        if isinstance(fmt_arg, int) and fmt_arg >= 0x1000:
            # Read string from heap
            chars = []
            i = 0
            while True:
                v = self._heap_read(fmt_arg + i)
                if v == 0: break
                chars.append(chr(v))
                i += 1
                if i > 10_000: break
            fmt = "".join(chars)
        else:
            fmt = str(fmt_arg).strip('"') if isinstance(fmt_arg, str) else str(fmt_arg)

        vals = args[1:]
        fmt  = fmt.replace("\\n", "\n").replace("\\t", "\t")
        result, vi, i = "", 0, 0
        while i < len(fmt):
            if fmt[i] == "%" and i + 1 < len(fmt):
                spec = fmt[i + 1]
                v    = vals[vi] if vi < len(vals) else 0
                if spec in ("d","i"):   result += str(int(v))
                elif spec == "f":       result += f"{float(v):.6f}"
                elif spec == "s":
                    # v might be a heap address (char*)
                    if isinstance(v, int) and v >= 0x1000:
                        chars = []
                        j = 0
                        while True:
                            cv = self._heap_read(v + j)
                            if cv == 0: break
                            chars.append(chr(cv))
                            j += 1
                        result += "".join(chars)
                    else:
                        result += str(v)
                elif spec == "c":       result += chr(int(v))
                elif spec == "%":       result += "%"; vi -= 1
                else:                   result += f"%{spec}"
                vi += 1; i += 2
            else:
                result += fmt[i]; i += 1
        for line in result.split("\n"):
            if line:
                self.output.append(line)


# ---------------------------------------------------------------------------
# Entry point helper
# ---------------------------------------------------------------------------

def run_file(parsed_json_str: str, max_unroll: int = 10_000) -> dict:
    """Execute a parsed IR JSON string and return output and trace.

    Convenience wrapper around :class:`VM` for one-shot execution of
    ``main()``.

    Args:
        parsed_json_str: A JSON string produced by ``parse_c_file`` or
            ``parse_java_file``.
        max_unroll: Maximum loop iterations before capping.  Defaults to
            ``10_000``.

    Returns:
        A dict with keys ``"output"`` (list of printed lines),
        ``"trace"`` (list of trace event dicts), and
        ``"unroll_capped"`` (bool).
    """
    """Run main() and return results dict with output, trace, return_value."""
    vm = VM(parsed_json_str, max_unroll=max_unroll)
    try:
        ret = vm.call_fn("main", {})
    except Exception:
        ret = None
    return {
        "output":        vm.output,
        "return_value":  ret,
        "trace":         vm.trace,
        "unroll_capped": vm.unroll_capped,
    }