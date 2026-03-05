"""
expr.py — Pratt parser for C expression strings.

Converts a raw C RHS/condition string into a nested expression tree.
Names in the tree are UNRESOLVED (bare identifiers, not scoped slot names).
Resolution to scoped slot names happens later in matrix.py.

Tree node shapes:
  {"name": "x"}                        — identifier reference
  {"const": 42,   "type": "int"}       — integer literal
  {"const": 3.14, "type": "float"}     — float literal
  {"const": "'a'","type": "char"}      — char literal
  {"const": '"hi"',"type": "string"}   — string literal
  {"op": "add",   "args": [L, R]}      — binary operation
  {"op": "neg",   "args": [X]}         — unary operation
  {"op": "index", "args": [arr, idx]}  — arr[idx]
  {"op": "field", "args": [obj], "field": "x"}   — obj.x or obj->x
  {"op": "call",  "fn": "f", "args": [...]}       — function call
  {"op": "cast",  "type": "int", "args": [X]}     — (int)x

Entry points:
    parse_expr(src: str) -> dict | None
        Parse a full expression string. Returns None if src is empty/unparseable.

    extract_condition(stmt_raw: str, kind: str) -> str | None
        Extract the condition substring from a branch/loop_head raw string.
"""

import re

# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

# Token types
_TT_NUM    = "NUM"      # integer or float literal
_TT_STR    = "STR"      # string literal  "..."
_TT_CHAR   = "CHAR"     # char literal    '.'
_TT_NAME   = "NAME"     # identifier
_TT_OP     = "OP"       # operator / punctuation
_TT_EOF    = "EOF"

# Two-char operators that must be recognised before single-char
_TWO_CHAR_OPS = {
    "->", "++", "--", "<<", ">>",
    "<=", ">=", "==", "!=",
    "&&", "||",
    "+=", "-=", "*=", "/=", "%=",
    "&=", "|=", "^=",
}

def _tokenize(src: str) -> list:
    """
    Return list of (type, value) pairs. Skips whitespace.
    Handles string/char literals and C-style comments.
    """
    tokens = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]

        # whitespace
        if c in " \t\r\n":
            i += 1
            continue

        # string literal
        if c == '"':
            j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2
                elif src[j] == '"':
                    j += 1
                    break
                else:
                    j += 1
            tokens.append((_TT_STR, src[i:j]))
            i = j
            continue

        # char literal
        if c == "'":
            j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2
                elif src[j] == "'":
                    j += 1
                    break
                else:
                    j += 1
            tokens.append((_TT_CHAR, src[i:j]))
            i = j
            continue

        # numeric literal (int or float)
        if c.isdigit() or (c == '.' and i + 1 < n and src[i+1].isdigit()):
            j = i
            while j < n and (src[j].isdigit() or src[j] in '.eExXabcdefABCDEFuUlL'):
                j += 1
            tokens.append((_TT_NUM, src[i:j]))
            i = j
            continue

        # identifier or keyword
        if c.isalpha() or c == '_':
            j = i
            while j < n and (src[j].isalnum() or src[j] == '_'):
                j += 1
            tokens.append((_TT_NAME, src[i:j]))
            i = j
            continue

        # two-char operator?
        if i + 1 < n and src[i:i+2] in _TWO_CHAR_OPS:
            tokens.append((_TT_OP, src[i:i+2]))
            i += 2
            continue

        # single-char operator / punctuation
        tokens.append((_TT_OP, c))
        i += 1

    tokens.append((_TT_EOF, ""))
    return tokens


# ---------------------------------------------------------------------------
# Operator tables
# ---------------------------------------------------------------------------

# Left binding power for binary/postfix operators
# Higher = tighter binding (C precedence, simplified)
_LBP = {
    "||":  10,
    "&&":  20,
    "|":   30,
    "^":   40,
    "&":   50,
    "==":  60,  "!=":  60,
    "<":   70,  ">":   70,  "<=": 70,  ">=": 70,
    "<<":  80,  ">>":  80,
    "+":   90,  "-":   90,
    "*":  100,  "/":  100,  "%": 100,
    "[":  110,   # index
    ".":  120,  "->": 120,  # field access
    "(":  120,               # call (postfix)
    "++": 130,  "--": 130,   # postfix incr/decr
}

# Mapping from C operator token to canonical op name
_BINOP = {
    "+":  "add",  "-":  "sub",  "*":  "mul",  "/":  "div",  "%":  "mod",
    "&":  "bit_and", "|": "bit_or", "^": "bit_xor",
    "<<": "shl",  ">>": "shr",
    "==": "cmp_eq", "!=": "cmp_ne",
    "<":  "cmp_lt", ">":  "cmp_gt", "<=": "cmp_le", ">=": "cmp_ge",
    "&&": "log_and", "||": "log_or",
}

_UNOP = {
    "-":  "neg",
    "!":  "log_not",
    "~":  "bit_not",
    "&":  "addr_of",
    "*":  "deref",
    "++": "pre_inc",
    "--": "pre_dec",
}

