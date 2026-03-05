"""Dependency matrix construction for the CDUP pipeline.

Takes the parsed segments list and builds a slot × statement matrix where
each row is one statement event (including synthetic phi nodes) and each
column is one memory slot (scoped variable or constant).  Cell values are
expressed as ``reads``, ``writes``, and ``decls`` lists per row.

Phi nodes are injected at:

- Branch reconvergence points (after ``if``/``else`` groups close).
- Loop entry points (slot value is either the initial value or the value
  from the previous iteration).

Entry point:
    ``build_matrix(segments: list) -> dict``
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seg_by_id(segments: list) -> dict:
    """Index a list of segment dicts by their ``id`` field.

    Args:
        segments: List of segment dicts from the parsed IR.

    Returns:
        Dict mapping segment ID (int) to segment dict.
    """
    return {seg["id"]: seg for seg in segments}


def _build_children(segments):
    """Return dict: parent_id -> [child_id, ...]  in id order."""
    children = {}
    for seg in segments:
        sid, pid = seg["id"], seg["parent"]
        if sid == pid:
            continue
        children.setdefault(pid, []).append(sid)
    for pid in children:
        children[pid].sort()
    return children


def _all_scoped_slots(segments):
    """
    Return an ordered list of all unique scoped slot names across all segments.
    Variables before constants, segments in id order.
    """
    seen = {}
    for seg in sorted(segments, key=lambda s: s["id"]):
        for slot in seg.get("memory", []):
            name = slot["scoped_name"]
            if name not in seen:
                seen[name] = slot
        for slot in seg.get("constants", []):
            name = slot["scoped_name"]
            if name not in seen:
                seen[name] = slot
    return list(seen.keys())


def _resolve_slot(name, scope_path, slot_index):
    """
    Resolve a variable name to its scoped slot name.
    Tries innermost scope first, walks up to root.

    Handles three name forms:
      plain      "x"      -> "root.fn.x"
      dotted     "a.x"    -> "root.fn.a.x"   (field-expanded UDT slot)
      indexed    "u[0]"   -> "root.fn.u.0"   (static array index only)
                 "u[i]"   -> "root.fn.u"     (dynamic index: conservative)
    """
    import re
    # Static array index: u[0] -> slot u.0
    arr_match = re.fullmatch(r'([A-Za-z_]\w*)\[(\d+)\]', name)
    if arr_match:
        base, idx = arr_match.group(1), arr_match.group(2)
        parts = scope_path.split(".")
        for depth in range(len(parts), 0, -1):
            candidate = ".".join(parts[:depth]) + f".{base}.{idx}"
            if candidate in slot_index:
                return candidate
        # Fall back to the base array slot (dynamic-index conservative)
        for depth in range(len(parts), 0, -1):
            candidate = ".".join(parts[:depth]) + f".{base}"
            if candidate in slot_index:
                return candidate
        return None
    # Dynamic array index: u[i] -> slot u  (conservative)
    dyn_match = re.fullmatch(r'([A-Za-z_]\w*)\[[A-Za-z_]\w*\]', name)
    if dyn_match:
        name = dyn_match.group(1)
    # Plain or dotted name (including field-expanded "a.x")
    parts = scope_path.split(".")
    for depth in range(len(parts), 0, -1):
        candidate = ".".join(parts[:depth]) + "." + name
        if candidate in slot_index:
            return candidate
    return None


def _extract_literal_slots(stmt, scope_path, slot_index):
    """Return list of scoped constant slot names for literals in stmt."""
    try:
        from .parse import _extract_literals, _canonical_constant_name
    except ImportError:
        from parse import _extract_literals, _canonical_constant_name
    lits = _extract_literals(stmt["raw"])
    slots = []
    string_idx = 0
    for v in lits["ints"]:
        c = _resolve_slot(_canonical_constant_name("int", v), scope_path, slot_index)
        if c: slots.append(c)
    for v in lits["floats"]:
        c = _resolve_slot(_canonical_constant_name("float", v), scope_path, slot_index)
        if c: slots.append(c)
    for v in lits["chars"]:
        c = _resolve_slot(_canonical_constant_name("char", v), scope_path, slot_index)
        if c: slots.append(c)
    for v in lits["strings"]:
        cname = _canonical_constant_name("string", v, string_idx)
        c = _resolve_slot(cname, scope_path, slot_index)
        if c: slots.append(c)
        string_idx += 1
    return slots


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def _resolve_expr(node, scope_path, slot_index):
    """
    Walk an unresolved expr tree (from parse.py) and resolve bare {"name":"x"}
    leaves to {"slot": "root.fn.x"} using the slot index.

    Special case: {"op":"field", "args":[{"name":"a"}], "field":"x"}
    — this represents "a.x" in C. We try to resolve it as a single dotted
    slot name "a.x" first (UDT field expansion). If that resolves, we emit
    {"slot": "root.fn.a.x"} directly rather than keeping the field op node.
    This is correct because UDT fields are stored as flat scoped slots.

    Literals ({"const":...}) are left unchanged.
    Names that cannot be resolved are left as {"name": ...} — the VM will
    raise NameError if it encounters one, which is the correct behaviour.

    Returns a new tree (does not mutate the input).
    """
    if node is None:
        return None
    if "name" in node:
        resolved = _resolve_slot(node["name"], scope_path, slot_index)
        if resolved:
            return {"slot": resolved}
        return node
    if "const" in node:
        return node
    if "slot" in node:
        return node
    op = node.get("op")
    if op is None:
        return node

    # Special case: field access (a.x or a->x)
    # Try to resolve as a dotted slot name before recursing generically.
    if op == "field":
        field_name = node.get("field", "")
        args = node.get("args", [])
        if args and "name" in args[0]:
            obj_name = args[0]["name"]
            dotted   = f"{obj_name}.{field_name}"
            resolved = _resolve_slot(dotted, scope_path, slot_index)
            if resolved:
                return {"slot": resolved}
        # Fall through to generic resolution below

    resolved_args = [_resolve_expr(a, scope_path, slot_index)
                     for a in node.get("args", [])]
    result = {"op": op, "args": resolved_args}
    for key in ("field", "type", "fn", "of"):
        if key in node:
            result[key] = node[key]
    return result


def _make_row(kind: str, seg_id, scope_path, raw: str, reads: list,
              writes: list, decls: list = None, note: str = None,
              expr: dict = None) -> dict:
    """Construct a single dependency-matrix row dict.

    Args:
        kind: Statement kind (e.g. ``"assign"``, ``"branch"``).
        seg_id: ID of the owning segment, or ``None`` for phi rows.
        scope_path: Dot-separated scope path of the owning segment.
        raw: Original source text of the statement.
        reads: List of scoped slot names read by this statement.
        writes: List of scoped slot names written by this statement.
        decls: List of scoped slot names declared by this statement.
        note: Optional annotation string (e.g. ``"loop_entry"``).
        expr: Optional resolved expression-tree dict.

    Returns:
        A row dict with ``kind``, ``seg_id``, ``scope_path``, ``raw``,
        ``reads``, ``writes``, ``decls``, ``note``, and optionally ``expr``.
    """
    row = {
        "kind":       kind,
        "seg_id":     seg_id,
        "scope_path": scope_path,
        "raw":        raw,
        "reads":      list(dict.fromkeys(reads)),
        "writes":     list(dict.fromkeys(writes)),
        "decls":      list(dict.fromkeys(decls or [])),
        "note":       note,
    }
    if expr is not None:
        row["expr"] = expr
    return row


def _stmt_to_row(stmt, seg_id, scope_path, slot_index):
    """Convert a classified statement dict into a matrix row."""
    kind   = stmt["kind"]
    l_name = stmt.get("l_name")
    r_names = stmt.get("r_names") or []
    raw    = stmt["raw"]

    reads, writes, decls = [], [], []

    # Resolve identifier reads from r_names.
    # If a name resolves directly, use it. If it doesn't but field slots
    # exist for it (e.g. "p1" -> "root.main.p1.x", "root.main.p1.y"),
    # expand to all field slots (UDT variable passed to a call).
    #
    # IMPORTANT: UDT expansion is restricted to slots whose scoped name
    # begins with the current scope_path. This prevents function names
    # in r_names (e.g. "dot_product" from "int dot = dot_product(u,v,3)")
    # from walking up to root and matching callee-internal slots like
    # root.dot_product.sum, root.dot_product.i, etc.
    # A valid UDT field slot looks like: scope_path.varname.fieldname
    # A callee internal slot looks like: root.callee_name.localvar
    # The scope restriction cleanly separates the two.
    for rn in r_names:
        resolved = _resolve_slot(rn, scope_path, slot_index)
        if resolved:
            reads.append(resolved)
        else:
            # UDT expansion: "rn" is a UDT variable passed to a call
            # (e.g. "p1" in compare_points(p1, p2)).  Expand to all field
            # slots of the form scope.rn.field within the CURRENT scope only.
            #
            # We deliberately do NOT walk up ancestor scopes here.  Walking up
            # would cause function names in r_names (e.g. "dot_product") to
            # match root.dot_product.* callee-internal slots.  UDT variables
            # always live in the same scope as the call site (they can't be
            # declared in a parent scope and accessed with field syntax in a
            # child without qualifying the parent — that pattern doesn't exist
            # in C).  So restricting to current scope is both correct and safe.
            prefix = scope_path + f".{rn}."
            expanded = sorted(s for s in slot_index if s.startswith(prefix)
                              # field name must be a single identifier (no dots)
                              and "." not in s[len(prefix):])
            reads.extend(expanded)

    # Resolve literal constant reads
    for cslot in _extract_literal_slots(stmt, scope_path, slot_index):
        reads.append(cslot)

    if kind == "decl":
        if l_name:
            scoped = _resolve_slot(l_name, scope_path, slot_index)
            if scoped:
                decls.append(scoped)
                writes.append(scoped)
            else:
                # UDT decl: parent slot doesn't exist — expand to field slots.
                # e.g. "Point p1 = {3, 4}" -> writes [p1.x, p1.y]
                # We find all slots of the form scope.l_name.* in slot_index.
                import re as _re
                prefix_candidates = []
                parts = scope_path.split(".")
                for depth in range(len(parts), 0, -1):
                    prefix = ".".join(parts[:depth]) + f".{l_name}."
                    matches = [s for s in slot_index if s.startswith(prefix)]
                    if matches:
                        prefix_candidates = sorted(matches)
                        break
                for fslot in prefix_candidates:
                    decls.append(fslot)
                    writes.append(fslot)
                # r_names already contains the initializer values from
                # _classify_statement; reads were resolved above. No
                # further action needed — the positional mapping between
                # initializer values and field slots is implicit (both
                # are ordered by appearance / declaration order).

    elif kind == "assign":
        if l_name:
            scoped = _resolve_slot(l_name, scope_path, slot_index)
            if scoped:
                writes.append(scoped)

    elif kind == "loop_head":
        if l_name:
            # Iterator variable is declared and initialized here — not a read
            scoped = _resolve_slot(l_name, scope_path, slot_index)
            if scoped:
                decls.append(scoped)
                writes.append(scoped)
                # Remove iterator from reads — it appears in r_names but is
                # being written here, not read
                reads[:] = [r for r in reads if r != scoped]

    # control / branch / call / func_decl / expr: reads only

    # Resolve the expr tree from parse.py (unresolved names -> scoped slots)
    unresolved_expr = stmt.get("expr")
    resolved_expr = _resolve_expr(unresolved_expr, scope_path, slot_index) if unresolved_expr else None

    return _make_row(kind, seg_id, scope_path, raw, reads, writes, decls, expr=resolved_expr)


# ---------------------------------------------------------------------------
# Phi node injection
# ---------------------------------------------------------------------------

def _phi_rows_for_branch_group(branch_child_ids, seg_map, children_map, slot_index):
    """
    After a group of branch segments (if/else/else-if), inject phi rows for
    every slot written in any branch. Phi merges writes at reconvergence point.
    """
    written = {}   # scoped_name -> list of source scope_paths that wrote it

    for child_id in branch_child_ids:
        child  = seg_map[child_id]
        cscope = child["scope_path"]
        for stmt in child.get("stmts", []):
            row = _stmt_to_row(stmt, child_id, cscope, slot_index)
            for w in row["writes"] + row["decls"]:
                written.setdefault(w, []).append(cscope)

    phi_rows = []
    for slot, sources in written.items():
        phi_rows.append(_make_row(
            kind="phi",
            seg_id=None,
            scope_path=None,
            raw=f"phi({slot})",
            reads=list(dict.fromkeys(sources)),
            writes=[slot],
            note="branch_reconvergence",
        ))
    return phi_rows


def _collect_writes_in_subtree(seg_id, seg_map, children_map, slot_index):
    """Recursively collect all slots written anywhere in a segment subtree."""
    written = set()
    seg   = seg_map[seg_id]
    scope = seg["scope_path"]
    for stmt in seg.get("stmts", []):
        row = _stmt_to_row(stmt, seg_id, scope, slot_index)
        for w in row["writes"] + row["decls"]:
            written.add(w)
    for child_id in children_map.get(seg_id, []):
        written.update(_collect_writes_in_subtree(child_id, seg_map, children_map, slot_index))
    return written


def _phi_rows_for_loop(loop_seg_id, seg_map, children_map, slot_index):
    """
    At loop entry inject a phi for every slot written anywhere inside the loop
    body (including nested branches/loops). Represents: value is either the
    pre-loop initial value OR the value from the previous iteration (back-edge).
    """
    loop_seg = seg_map[loop_seg_id]
    lscope   = loop_seg["scope_path"]
    written  = _collect_writes_in_subtree(loop_seg_id, seg_map, children_map, slot_index)

    phi_rows = []
    for slot in sorted(written):
        phi_rows.append(_make_row(
            kind="phi",
            seg_id=loop_seg_id,
            scope_path=lscope,
            raw=f"phi({slot})",
            reads=[slot],
            writes=[slot],
            note="loop_entry",
        ))
    return phi_rows


# ---------------------------------------------------------------------------
# Segment traversal
# ---------------------------------------------------------------------------

def _walk_segment(seg_id: int, seg_map: dict, children_map: dict,
                  slot_index: set, rows: list) -> None:
    """Walk a segment and its children in program order, emitting matrix rows.

    Injects phi nodes at branch reconvergence points and loop entry points.
    Recurses into child segments driven by ``branch`` and ``loop_head``
    statements, then flushes any remaining children.

    Args:
        seg_id: ID of the segment to walk.
        seg_map: Dict mapping segment ID to segment dict.
        children_map: Dict mapping parent ID to ordered list of child IDs.
        slot_index: Set of all known scoped slot names (used for resolution).
        rows: Accumulator list; matrix rows are appended in-place.
    """
    seg      = seg_map[seg_id]
    scope    = seg["scope_path"]
    seg_type = seg["type"]
    child_ids = children_map.get(seg_id, [])
    child_iter = iter(child_ids)

    branch_group = []   # accumulates consecutive branch children for phi injection

    def flush_branch_group() -> None:
        """Emit phi rows for any accumulated branch children, then clear the group."""
        if branch_group:
            rows.extend(_phi_rows_for_branch_group(branch_group, seg_map, children_map, slot_index))
        branch_group.clear()

    # Loop: inject entry phi before body, then walk body stmts
    if seg_type == "loop":
        rows.extend(_phi_rows_for_loop(seg_id, seg_map, children_map, slot_index))

    for stmt in seg.get("stmts", []):
        kind = stmt["kind"]

        if kind in ("branch", "loop_head"):
            # Emit the condition/header row
            rows.append(_stmt_to_row(stmt, seg_id, scope, slot_index))
            # Recurse into the matching child block
            try:
                child_id   = next(child_iter)
                child_type = seg_map[child_id]["type"]
                if child_type == "branch":
                    branch_group.append(child_id)
                else:
                    # Non-branch child (loop body) — flush any pending branch group first
                    flush_branch_group()
                _walk_segment(child_id, seg_map, children_map, slot_index, rows)
            except StopIteration:
                pass

        else:
            # Any non-block stmt closes a pending branch group
            flush_branch_group()
            rows.append(_stmt_to_row(stmt, seg_id, scope, slot_index))

    # Flush trailing branch group (e.g. if/else at end of function)
    flush_branch_group()

    # Recurse into any remaining children not consumed by branch/loop logic
    # (e.g., methods inside a Java class, or nested functions)
    for child_id in child_iter:
        _walk_segment(child_id, seg_map, children_map, slot_index, rows)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_matrix(segments: list) -> dict:
    """
    Build the dependency matrix from a list of parsed segment dicts.

    Returns:
      {
        "slots": [...],   ordered list of all scoped slot names (columns)
        "rows":  [...],   list of row dicts, each with reads/writes/decls
      }
    """
    seg_map      = _seg_by_id(segments)
    children_map = _build_children(segments)
    all_slots    = _all_scoped_slots(segments)
    slot_index   = set(all_slots)
    rows         = []

    # Find all root segments (parent == self) — there may be multiple after
    # merging IRs from separate files.
    root_ids = sorted(seg["id"] for seg in segments if seg["id"] == seg["parent"])

    for root_id in root_ids:
        # Root-level stmts (func_decl headers)
        for stmt in seg_map[root_id].get("stmts", []):
            rows.append(_stmt_to_row(stmt, root_id, seg_map[root_id]["scope_path"], slot_index))

        # Walk each top-level child (functions, structs) in order
        for child_id in children_map.get(root_id, []):
            _walk_segment(child_id, seg_map, children_map, slot_index, rows)

    return {
        "slots": all_slots,
        "rows":  rows,
    }