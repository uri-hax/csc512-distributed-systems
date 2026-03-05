"""C source parser for the CDUP pipeline.

Converts a C source string into the common IR JSON used by the rest of
the pipeline.  The parsing pipeline is:

1. Brace scanning — :func:`_find_nested_pairs` identifies all ``{…}`` blocks.
2. Segment extraction — :func:`_parse_code_segs` builds the raw segment tree.
3. Statement classification — :func:`_classify_statement` labels each line.
4. Memory/constant extraction — :func:`_extract_memory` and
   :func:`_extract_constants` populate slot lists.
5. Scope-path assignment — :func:`_build_scope_path` produces dot-separated
   fully-qualified names.

Entry point:
    ``parse_c_file(file_str, ...) -> str``  (returns IR JSON)
"""

import re
import json
from typing import List
try:
    from .models import Segment, Statement, Slot
except ImportError:
    from models import Segment, Statement, Slot

def _pair_opn_cls(cls_open_sequence: list, open_idx: list, cls_idx: list) -> list:
    """Pair opening and closing brace indices from the brace-sequence scan.

    Args:
        cls_open_sequence: Flat list of ``"{"`` and ``"}"`` tokens in source order.
        open_idx: Source indices of each ``"{"`` token.
        cls_idx: Source indices of each ``"}"`` token.

    Returns:
        List of ``(open_pos, close_pos)`` index pairs, one per matched brace.
    """
    pairs = []
    stack = []
    oidx = 0
    cidx = 0
    for i in range(len(cls_open_sequence)):
        if cls_open_sequence[i] == 1:
            stack.append(open_idx[oidx])
            oidx += 1
        else:
            pairs.append([stack.pop(), cls_idx[cidx]])
            cidx += 1
    return pairs

def _find_nested_pairs(cls_open_sequence) -> list:
    """Identify all matched brace pairs in a source-order brace sequence.

    Args:
        cls_open_sequence: A list of ``(token, source_index)`` tuples where
            token is ``"{"`` or ``"}"``.

    Returns:
        List of ``(open_pos, close_pos)`` source-index pairs.
    """
    n_pairs = cls_open_sequence.count(1)
    parents = [None] * n_pairs
    stack = []
    pair_idx = 0
    for val in cls_open_sequence:
        if val == 1:
            current = pair_idx
            if stack:
                parents[current] = stack[-1]
            else:
                parents[current] = current
            stack.append(current)
            pair_idx += 1
        else:
            stack.pop()
    return parents

def _parse_code_segs(file_str: str, pairs: list, parents: list):
    """Extract raw code segments from the source string using brace-pair positions.

    Args:
        file_str: The full source string.
        pairs: List of ``(open_pos, close_pos)`` brace-pair index tuples.
        parents: List of parent-segment indices parallel to ``pairs``.

    Returns:
        List of raw segment strings, one per brace-delimited block.
    """
    raw_segs = []
    for i in range(len(pairs)):
        raw_segs.append(file_str[pairs[i][0] : pairs[i][1]])

    segs = raw_segs.copy()
    for i in sorted(range(len(segs)), key=lambda i: pairs[i][0], reverse=True):
        parent = parents[i]
        if parent != i:
            parent_start = pairs[parent][0]
            child_start = pairs[i][0] - parent_start
            child_end = pairs[i][1] - parent_start
            segs[parent] = segs[parent][:child_start] + segs[parent][child_end:]

    root_seg = file_str
    for i in sorted(range(len(pairs)), key=lambda i: pairs[i][0], reverse=True):
        if parents[i] == i:
            root_seg = root_seg[:pairs[i][0]] + root_seg[pairs[i][1]:]

    return [root_seg] + segs