# C type keywords for cast detection
_CAST_TYPES = {
    "int", "long", "short", "char", "unsigned", "signed",
    "float", "double", "void", "size_t", "uint8_t", "uint16_t",
    "uint32_t", "uint64_t", "int8_t", "int16_t", "int32_t", "int64_t",
}


# ---------------------------------------------------------------------------
# Pratt parser
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens):
        self._tokens = tokens
        self._pos    = 0

    # ── Token access ─────────────────────────────────────────────────────────

    def _peek(self):
        return self._tokens[self._pos]

    def _consume(self):
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, val):
        tt, tv = self._consume()
        if tv != val:
            raise ValueError(f"Expected '{val}', got '{tv}'")
        return tv

    def _at_end(self):
        return self._peek()[0] == _TT_EOF

    # ── Core Pratt loop ───────────────────────────────────────────────────────

    def parse(self, min_bp=0):
        """Parse an expression with left binding power >= min_bp."""
        left = self._nud()

        while True:
            tt, tv = self._peek()
            if tt == _TT_EOF:
                break
            bp = _LBP.get(tv, 0)
            if bp <= min_bp:
                break
            left = self._led(left)

        return left

    # ── Null denotation (prefix position) ────────────────────────────────────

    def _nud(self):
        tt, tv = self._consume()

        # numeric literal
        if tt == _TT_NUM:
            if '.' in tv or 'e' in tv.lower():
                return {"const": float(tv), "type": "float"}
            # Strip suffixes like u, l, ul, etc.
            clean = re.sub(r'[uUlL]+$', '', tv)
            try:
                val = int(clean, 0)  # handles 0x hex, 0 octal
            except ValueError:
                val = int(clean) if clean.isdigit() else 0
            return {"const": val, "type": "int"}

        if tt == _TT_STR:
            return {"const": tv, "type": "string"}

        if tt == _TT_CHAR:
            return {"const": tv, "type": "char"}

        if tt == _TT_NAME:
            # Check for cast: (type)expr — but we're past the '(' here.
            # Casts are handled in the '(' branch below.
            # sizeof(x)
            if tv == "sizeof":
                tt2, tv2 = self._peek()
                if tv2 == "(":
                    self._consume()  # consume '('
                    # Could be a type or an expression — read until matching ')'
                    depth = 1
                    inner_toks = []
                    while not self._at_end():
                        t2, v2 = self._consume()
                        if v2 == "(": depth += 1
                        elif v2 == ")":
                            depth -= 1
                            if depth == 0: break
                        inner_toks.append((t2, v2))
                    # Return opaque sizeof node
                    inner_str = " ".join(v for _, v in inner_toks)
                    return {"op": "sizeof", "args": [], "of": inner_str}
                else:
                    inner = self.parse(100)
                    return {"op": "sizeof", "args": [inner], "of": None}
            return {"name": tv}

        if tt == _TT_OP:
            # Parenthesised subexpression or cast
            if tv == "(":
                # Peek ahead: is this a cast like (int) or (unsigned long)?
                saved_pos = self._pos
                cast_type = self._try_parse_cast_type()
                if cast_type is not None:
                    operand = self.parse(99)  # right-associative, tight
                    return {"op": "cast", "type": cast_type, "args": [operand]}
                else:
                    self._pos = saved_pos
                    inner = self.parse(0)
                    self._expect(")")
                    return inner

            # Unary prefix operators
            if tv in _UNOP:
                operand = self.parse(99)   # right-associative
                return {"op": _UNOP[tv], "args": [operand]}

            # Ternary — treat condition as complete expr, skip ?:
            # Fall through to error for anything else

        raise ValueError(f"Unexpected token in nud: ({tt}, {tv!r})")

    def _try_parse_cast_type(self):
        """
        Try to consume a C type name sequence followed by ')'.
        Returns the type string if successful, None otherwise.
        Leaves self._pos just after ')' on success.
        """
        type_parts = []
        while True:
            tt, tv = self._peek()
            if tt == _TT_NAME and tv in _CAST_TYPES:
                type_parts.append(tv)
                self._consume()
            elif tt == _TT_OP and tv == "*":
                type_parts.append("*")
                self._consume()
            else:
                break
        if type_parts:
            tt2, tv2 = self._peek()
            if tv2 == ")":
                self._consume()
                return " ".join(type_parts)
        return None

    # ── Left denotation (infix/postfix position) ──────────────────────────────

    def _led(self, left):
        tt, tv = self._consume()

        # Binary arithmetic / comparison / logical
        if tv in _BINOP:
            right = self.parse(_LBP[tv])   # left-associative
            return {"op": _BINOP[tv], "args": [left, right]}

        # Array index: arr[idx]
        if tv == "[":
            idx = self.parse(0)
            self._expect("]")
            return {"op": "index", "args": [left, idx]}

        # Field access: obj.field or obj->field
        if tv in (".", "->"):
            tt2, field_name = self._consume()
            if tt2 != _TT_NAME:
                raise ValueError(f"Expected field name after '{tv}', got {field_name!r}")
            return {"op": "field", "args": [left], "field": field_name}

        # Function call: fn(args...)
        if tv == "(":
            args = []
            tt2, tv2 = self._peek()
            if tv2 != ")":
                args.append(self.parse(0))
                while True:
                    tt3, tv3 = self._peek()
                    if tv3 != ",":
                        break
                    self._consume()  # consume ','
                    args.append(self.parse(0))
            self._expect(")")
            # Extract function name from left node
            fn_name = left.get("name", "unknown")
            return {"op": "call", "fn": fn_name, "args": args}

        # Postfix ++ / --
        if tv == "++":
            return {"op": "post_inc", "args": [left]}
        if tv == "--":
            return {"op": "post_dec", "args": [left]}

        raise ValueError(f"Unexpected token in led: ({tt}, {tv!r})")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_expr(src: str):
    """
    Parse a C expression string into an expr tree.

    Args:
        src: Raw expression string (RHS of assignment, condition, etc.)
             May include trailing semicolons — they are stripped.

    Returns:
        An expr tree dict, or None if src is empty or cannot be parsed.

    Examples:
        parse_expr("a + b * c")
        -> {"op": "add", "args": [{"name": "a"}, {"op": "mul", "args": [...]}]}

        parse_expr("u[i]")
        -> {"op": "index", "args": [{"name": "u"}, {"name": "i"}]}

        parse_expr("42")
        -> {"const": 42, "type": "int"}
    """
    if not src:
        return None
    src = src.strip().rstrip(";").strip()
    if not src:
        return None

    try:
        tokens = _tokenize(src)
        parser = _Parser(tokens)
        tree = parser.parse(0)
        # If there are unconsumed tokens (other than EOF), something went wrong
        tt, tv = parser._peek()
        if tt != _TT_EOF:
            # Partial parse — return None rather than a corrupt tree
            return None
        return tree
    except (ValueError, IndexError, RecursionError):
        return None


def extract_condition(stmt_raw: str, kind: str):
    """
    Extract the condition/expression substring from a branch or loop_head
    raw statement string, suitable for passing to parse_expr().

    For branch:    "if (dx == 0) {}"  -> "dx == 0"
                   "else {}"           -> None  (no condition)
    For loop_head: "while (i < n) {}" -> "i < n"
                   "for (int i=0; i<n; i++) {}" -> None (too complex, skip)
                   "do {} while (n>0);" -> "n > 0"
    For control:   "return sum;"       -> "sum"
    For assign:    caller passes rhs directly, not needed here
    """
    s = stmt_raw.strip()

    if kind == "branch":
        if s.startswith("if") or s.startswith("else if"):
            m = re.search(r'\((.+)\)\s*\{', s, re.DOTALL)
            if m:
                return m.group(1).strip()
        return None

    if kind == "loop_head":
        if s.startswith("while"):
            m = re.search(r'while\s*\((.+)\)\s*\{', s, re.DOTALL)
            if m:
                return m.group(1).strip()
        if s.startswith("do"):
            m = re.search(r'while\s*\((.+)\)\s*;?\s*$', s, re.DOTALL)
            if m:
                return m.group(1).strip()
        if s.startswith("for"):
            # for (init; condition; update) — extract just the condition
            try:
                inner = s[s.index("(")+1 : s.rindex(")")]
                parts = inner.split(";", 2)
                if len(parts) >= 2:
                    return parts[1].strip()
            except (ValueError, IndexError):
                pass
        return None

    if kind == "control":
        # "return expr;"  or  "return;"
        m = re.match(r'return\s+(.*)', s.rstrip(";").strip())
        if m:
            return m.group(1).strip() or None
        return None

    return None


# ---------------------------------------------------------------------------
# Compound assignment decomposition
# ---------------------------------------------------------------------------

_COMPOUND_TO_OP = {
    "+=": "add", "-=": "sub", "*=": "mul", "/=": "div", "%=": "mod",
    "&=": "bit_and", "|=": "bit_or", "^=": "bit_xor",
    "<<=": "shl", ">>=": "shr",
}

def build_assign_expr(l_name: str, op_token: str, rhs_src: str):
    """
    Build the full expr tree for an assignment statement.

    For simple assignment (op_token == "="):
        expr = parse_expr(rhs_src)

    For compound assignment (op_token == "+=", etc.):
        expr = {"op": "add", "args": [{"name": l_name}, parse_expr(rhs_src)]}

    Returns None if rhs cannot be parsed.
    """
    rhs = parse_expr(rhs_src)
    if rhs is None:
        return None

    if op_token == "=":
        return rhs

    bin_op = _COMPOUND_TO_OP.get(op_token)
    if bin_op is None:
        return rhs  # unknown compound op — just return rhs

    # Split l_name on dot for field access (e.g. "a.x")
    if "." in l_name:
        parts = l_name.split(".", 1)
        lhs_node = {"op": "field", "args": [{"name": parts[0]}], "field": parts[1]}
    else:
        lhs_node = {"name": l_name}

    return {"op": bin_op, "args": [lhs_node, rhs]}