def _parse_statements(seg: str, include_comments: bool = False,
                      include_includes: bool = False, include_macros: bool = False) -> list:
    statements = []
    current = ""
    i = 0
    depth = 0

    def _add_statement(stmt):
        if not stmt:
            return
        if stmt.startswith("#"):
            is_inc = stmt[1:].lstrip().startswith("include")
            if is_inc and not include_includes:
                return
            if not is_inc and not include_macros:
                return
        statements.append(stmt)

    while i < len(seg):
        if seg[i] == '"' and depth == 0:
            current += seg[i]
            i += 1
            while i < len(seg):
                current += seg[i]
                if seg[i] == '\\':
                    i += 1
                    if i < len(seg):
                        current += seg[i]
                elif seg[i] == '"':
                    i += 1
                    break
                i += 1
        elif seg[i] == "'" and depth == 0:
            current += seg[i]
            i += 1
            while i < len(seg):
                current += seg[i]
                if seg[i] == '\\':
                    i += 1
                    if i < len(seg):
                        current += seg[i]
                elif seg[i] == "'":
                    i += 1
                    break
                i += 1
        elif seg[i:i+2] == "//" and depth == 0:
            if current.strip():
                _add_statement(current.strip())
            current = ""
            comment_str = ""
            while i < len(seg) and seg[i] != "\n":
                comment_str += seg[i]
                i += 1
            if include_comments:
                stmt = comment_str.strip()
                if stmt:
                    statements.append(stmt)
        elif seg[i:i+2] == "/*" and depth == 0:
            if current.strip():
                _add_statement(current.strip())
            current = ""
            comment_str = ""
            while i < len(seg) and seg[i:i+2] != "*/":
                comment_str += seg[i]
                i += 1
            if i < len(seg):
                comment_str += "*/"
                i += 2
            if include_comments:
                stmt = comment_str.strip()
                if stmt:
                    statements.append(stmt)
        elif seg[i] == "(":
            depth += 1
            current += seg[i]
            i += 1
        elif seg[i] == ")":
            depth -= 1
            current += seg[i]
            i += 1
        elif seg[i:i+2] == "{}" and depth == 0:
            current += "{}"
            # Do-while: don't emit yet — peek ahead to collect 'while (...);' tail
            # Must be exactly 'do' or 'do{' — not 'double', 'doSomething', etc.
            _stripped = current.strip()
            _is_do = (_stripped == "do" or _stripped.startswith("do ")
                      or _stripped.startswith("do{") or _stripped.startswith("do\n"))
            if _is_do:
                pending_do = current.strip()
                current = ""
                i += 2
                # Skip whitespace then collect up to the next ';'
                tail = ""
                while i < len(seg):
                    if seg[i] == '(':
                        depth += 1
                        tail += seg[i]
                    elif seg[i] == ')':
                        depth -= 1
                        tail += seg[i]
                    elif seg[i] == ';' and depth == 0:
                        tail += ';'
                        i += 1
                        break
                    else:
                        tail += seg[i]
                    i += 1
                tail = tail.strip()
                if tail.startswith("while"):
                    _add_statement(f"{pending_do} {tail}")
                else:
                    # Unexpected — emit do {} alone, then the tail separately
                    _add_statement(pending_do)
                    if tail:
                        _add_statement(tail)
                continue
            _add_statement(current.strip())
            current = ""
            i += 2
        elif seg[i] == ";" and depth == 0:
            current += ";"
            _add_statement(current.strip())
            current = ""
            i += 1
        elif seg[i] == "\n" and depth == 0 and current.strip().startswith("#"):
            _add_statement(current.strip())
            current = ""
            i += 1
        else:
            current += seg[i]
            i += 1

    if current.strip():
        _add_statement(current.strip())

    return statements


# ---------------------------------------------------------------------------
# Statement classification
# ---------------------------------------------------------------------------

_C_TYPES = {
    "int", "char", "float", "double", "long", "short", "unsigned", "signed",
    "void", "size_t", "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "int8_t", "int16_t", "int32_t", "int64_t", "bool", "FILE"
}

_C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "inline",
    "int", "long", "register", "restrict", "return", "short", "signed", "sizeof",
    "static", "struct", "switch", "typedef", "union", "unsigned", "void",
    "volatile", "while", "NULL", "true", "false"
}

_IDENTIFIER_RE = re.compile(r'[A-Za-z_]\w*')
_ASSIGN_OPS = ["<<=", ">>=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "="]
_CONTROL_KEYWORDS = {"return", "break", "continue", "goto"}
_BRANCH_KEYWORDS  = {"if", "else", "switch", "case"}
_LOOP_KEYWORDS    = {"for", "while", "do"}

def _extract_identifiers(expr: str, known_types: set = None,
                         known_udt_vars: set = None) -> list:
    """Return identifiers in expr, excluding C keywords, types, and string literal contents.

    For variables in known_udt_vars (UDT instances), field access like a.x or
    a->x is preserved as "a.x" so the caller gets field-level slot names.
    For all other identifiers, dot/arrow chains are collapsed to the root variable
    (existing behaviour, zero regression).

    known_udt_vars: set of bare variable names that are UDT instances.
                    If None (default), all chains are collapsed (old behaviour).
    """
    if known_types is None:
        known_types = _C_TYPES
    expr_no_strings = re.sub(r'"(?:[^"\\]|\\.)*"', "", expr)

    if known_udt_vars:
        # Normalise arrow to dot so we only handle one separator
        expr_no_strings = re.sub(r'([A-Za-z_]\w*)\s*->\s*([A-Za-z_]\w*)',
                                 r'\1.\2', expr_no_strings)
        # For UDT vars preserve "var.field"; for others collapse to "var".
        def _replace_field(m):
            root, field = m.group(1), m.group(2)
            if root in known_udt_vars:
                return f"{root}\x00{field}"   # placeholder; \x00 restored below
            return root
        expr_no_strings = re.sub(r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)',
                                 _replace_field, expr_no_strings)
        # Collapse any remaining (non-UDT) dot chains
        expr_no_strings = re.sub(r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)', r'\1', expr_no_strings)
        # Restore placeholders
        expr_no_strings = expr_no_strings.replace('\x00', '.')
        # Tokenise: match "var.field" tokens first, then plain identifiers
        token_pattern = re.compile(r'[A-Za-z_]\w*\.[A-Za-z_]\w*|[A-Za-z_]\w*')
        return [t for t in token_pattern.findall(expr_no_strings)
                if t not in _C_KEYWORDS and t not in known_types
                and t.split('.')[0] not in known_types]
    else:
        # Original behaviour: collapse all chains
        expr_no_strings = re.sub(r'([A-Za-z_]\w*)(?:\.|->)[A-Za-z_]\w*', r'\1', expr_no_strings)
        expr_no_strings = re.sub(r'([A-Za-z_]\w*)(?:\.|->)[A-Za-z_]\w*', r'\1', expr_no_strings)
        return [t for t in _IDENTIFIER_RE.findall(expr_no_strings)
                if t not in _C_KEYWORDS and t not in known_types]

def _extract_literals(raw: str) -> dict:
    """
    Extract all literal values from a raw statement.
    Returns {"ints": [...], "floats": [...], "strings": [...], "chars": [...]}
    """
    # Strip string/char literals from raw before scanning for numbers
    strings = re.findall(r'"(?:[^"\\]|\\.)*"', raw)
    chars   = re.findall(r"'(?:[^'\\]|\\.)*'", raw)
    stripped = re.sub(r'"(?:[^"\\]|\\.)*"', "", raw)
    stripped = re.sub(r"'(?:[^'\\]|\\.)*'", "", stripped)
    floats = re.findall(r'\b\d+\.\d+\b', stripped)
    # integers: exclude those that were part of a float already
    ints = re.findall(r'\b(\d+)\b', stripped)
    # filter out integers that appear as part of a float (already captured)
    float_parts = set()
    for f in floats:
        a, b = f.split(".")
        float_parts.add(a)
        float_parts.add(b)
    ints = [x for x in ints if x not in float_parts]
    return {"ints": ints, "floats": floats, "strings": strings, "chars": chars}

def _canonical_constant_name(kind: str, value: str, string_index: int = 0) -> str:
    """
    Convert a literal value to a canonical constant slot name.
      int    10      -> const_int_10
      float  10.1    -> const_float_10p1
      char   'a'     -> const_char_a
      char   '\n'    -> const_char_newline
      string "hello" -> const_str_0  (indexed, content too long to embed)
    """
    if kind == "int":
        return f"const_int_{value}"
    if kind == "float":
        return "const_float_" + value.replace(".", "p")
    if kind == "char":
        inner = value.strip("'")
        escape_map = {
            "\\n": "newline", "\\t": "tab", "\\r": "cr",
            "\\0": "null", "\\\\": "backslash", "\\'": "squote"
        }
        name = escape_map.get(inner, inner if inner.isalnum() else f"0x{ord(inner):02x}" if len(inner) == 1 else "esc")
        return f"const_char_{name}"
    if kind == "string":
        return f"const_str_{string_index}"
    return f"const_{kind}_{string_index}"

def _classify_statement(raw: str, known_types: set = None,
                        known_udt_vars: set = None) -> Statement:
    """
    Classify a raw C statement into a Statement dataclass.
    """
    if known_types is None:
        known_types = _C_TYPES

    def _ids(expr):
        return _extract_identifiers(expr, known_types, known_udt_vars)

    s = raw.strip().rstrip(";").strip()
    first_word = s.split()[0] if s.split() else ""

    # --- block headers (contain {} placeholder) ---
    if "{}" in raw:
        if first_word in _LOOP_KEYWORDS:
            iterator_name = None
            iterator_type = None
            if first_word == "for" and "(" in s and ";" in s:
                try:
                    inner = s[s.index("(")+1 : s.rindex(")")]
                    init_clause = inner.split(";")[0].strip()
                    init_tokens = init_clause.split()
                    if init_tokens and init_tokens[0].rstrip("*") in known_types:
                        rest = init_clause[len(init_tokens[0]):].strip().lstrip("*").strip()
                        nm = _IDENTIFIER_RE.match(rest)
                        if nm:
                            iterator_name = nm.group(0)
                            iterator_type = init_tokens[0]
                except (ValueError, IndexError):
                    pass
            return Statement(raw=raw, kind="loop_head", l_name=iterator_name,
                             iterator_type=iterator_type, r_names=_ids(s))
        if first_word in _BRANCH_KEYWORDS:
            return Statement(raw=raw, kind="branch", l_name=None, r_names=_ids(s))
        # func_decl: <type> <n>(...){}
        tokens_s = s.split()
        base = tokens_s[0].rstrip("*") if tokens_s else ""
        if base in known_types:
            rest = s[len(tokens_s[0]):].strip().lstrip("*").strip()
            nm = _IDENTIFIER_RE.match(rest)
            if nm and rest[nm.end():].strip().startswith("("):
                param_names = _ids(rest[nm.end():])
                return Statement(raw=raw, kind="func_decl",
                        l_name=nm.group(0), r_names=param_names)
        return Statement(raw=raw, kind="expr", l_name=None,
                r_names=_ids(s))

    # --- control ---
    if first_word in _CONTROL_KEYWORDS:
        return Statement(raw=raw, kind="control", l_name=None,
                r_names=_ids(s[len(first_word):]))

    # --- bare branch (else, case X:, default:) ---
    if first_word in _BRANCH_KEYWORDS:
        return Statement(raw=raw, kind="branch", l_name=None,
                r_names=_ids(s))

    # --- func_decl or decl: starts with a known C type ---
    tokens = s.split()
    base_type = tokens[0].rstrip("*") if tokens else ""
    if base_type in known_types:
        rest = s[len(tokens[0]):].strip().lstrip("*").strip()
        nm = _IDENTIFIER_RE.match(rest)
        if nm:
            after_name = rest[nm.end():].strip()
            if after_name.startswith("("):
                param_names = _ids(after_name)
                return Statement(raw=raw, kind="func_decl",
                        l_name=nm.group(0), r_names=param_names)
            l_name = nm.group(0)
            if after_name.startswith("="):
                rhs = after_name[1:].strip()
                if rhs.startswith("{") and rhs.endswith("}"):
                    rhs = rhs[1:-1]
                r_names = _ids(rhs)
            else:
                r_names = []
            return Statement(raw=raw, kind="decl", type=tokens[0],
                    l_name=l_name, r_names=r_names)

    # --- assignment: compound or simple ---
    # Handles plain vars (x = rhs) and field targets (a.x = rhs, a->x = rhs)
    for op in _ASSIGN_OPS:
        idx = s.find(op)
        if idx > 0:
            lhs = s[:idx].strip()
            rhs = s[idx + len(op):].strip()
            lhs_field = re.fullmatch(r'([A-Za-z_]\w*)(?:\.|->)([A-Za-z_]\w*)', lhs)
            lhs_plain = _IDENTIFIER_RE.match(lhs)
            if lhs_field:
                root_var = lhs_field.group(1)
                field    = lhs_field.group(2)
                dotted   = f"{root_var}.{field}" if (known_udt_vars and root_var in known_udt_vars) else root_var
                r_names  = _ids(rhs)
                if op != "=":
                    if dotted not in r_names:
                        r_names = [dotted] + r_names
                return Statement(raw=raw, kind="assign",
                        l_name=dotted, r_names=r_names)
            elif lhs_plain and lhs_plain.end() == len(lhs):
                r_names = _ids(rhs)
                if op != "=":
                    l = lhs_plain.group(0)
                    if l not in r_names:
                        r_names = [l] + r_names
                return Statement(raw=raw, kind="assign",
                        l_name=lhs_plain.group(0),
                        r_names=r_names)

    # --- standalone call ---
    if "(" in s:
        call_match = _IDENTIFIER_RE.match(s)
        if call_match and s[call_match.end():].lstrip().startswith("("):
            return Statement(raw=raw, kind="call", l_name=None,
                    r_names=_ids(s[s.index("("):]))

    # --- increment / decrement: x++, x--, ++x, --x ---
    incr_match = re.fullmatch(r'([A-Za-z_]\w*)\s*(\+\+|--)', s)
    if not incr_match:
        incr_match2 = re.fullmatch(r'(\+\+|--)\s*([A-Za-z_]\w*)', s)
        if incr_match2:
            var_name = incr_match2.group(2)
            return Statement(raw=raw, kind="assign", l_name=var_name,
                    r_names=[var_name])
    if incr_match:
        var_name = incr_match.group(1)
        return Statement(raw=raw, kind="assign", l_name=var_name,
                r_names=[var_name])

    return Statement(raw=raw, kind="expr", l_name=None,
            r_names=_ids(s))


def _extract_params(head: str, scope_path: str, known_types: set = None,
                    struct_fields: dict = None) -> List[Slot]:
    """
    Extract typed parameter names from a function header string.
    Returns Slot dataclasses with scoped names and param=True flag.
    """
    if known_types is None:
        known_types = _C_TYPES
    if struct_fields is None:
        struct_fields = {}
    if not head:
        return []
    try:
        inner = head[head.index('(')+1 : head.rindex(')')]
    except ValueError:
        return []
    inner = inner.strip()
    if not inner or inner == 'void':
        return []
    params = []
    for param in inner.split(','):
        param = param.strip()
        tokens = param.split()
        if len(tokens) < 2:
            continue
        ptype = tokens[0].rstrip('*')
        if ptype not in known_types:
            continue
        last = tokens[-1]
        bracket_pos = last.find('[')
        if bracket_pos != -1:
            last = last[:bracket_pos]
        pname = last.strip('*').strip()
        if not pname or pname in _C_KEYWORDS or pname in known_types:
            continue
        # UDT parameter: expand to field slots
        if ptype in struct_fields:
            for field in struct_fields[ptype]:
                params.append(Slot(
                    name=f"{pname}.{field}",
                    scoped_name=f"{scope_path}.{pname}.{field}",
                    type="field",
                    constant=False,
                    param=True,
                    udt_parent=pname,
                    udt_type=ptype,
                ))
        else:
            params.append(Slot(
                name=pname,
                scoped_name=f"{scope_path}.{pname}",
                type=tokens[0],
                constant=False,
                param=True,
            ))
    return params

def _extract_memory(raw_stmts: list, scope_path: str, known_types: set = None,
                    struct_fields: dict = None) -> List[Slot]:
    """
    Scan raw statements for variable declarations.
    Returns Slot dataclasses with scoped names.
    """
    if known_types is None:
        known_types = _C_TYPES
    if struct_fields is None:
        struct_fields = {}
    memory = []
    for stmt in raw_stmts:
        op = _classify_statement(stmt, known_types)
        if op.kind == "decl" and op.l_name:
            dtype = op.type.rstrip("*") if op.type else "unknown"
            vname = op.l_name
            if dtype in struct_fields:
                for field in struct_fields[dtype]:
                    memory.append(Slot(
                        name=f"{vname}.{field}",
                        scoped_name=f"{scope_path}.{vname}.{field}",
                        type="field",
                        constant=False,
                        udt_parent=vname,
                        udt_type=dtype,
                    ))
            else:
                memory.append(Slot(
                    name=vname,
                    scoped_name=f"{scope_path}.{vname}",
                    type=op.type or "unknown",
                    constant=False,
                ))
        elif op.kind == "loop_head" and op.l_name:
            memory.append(Slot(
                name=op.l_name,
                scoped_name=f"{scope_path}.{op.l_name}",
                type=op.iterator_type or "unknown",
                constant=False,
                loop_iterator=True,
            ))
    return memory

def _extract_constants(classified_stmts: List[Statement], scope_path: str) -> List[Slot]:
    """
    Scan classified stmts for literal values and return Slot dataclasses.
    """
    seen = {}
    string_counter = [0]

    def _add(kind, value):
        if kind == "string":
            cname = _canonical_constant_name("string", value, string_counter[0])
            string_counter[0] += 1
        else:
            cname = _canonical_constant_name(kind, value)
        if cname not in seen:
            seen[cname] = Slot(
                name=cname,
                scoped_name=f"{scope_path}.{cname}",
                type=kind,
                constant=True,
                value=value,
            )

    for stmt in classified_stmts:
        if stmt.kind == "func_decl":
            continue
        lits = _extract_literals(stmt.raw)
        for v in lits["ints"]:    _add("int",    v)
        for v in lits["floats"]:  _add("float",  v)
        for v in lits["strings"]: _add("string", v)
        for v in lits["chars"]:   _add("char",   v)

    return list(seen.values())

def _get_seg_type(header: str) -> str:
    """Determine segment type from its header statement in the parent."""
    if header is None:
        return "root"
    h = header.strip()
    if h.startswith("struct ") or h.startswith("typedef struct"):
        return "struct"
    for kw in ["for ", "for(", "while ", "while(", "do ", "do{"]:
        if h.startswith(kw):
            return "loop"
    for kw in ["if ", "if(", "else", "switch ", "switch("]:
        if h.startswith(kw):
            return "branch"
    return "function"

def _get_seg_name(seg_type: str, head: str, child_index: int) -> str:
    """
    Derive a human-readable name for a segment.
      root      -> "root"
      function  -> function name extracted from head  e.g. "add"
      loop      -> "loop_1", "loop_2" ... (1-indexed child_index)
      branch    -> "branch_1", "branch_2" ...
      struct    -> struct name extracted from head
    """
    if seg_type == "root":
        return "root"
    if seg_type == "function" and head:
        # head looks like "int add(int a, int b) {}"
        # extract the identifier after the return type
        # The return type can be a primitive or a UDT — accept any identifier token
        tokens = head.strip().split()
        base = tokens[0].rstrip("*") if tokens else ""
        if _IDENTIFIER_RE.fullmatch(base) and len(tokens) > 1:
            rest = head[len(tokens[0]):].strip().lstrip("*").strip()
            nm = _IDENTIFIER_RE.match(rest)
            if nm and rest[nm.end():].strip().startswith("("):
                return nm.group(0)
    if seg_type == "struct" and head:
        h = head.strip()
        # typedef struct { ... } Point;  -> name comes from after the closing }
        # which is in the *parent* statement: "typedef struct {} Point;"
        # The head here is the stmt with {}, so check for typedef pattern
        if "typedef" in h:
            # "typedef struct {}" — name is on the following "Point;" stmt in parent
            # We can't resolve it here without parent context, return placeholder
            # that will be patched in parse_c_file after all segments are built
            return "__typedef__"
        tokens = h.split()
        if len(tokens) > 1:
            return tokens[1].rstrip("{").strip()
    if seg_type == "loop":
        return f"loop_{child_index}"
    if seg_type == "branch":
        return f"branch_{child_index}"
    return f"seg_{child_index}"

def _build_scope_path(seg_id: int, seg_names: dict, bparents: list) -> str:
    """
    Walk up the parent chain to build the full dot-separated scope path.
    e.g. "root.add.loop_1"
    """
    path_parts = []
    current = seg_id
    visited = set()
    while True:
        if current in visited:
            break
        visited.add(current)
        path_parts.append(seg_names[current])
        parent = bparents[current]
        if parent == current:
            break
        current = parent
    return ".".join(reversed(path_parts))

def _error_handling(bcos, pcos, boidx, bcidx, poidx, pcidx) -> None:
    """Validate that brace and parenthesis counts are balanced.

    Args:
        bcos: Brace open-close sequence list.
        pcos: Parenthesis open-close sequence list.
        boidx: Brace open-index list.
        bcidx: Brace close-index list.
        poidx: Parenthesis open-index list.
        pcidx: Parenthesis close-index list.

    Raises:
        ValueError: If any bracket type is unbalanced.
    """
    if not bcos:
        return
    if bcos[0] != 1:
        raise ValueError("C program starts with } before {")
    if bcos[-1] != 0:
        raise ValueError("C program final open { is not closed with }")
    if len(boidx) != len(bcidx):
        raise ValueError("C program does not have the same number of { and }")
    if pcos and pcos[0] != 1:
        raise ValueError("C program starts with ) before (")
    if pcos and pcos[-1] != 0:
        raise ValueError("C program final open ( is not closed with )")
    if len(poidx) != len(pcidx):
        raise ValueError("C program does not have the same number of ( and )")

def parse_c_file(file_str: str, include_comments: bool = False,
                 include_includes: bool = False, include_macros: bool = False) -> str:

    b_cls_open_sequence = []
    p_cls_open_sequence = []
    open_bidx  = []
    cls_bidx   = []
    open_pidx  = []
    cls_pidx   = []

    i = 0
    in_line_comment  = False
    in_block_comment = False
    in_string        = False
    in_char_literal  = False
    initializer_depth = 0  # tracks {} used as data initializers, not code blocks

    while i < len(file_str):
        c = file_str[i]

        if in_line_comment:
            if c == '\n':
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if file_str[i:i+2] == '*/':
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if c == '\\':
                i += 2
            elif c == '"':
                in_string = False
                i += 1
            else:
                i += 1
            continue
        if in_char_literal:
            if c == '\\':
                i += 2
            elif c == "'":
                in_char_literal = False
                i += 1
            else:
                i += 1
            continue

        if file_str[i:i+2] == '//':
            in_line_comment = True
            i += 2
            continue
        if file_str[i:i+2] == '/*':
            in_block_comment = True
            i += 2
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == "'":
            in_char_literal = True
            i += 1
            continue

        if c == '{':
            # Initializer brace: { immediately preceded by = (ignoring whitespace)
            j = i - 1
            while j >= 0 and file_str[j] in (' ', '\t', '\n', '\r'):
                j -= 1
            if j >= 0 and file_str[j] == '=':
                initializer_depth += 1
            elif initializer_depth > 0:
                initializer_depth += 1
            else:
                b_cls_open_sequence.append(1)
                open_bidx.append(i + 1)
        elif c == '}':
            if initializer_depth > 0:
                initializer_depth -= 1
            else:
                b_cls_open_sequence.append(0)
                cls_bidx.append(i)
        elif c == '(':
            p_cls_open_sequence.append(1)
            open_pidx.append(i + 1)
        elif c == ')':
            p_cls_open_sequence.append(0)
            cls_pidx.append(i)

        i += 1

    """
    _error_handling(
        b_cls_open_sequence, p_cls_open_sequence,
        open_bidx, cls_bidx, open_pidx, cls_pidx
    )
    """

    bpairs = sorted(_pair_opn_cls(b_cls_open_sequence, open_bidx, cls_bidx), key=lambda r: r[0])
    ppairs = sorted(_pair_opn_cls(p_cls_open_sequence, open_pidx, cls_pidx), key=lambda r: r[0])

    bparents = _find_nested_pairs(b_cls_open_sequence)
    pparents = _find_nested_pairs(p_cls_open_sequence)

    bsegs = _parse_code_segs(file_str, bpairs, bparents)
    _parse_code_segs(file_str, ppairs, pparents)  # paren segs unused at this stage

    bparents = [0 if bparents[i] == i else bparents[i] + 1 for i in range(len(bparents))]
    bparents = [0] + bparents

    # Clean segments
    cleaned_segs = []
    for seg in bsegs:
        seg = "\n".join(line.strip() for line in seg.splitlines() if line.strip())
        cleaned_segs.append(seg)

    # Extract raw statements per segment
    bseg_stmnts = [
        _parse_statements(seg, include_comments, include_includes, include_macros)
        for seg in cleaned_segs
    ]

    # Build children map and header info
    children_of = {}
    for seg_id in range(1, len(bsegs)):
        children_of.setdefault(bparents[seg_id], []).append(seg_id)

    def get_block_stmts(stmnts):
        return [(idx, s) for idx, s in enumerate(stmnts) if "{}" in s]

    seg_headers = {0: None}
    for parent_id, child_ids in children_of.items():
        block_stmts = get_block_stmts(bseg_stmnts[parent_id])
        for i, child_id in enumerate(child_ids):
            seg_headers[child_id] = block_stmts[i][1] if i < len(block_stmts) else None

    # --- First pass: assign names and build scope paths ---
    # Track per-parent how many loops/branches we've seen (for numbering)
    type_counters = {}   # parent_id -> {"loop": 0, "branch": 0}
    seg_names = {}

    for seg_id in range(len(bsegs)):
        head      = seg_headers.get(seg_id)
        seg_type  = _get_seg_type(head)
        parent_id = bparents[seg_id]

        if seg_type in ("loop", "branch"):
            if parent_id not in type_counters:
                type_counters[parent_id] = {"loop": 0, "branch": 0}
            type_counters[parent_id][seg_type] += 1
            child_index = type_counters[parent_id][seg_type]
        else:
            child_index = 0

        seg_names[seg_id] = _get_seg_name(seg_type, head, child_index)

    # Patch typedef struct names: after seg_names loop, find segments named
    # "__typedef__" and resolve their name from the following "TypeName;" stmt
    # in the parent segment.
    for seg_id, name in seg_names.items():
        if name == "__typedef__":
            parent_id = bparents[seg_id]
            parent_stmts = bseg_stmnts[parent_id]
            # Find the stmt index of "typedef struct {}" in the parent
            for idx, stmt in enumerate(parent_stmts):
                if "typedef" in stmt and "{}" in stmt:
                    # The very next stmt should be "TypeName;"
                    if idx + 1 < len(parent_stmts):
                        next_stmt = parent_stmts[idx + 1].strip().rstrip(";").strip()
                        if _IDENTIFIER_RE.fullmatch(next_stmt):
                            seg_names[seg_id] = next_stmt
                            break
            # If still unresolved, fall back to a generic name
            if seg_names[seg_id] == "__typedef__":
                seg_names[seg_id] = "struct_0"

    scope_paths = {
        seg_id: _build_scope_path(seg_id, seg_names, bparents)
        for seg_id in range(len(bsegs))
    }

    # --- Pass 0: collect user-defined type names and struct field registries ---
    # user_types: set of known type names (C builtins + struct names)
    # struct_fields: maps struct name -> ordered list of field names
    # These let us recognise `Point p1` as a decl and expand its fields.
    user_types = _C_TYPES | {
        seg_names[i]
        for i in range(len(bsegs))
        if _get_seg_type(seg_headers.get(i)) == "struct" and seg_names.get(i)
    }

    # Build struct_fields by doing a quick pre-pass over struct segments.
    # We need field names, which come from decl statements inside the struct body.
    struct_fields = {}   # e.g. {"Point": ["x", "y"]}
    for i in range(len(bsegs)):
        if _get_seg_type(seg_headers.get(i)) != "struct":
            continue
        sname = seg_names.get(i)
        if not sname:
            continue
        fields = []
        for stmt in bseg_stmnts[i]:
            op = _classify_statement(stmt, user_types)
            if op.kind == "decl" and op.l_name:
                fields.append(op.l_name)
        struct_fields[sname] = fields

    # --- Build descendant map for constant collection ---
    # Maps seg_id -> list of direct descendant seg_ids that are NOT nested
    # function/struct scopes (those own their own constants).
    # Stops recursing at function/struct boundaries so grandchildren of nested
    # functions are never included in a parent's constant scan.
    def _owned_descendants(seg_id, children_of):
        """Return all descendant seg_ids within the same function/root scope."""
        result = []
        for child in children_of.get(seg_id, []):
            child_type = _get_seg_type(seg_headers.get(child))
            if child_type in ("function", "struct"):
                continue  # this child owns its own constants; don't descend
            result.append(child)
            result.extend(_owned_descendants(child, children_of))
        return result

    # --- Second pass: build final segment list ---
    segments: List[Segment] = []
    for seg_id in range(len(bsegs)):
        head       = seg_headers.get(seg_id)
        seg_type   = _get_seg_type(head)
        scope_path = scope_paths[seg_id]
        raw_stmts  = bseg_stmnts[seg_id]

        known_udt_vars_here = set()
        for stmt in raw_stmts:
            op0 = _classify_statement(stmt, user_types)
            if op0.kind == "decl" and op0.l_name:
                if (op0.type or "").rstrip("*") in struct_fields:
                    known_udt_vars_here.add(op0.l_name)

        if seg_type == "function" and head:
            try:
                inner = head[head.index('(')+1 : head.rindex(')')]
                for param in inner.split(','):
                    toks = param.strip().split()
                    if len(toks) >= 2:
                        ptype = toks[0].rstrip('*')
                        if ptype in struct_fields:
                            pname = toks[-1].strip('*[]').strip()
                            if pname:
                                known_udt_vars_here.add(pname)
            except ValueError:
                pass

        if seg_type in ("loop", "branch"):
            parent_id = bparents[seg_id]
            if parent_id != seg_id and parent_id < len(segments):
                for slot in segments[parent_id].memory:
                    if slot.udt_parent:
                        known_udt_vars_here.add(slot.udt_parent)

        udt_vars = known_udt_vars_here if known_udt_vars_here else None

        classified = [_classify_statement(s, user_types, udt_vars) for s in raw_stmts]
        params     = _extract_params(head, scope_path, user_types, struct_fields) if seg_type == "function" else []
        memory     = params + _extract_memory(raw_stmts, scope_path, user_types, struct_fields)

        udt_expand = {}
        for slot in memory:
            if slot.udt_parent:
                parent = slot.udt_parent
                udt_expand.setdefault(parent, []).append(slot.name)

        if udt_expand:
            def _expand_r_names(r_names):
                result = []
                for rn in r_names:
                    if rn in udt_expand:
                        result.extend(udt_expand[rn])
                    else:
                        result.append(rn)
                return result
            for st in classified:
                st.r_names = _expand_r_names(st.r_names)

        # Attach expr trees
        try:
            try:
                from .expr import parse_expr, extract_condition, build_assign_expr
            except ImportError:
                from expr import parse_expr, extract_condition, build_assign_expr

            def _attach_expr(st):
                kind = st.kind
                raw  = st.raw
                expr = None

                if kind == "assign":
                    l_name = st.l_name or ""
                    s = raw.strip().rstrip(";").strip()
                    op_token = "="
                    for cop in ("+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="):
                        idx = s.find(cop)
                        if idx > 0:
                            op_token = cop
                            rhs_src  = s[idx + len(cop):].strip()
                            break
                    else:
                        eq_idx = s.find("=")
                        if eq_idx > 0:
                            rhs_src = s[eq_idx + 1:].strip()
                        else:
                            incr = re.search(r'\+\+|--', s)
                            if incr:
                                op_str = incr.group(0)
                                st.expr = {"op": "post_inc" if op_str == "++" else "post_dec",
                                           "args": [{"name": l_name}]}
                            return
                    st.expr = build_assign_expr(l_name, op_token, rhs_src)

                elif kind == "decl":
                    raw_s = raw.strip().rstrip(";")
                    eq_idx = raw_s.find("=")
                    if eq_idx > 0:
                        rhs_src = raw_s[eq_idx + 1:].strip()
                        if rhs_src.startswith("{") and rhs_src.endswith("}"):
                            rhs_src = rhs_src[1:-1].strip()
                        st.expr = parse_expr(rhs_src)

                elif kind in ("branch", "loop_head", "control"):
                    cond_src = extract_condition(raw, kind)
                    if cond_src:
                        st.expr = parse_expr(cond_src)

                elif kind == "call":
                    s = raw.strip().rstrip(";").strip()
                    st.expr = parse_expr(s)

            for st in classified:
                _attach_expr(st)

        except Exception:
            pass

        if seg_type in ("function", "root", "struct"):
            all_classified = classified[:]
            for desc_id in _owned_descendants(seg_id, children_of):
                desc_stmts = [_classify_statement(s, user_types, udt_vars) for s in bseg_stmnts[desc_id]]
                all_classified.extend(desc_stmts)
            constants = _extract_constants(all_classified, scope_path)
        else:
            constants = []

        segments.append(Segment(
            id=seg_id,
            parent=bparents[seg_id],
            type=seg_type,
            name=seg_names[seg_id],
            scope_path=scope_path,
            head=head,
            memory=memory,
            constants=constants,
            stmts=classified,
        ))

    # Build matrix and DAG
    try:
        from .matrix import build_matrix
        from .dag import build_dag
    except ImportError:
        from matrix import build_matrix
        from dag import build_dag

    # Convert Segments back to dicts for downstream tools to maintain compatibility for now
    seg_dicts = [s.to_dict() for s in segments]
    matrix = build_matrix(seg_dicts)
    dag    = build_dag(seg_dicts, matrix)

    return json.dumps({"segments": seg_dicts, "matrix": matrix, "dag": dag}, indent=2)