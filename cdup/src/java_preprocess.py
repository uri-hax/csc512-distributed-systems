"""Java-to-near-C preprocessor for the CDUP pipeline.

Transforms Java source into near-C so that :func:`parse_c_file` can process
it unchanged.

Strategy:
Java and C share brace structure, semicolons, most expression syntax, and
control-flow keywords. The preprocessor makes Java *look* like C by:

1. Stripping Java-only modifiers (public, private, static, final, ...)
2. Normalising the class block so it reads like a C struct
3. Mapping Java types to C equivalents (boolean→int, String→char*, etc.)
4. Desugaring 'new T(args)' → 'malloc(sizeof(T))'  /  'new T[n]' → 'malloc(n*sizeof(T))'
5. Aliasing I/O and Math to C stdlib names
6. Normalising main(String[] args) → int main()
7. Removing annotations (@Override, @SuppressWarnings, ...)
8. Removing import/package lines  (or keeping as comments so line numbers stay stable)
9. Handling enhanced for: 'for (T x : col) {}' → 'for (int _i=0; _i<col_len; _i++) {}'
10. Handling 'this.field' → 'field'
11. Mapping 'instanceof' → '__instanceof__'  (kept as identifier for expr parser)

What is NOT handled here (left for later phases):
- Generics: List<T>, Map<K,V> — angle brackets stripped, T left bare
- Interfaces / abstract methods — treated as empty function stubs
- Exception handling: try{} catch(T e){} — kept structurally, exception type dropped
- String methods: s.length(), s.charAt() — left as method calls, VM handles them
- Multi-dimensional generic arrays — simplified to pointer
"""

import re

# ---------------------------------------------------------------------------
# Token-level constants
# ---------------------------------------------------------------------------

_MODIFIERS = {
    "public", "private", "protected", "static", "final", "abstract",
    "volatile", "transient", "synchronized", "native", "strictfp", "default",
    "sealed", "non-sealed", "open",
}

# Java primitives → C type equivalents
_TYPE_MAP = {
    "boolean":  "int",
    "byte":     "char",
    "short":    "short",
    "String":   "char*",
    "Object":   "void*",
    "Integer":  "int",
    "Long":     "long",
    "Double":   "double",
    "Float":    "float",
    "Boolean":  "int",
    "Character":"char",
    "Byte":     "char",
    "Short":    "short",
    # Keep: int, char, float, double, long, void — already C
}

# Java stdlib → C stdlib aliases
_STDLIB_MAP = [
    # I/O
    (r'\bSystem\.out\.println\b',   'printf'),
    (r'\bSystem\.out\.print\b',     'printf'),
    (r'\bSystem\.err\.println\b',   'fprintf'),
    (r'\bSystem\.out\.printf\b',    'printf'),
    # Math
    (r'\bMath\.abs\b',              'abs'),
    (r'\bMath\.max\b',              'fmax'),
    (r'\bMath\.min\b',              'fmin'),
    (r'\bMath\.sqrt\b',             'sqrt'),
    (r'\bMath\.pow\b',              'pow'),
    (r'\bMath\.floor\b',            'floor'),
    (r'\bMath\.ceil\b',             'ceil'),
    (r'\bMath\.round\b',            'round'),
    (r'\bMath\.log\b',              'log'),
    (r'\bMath\.exp\b',              'exp'),
    (r'\bMath\.PI\b',               'M_PI'),
    (r'\bMath\.E\b',                'M_E'),
    # String utilities
    (r'\bString\.valueOf\b',        '__str_of'),
    (r'\bInteger\.parseInt\b',      'atoi'),
    (r'\bDouble\.parseDouble\b',    'atof'),
    # Arrays utility
    (r'\bArrays\.fill\b',           'memset_fill'),
    (r'\bArrays\.copyOf\b',         '__arrays_copyOf'),
    (r'\bArrays\.sort\b',           'qsort'),
    # Object methods — map to C-style names so the VM can handle them
    (r'\.length\(\)',               '_length()'),
    (r'\.size\(\)',                 '_size()'),
    (r'\.charAt\(',                 '_charAt('),
    (r'\.substring\(',              '_substring('),
    (r'\.equals\(',                 '_str_equals('),
    (r'\.compareTo\(',              '_str_compare('),
    (r'\.toCharArray\(\)',          '_toCharArray()'),
    (r'\.toString\(\)',             '_toString()'),
    (r'\.indexOf\(',                '_indexOf('),
    (r'\.contains\(',               '_contains('),
    (r'\.toLowerCase\(\)',          '_toLowerCase()'),
    (r'\.toUpperCase\(\)',          '_toUpperCase()'),
    (r'\.trim\(\)',                 '_trim()'),
    # null → NULL
    (r'\bnull\b',                   'NULL'),
    # true/false already valid C
    # instanceof → C-safe identifier
    (r'\binstanceof\b',             '__instanceof__'),
]

# ---------------------------------------------------------------------------
# Preprocessing passes
# ---------------------------------------------------------------------------

def _strip_annotations(src: str) -> str:
    """Remove @Annotation lines and inline annotations."""
    # Full-line annotations: @Override, @SuppressWarnings("..."), etc.
    src = re.sub(r'^\s*@\w+(?:\s*\(.*?\))?\s*$', '', src, flags=re.MULTILINE)
    # Inline annotations in parameter lists: @NotNull, @NonNull, etc.
    src = re.sub(r'@\w+(?:\s*\(.*?\))?\s*', '', src)
    return src


def _strip_imports_packages(src: str) -> str:
    """Remove import and package declarations."""
    src = re.sub(r'^\s*import\s+.*?;\s*$', '', src, flags=re.MULTILINE)
    src = re.sub(r'^\s*package\s+.*?;\s*$', '', src, flags=re.MULTILINE)
    return src


def _strip_modifiers(src: str) -> str:
    """Remove Java access and other modifiers from declarations.

    Processes word-by-word per line to avoid clobbering identifiers that
    happen to contain modifier strings (e.g. ``static`` in ``staticField``).

    Args:
        src: Java source string.

    Returns:
        Source string with modifier keywords removed.
    """
    result_lines = []
    for line in src.splitlines():
        stripped = line
        for mod in _MODIFIERS:
            # Only strip whole words at the beginning of a token sequence
            stripped = re.sub(rf'\b{re.escape(mod)}\b\s*', '', stripped)
        result_lines.append(stripped)
    return '\n'.join(result_lines)


def _map_types(src: str) -> str:
    """Replace Java-only types with C equivalents."""
    for java_type, c_type in _TYPE_MAP.items():
        src = re.sub(rf'\b{re.escape(java_type)}\b', c_type, src)
    return src


def _strip_generics(src: str) -> str:
    """Remove generic type parameters from Java source.

    ``List<Integer>`` → ``List``, ``Map<K,V>`` → ``Map``.  Uses a simple
    angle-bracket depth counter; only strips when ``<`` immediately follows an
    identifier (not a comparison operator).

    Args:
        src: Java source string.

    Returns:
        Source string with generic type parameters removed.
    """
    result = []
    i = 0
    n = len(src)
    while i < n:
        # Check for identifier immediately followed by <
        m = re.match(r'[A-Za-z_]\w*', src[i:])
        if m and i + m.end() < n and src[i + m.end()] == '<':
            # Peek ahead: is this really a generic or a comparison?
            # Heuristic: scan for matching > — if we find it before ; or =, it's generic
            j = i + m.end() + 1
            depth = 1
            while j < n and depth > 0:
                if src[j] == '<':
                    depth += 1
                elif src[j] == '>':
                    depth -= 1
                elif src[j] in (';', '\n', '=', '{'):
                    break  # not a generic
                j += 1
            if depth == 0:
                # It's a generic — emit just the base identifier
                result.append(m.group(0))
                i = j  # skip past >
                continue
        result.append(src[i])
        i += 1
    return ''.join(result)


def _desugar_length_field(src: str) -> str:
    """Rewrite ``.length`` field accesses to ``_arrlen()`` calls.

    ``s.length`` (no parentheses) → ``_arrlen(s)``.
    ``.length()`` with parentheses is handled separately by :func:`_map_stdlib`.

    Args:
        src: Java source string.

    Returns:
        Source string with ``.length`` rewritten.
    """
    # s.length (no parens) -> _arrlen(s).  .length() handled by _map_stdlib.
    return re.sub(
        r'([A-Za-z_]\w*)\.length(?!\s*[(])',
        lambda m: '_arrlen(' + m.group(1) + ')', src)


def _map_stdlib(src: str) -> str:
    """Apply stdlib alias substitutions."""
    for pattern, replacement in _STDLIB_MAP:
        src = re.sub(pattern, replacement, src)
    return src


def _desugar_new(src: str) -> str:
    """Rewrite Java ``new`` expressions to C ``malloc`` calls.

    Transformations applied:

    - ``new T[n]``   → ``malloc(n * sizeof(T))``
    - ``new T[n][m]`` → ``malloc(n * m * sizeof(T))``  (2-D, simplified)
    - ``new T(args)`` → ``malloc(sizeof(T))``  (constructor args dropped)

    Args:
        src: Java source string.

    Returns:
        Source string with ``new`` expressions replaced.
    """
    # Array allocation: new T[expr]  (possibly nested [expr][expr])
    def _replace_array_new(m):
        type_name = m.group(1)
        dims_str  = m.group(2)
        dims = re.findall(r'\[([^\]]+)\]', dims_str)
        if len(dims) == 1:
            return f'malloc({dims[0]} * sizeof({type_name}))'
        elif len(dims) == 2:
            return f'malloc({dims[0]} * {dims[1]} * sizeof({type_name}))'
        else:
            return f'malloc(sizeof({type_name}))'

    src = re.sub(
        r'\bnew\s+([A-Za-z_]\w*)(\s*\[[^\]]*\](?:\s*\[[^\]]*\])*)',
        _replace_array_new, src
    )
    # Object allocation: new T(args)
    # We must match the closing parenthesis properly to handle nested calls like `new T(f())`
    result = []
    i = 0
    n = len(src)
    while i < n:
        m = re.match(r'\bnew\s+([A-Za-z_]\w*)\s*\(', src[i:])
        if m:
            type_name = m.group(1)
            # Find matching closing parenthesis
            start_args = i + m.end() - 1
            depth = 0
            j = start_args
            while j < n:
                if src[j] == '(':
                    depth += 1
                elif src[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j < n:
                result.append(f'malloc(sizeof({type_name}))')
                i = j + 1
                continue
        result.append(src[i])
        i += 1
    src = ''.join(result)
    return src


def _normalise_main(src: str) -> str:
    """
    void main(String[] args)  →  int main()
    void main()               →  int main()
    """
    src = re.sub(
        r'\bvoid\s+(main)\s*\([^)]*\)',
        r'int \1()',
        src
    )
    return src


def _desugar_this(src: str) -> str:
    """this.field → field   (works well for simple single-class programs)"""
    src = re.sub(r'\bthis\.([A-Za-z_]\w*)', r'\1', src)
    return src


def _desugar_enhanced_for(src: str) -> str:
    """
    for (Type var : collection) {}
    →
    for (int _efi = 0; _efi < _length(collection); _efi++) {}

    The VM doesn't know collection length at parse time, but the structure
    is correct for scope/memory analysis. The VM handles the semantics.
    Note: 'collection' is preserved in r_names via _length(collection).
    """
    counter = [0]
    def _replace(m):
        typ  = m.group(1).strip()
        var  = m.group(2).strip()
        coll = m.group(3).strip()
        idx  = f'_efi{counter[0]}'
        counter[0] += 1
        # Emit a synthetic decl for var so memory extraction picks it up
        # We use a special prefix comment trick: emit the decl inline
        # The leading `{var} = {coll}[{idx}];` goes in the loop body placeholder
        # We can't inject into the child block here, so we store it in a side-channel.
        # Simplest correct approach: rewrite as index-based loop, var decl goes
        # into the block as first stmt — but we can't insert into {} here.
        # Compromise: use a zero-semicolons for-header that the statement parser
        # will classify as loop_head, and var becomes a memory slot via
        # a special "enhanced_for_var" annotation injected as a comment-stmt.
        return (
            f'/* __efor_var__ {typ} {var} {coll} */\n'
            f'for (int {idx} = 0; {idx} < _length({coll}); {idx}++)'
        )
    src = re.sub(
        r'\bfor\s*\(\s*([A-Za-z_]\w*(?:\[\])*)\s+([A-Za-z_]\w*)\s*:\s*([^)]+)\)',
        _replace, src
    )
    return src


def _desugar_try_catch(src: str) -> str:
    """
    Simplify: catch (ExceptionType e) {}  →  catch (void* e) {}
    The exception type becomes 'void*' so the brace scanner sees valid C.
    """
    src = re.sub(
        r'\bcatch\s*\(\s*([A-Za-z_]\w*(?:\s*\|\s*[A-Za-z_]\w*)*)\s+([A-Za-z_]\w*)\s*\)',
        lambda m: f'catch (void* {m.group(2).strip()})',
        src
    )
    # 'finally' is not a C keyword — rename so the classifier sees it as a branch
    src = re.sub(r'\bfinally\s*(?=\{)', 'else /* finally */', src)
    return src


def _desugar_class_header(src: str) -> str:
    """
    class Foo extends Bar implements Baz, Qux {
    →
    struct Foo {

    The 'struct' keyword lets _get_seg_type classify it correctly.
    We keep the class name. extends/implements clauses are dropped but
    we could store them as metadata in a future pass.
    """
    src = re.sub(
        r'\bclass\s+([A-Za-z_]\w*)(?:\s+extends\s+[A-Za-z_]\w*)?(?:\s+implements\s+[A-Za-z_$][\w$,\s]*?)?\s*(?=\{)',
        r'struct \1 ',
        src
    )
    # interface → struct (methods become function stubs)
    src = re.sub(
        r'\binterface\s+([A-Za-z_]\w*)(?:\s+extends\s+[A-Za-z_$][\w$,\s]*)?\s*(?=\{)',
        r'struct \1 ',
        src
    )
    return src


def _desugar_varargs(src: str) -> str:
    """int... args → int* args"""
    src = re.sub(r'\b(\w+)\.\.\.\s*(\w+)', r'\1* \2', src)
    return src


def _desugar_array_types(src: str) -> str:
    """
    Convert Java array types to C equivalents, handling two cases:

    1. Parameter / declaration WITHOUT brace initializer:
         int[] arr      ->  int* arr      (pointer — caller owns allocation)
         int[][] mat    ->  int** mat

    2. Local declaration WITH brace initializer (key Java idiom):
         int[] x = {10}        ->  int x[1] = {10}
         int[] nums = {1,2,3}  ->  int nums[3] = {1, 2, 3}
         int[][] pp = {y}      ->  int* pp[1] = {y}

       This fires the C parser array-brace-init path so the VM allocates a
       real heap array — exactly what Java pass-by-reference arrays need.
       Element count is inferred by counting top-level commas in the braces.
    """
    lines = src.splitlines()
    result = []
    _BRACE_DECL = re.compile(
        r'^(\s*)'                           # leading whitespace
        r'([A-Za-z_]\w*)'                   # base type
        r'(\**)(\[\](?:\[\])?)'          # existing stars + [] or [][]
        r'\s+([A-Za-z_]\w*)'               # variable name
        r'\s*=\s*\{([^}]*)\}'            # = { ... }
        r'\s*;?\s*$'                        # optional semicolon
    )
    for line in lines:
        m = _BRACE_DECL.match(line)
        if m:
            indent    = m.group(1)
            base_type = m.group(2)
            stars     = m.group(3)
            brackets  = m.group(4)
            var_name  = m.group(5)
            contents  = m.group(6).strip()
            depth = 0
            count = 1 if contents else 0
            for ch in contents:
                if ch == "{": depth += 1
                elif ch == "}": depth -= 1
                elif ch == "," and depth == 0: count += 1
            if "[][]" in brackets:
                result.append(
                    f'{indent}{base_type}{stars}* {var_name}[{count}] = {{{contents}}};')
            else:
                result.append(
                    f'{indent}{base_type}{stars} {var_name}[{count}] = {{{contents}}};')
            continue
        line = re.sub(r'\b([A-Za-z_]\w*)\[\]\[\]', r'\1**', line)
        line = re.sub(r'\b([A-Za-z_]\w*)\[\]',     r'\1*',  line)
        result.append(line)
    return '\n'.join(result)


def _desugar_string_concat(src: str) -> str:
    """
    Convert Java System.out.println/print with + concatenation to C printf.

    System.out.println("x=" + val + " y=" + other)
    ->  printf("x=%s y=%s\n", val, other)

    String literal segments are embedded directly in the format string.
    Non-literal segments (variables, array indices) become %s arguments.
    println adds \n, print does not.

    Must run BEFORE _map_stdlib so the System.out.println pattern is intact.
    """
    def _split_concat(s):
        parts, current, depth, in_str = [], "", 0, False
        i = 0
        while i < len(s):
            c = s[i]
            if c == '"' and not in_str:
                in_str = True; current += c
            elif c == '"' and in_str:
                in_str = False; current += c
            elif in_str:
                if c == '\\': current += c + (s[i+1] if i+1 < len(s) else ''); i += 2; continue
                else: current += c
            elif c in '([': depth += 1; current += c
            elif c in ')]': depth -= 1; current += c
            elif c == '+' and depth == 0:
                if current.strip(): parts.append(current.strip())
                current = ""
            else: current += c
            i += 1
        if current.strip(): parts.append(current.strip())
        return parts

    def _convert(m):
        is_println = 'println' in m.group(1)
        parts = _split_concat(m.group(2).strip())
        fmt, varargs = "", []
        for p in parts:
            p = p.strip()
            if p.startswith('"') and p.endswith('"'):
                fmt += p[1:-1]      # string literal: embed directly
            else:
                fmt += "%s"
                varargs.append(p)
        if is_println:
            fmt += "\\n"
        if varargs:
            return 'printf("' + fmt + '", ' + ', '.join(varargs) + ')'
        else:
            return 'printf("' + fmt + '")'

    return re.sub(
        r'\bSystem\.out\.(print(?:ln)?)\s*\((.+?)\)(?=\s*;)',
        _convert, src, flags=re.DOTALL
    )


def _fixup_constructor(src: str) -> str:
    """
    A constructor looks like:  ClassName(params) {}
    After modifier stripping it has no return type.  Add 'void' so the
    classifier sees it as a func_decl.
    We detect: identifier immediately followed by ( at the start of a trimmed line,
    where the identifier matches a known class name.
    We can't know class names here (that's a second pass), so we use a heuristic:
    if a line after stripping starts with Identifier( and is not a call statement
    (i.e. it has the {} block marker), treat as void Identifier(...) {}.
    This pass runs AFTER class-header rewriting, so struct names are available
    from the already-processed text.
    """
    # Find all struct names in the (already-processed) source
    class_names = set(re.findall(r'\bstruct\s+([A-Za-z_]\w*)', src))
    if not class_names:
        return src

    def _fix_line(m):
        name = m.group(1)
        rest = m.group(2)
        if name in class_names:
            return f'void {name}{rest}'
        return m.group(0)

    src = re.sub(
        r'^(\s*)([A-Z][A-Za-z_]\w*)\s*(\([^{;]*\)\s*(?:\{|$))',
        lambda m: m.group(1) + _fix_line(re.match(r'([A-Z][A-Za-z_]\w*)(.*)', m.group(2) + m.group(3))),
        src, flags=re.MULTILINE
    )
    return src


def _add_return_to_main(src: str) -> str:
    """
    If main() has no return statement, add 'return 0;' before the final
    closing brace.  This is a best-effort pass that just ensures the IR has
    a clean return from main.  The parse pipeline already handles this for C
    via the classifier, but being explicit helps the VM.
    """
    # We don't have the AST here so we skip this — parse.py will handle it
    # via the _extract_constants path. The Java VM handler adds return 0 too.
    return src


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _desugar_char_array_init(src: str) -> str:
    """
    char x[] = {'a', 'b', '\\0'}  ->  int x[] = {97, 98, 0}

    Converts char literal brace initializers to integer values so the
    VM's existing array brace-init path can handle them correctly.
    Only targets declarations that have a brace initializer with char literals.
    """
    import ast

    def _char_to_int(c: str) -> int:
        try:
            return ord(ast.literal_eval(c))
        except Exception:
            return 0

    def _convert_init(m):
        pre     = m.group(1)   # everything before the braces
        content = m.group(2)   # contents inside {}
        # Check if this looks like char literals (contains ' markers)
        if "\'" not in content and "\\'" not in content:
            return m.group(0)
        # Split on commas (simple split is fine for char literals)
        parts = [p.strip() for p in content.split(",")]
        ints = []
        for p in parts:
            p = p.strip()
            if p.startswith("'") and p.endswith("'"):
                inner = p[1:-1]
                if inner == "\\0" or inner == "\\\\0":
                    ints.append("0")
                elif inner.startswith("\\\\"):
                    try: ints.append(str(ord(ast.literal_eval("\'" + inner + "\'"))))
                    except: ints.append("0")
                else:
                    try: ints.append(str(ord(inner)))
                    except: ints.append("0")
            else:
                ints.append(p)
        # Replace char type with int in the declaration prefix
        new_pre = re.sub(r'\bchar\b', 'int', pre)
        return new_pre + "{" + ", ".join(ints) + "}"

    return re.sub(
        r'((?:char|int)\s+\w+\s*(?:\[[^\]]*\])?\s*=\s*)\{([^}]*)\}',
        _convert_init, src
    )


def _desugar_double_index(src: str) -> str:
    """
    Java double-index write: pp[0][0] = val  ->  *(pp[0]) = val
    This lets the VM handle it as a single deref-write into a heap pointer.

    Also rewrites single-element pointer array decls:
    int* pp[1] = {y}  ->  int** pp = &y
    These are Java's simulation of pointer-to-pointer (int[][] pp = {y}).
    """
    # Rewrite double-index assignments: name[idx1][idx2] = rhs -> *(name[idx1]) = rhs
    src = re.sub(
        r'\b([A-Za-z_]\w*)\[(\d+)\]\[(\d+)\]\s*=\s*([^;\n]+);',
        lambda m: f'*(({m.group(1)})[{m.group(2)}]) = {m.group(4).strip()};',
        src
    )
    # Rewrite single-element pointer array decls: type* name[1] = {var} -> type** name = &var
    src = re.sub(
        r'([A-Za-z_]\w*)\*\s+([A-Za-z_]\w*)\[1\]\s*=\s*\{([A-Za-z_]\w*)\}',
        lambda m: f'{m.group(1)}** {m.group(2)} = &{m.group(3)}',
        src
    )
    return src

def preprocess_java(src: str) -> str:
    """
    Transform a Java source string into near-C source suitable for parse_c_file.

    Passes are applied in dependency order:
      annotations → imports/packages → generics → class headers → modifiers
      → types → stdlib → new → main → this → enhanced-for → try/catch
      → array types → varargs → constructors
    """
    src = _strip_annotations(src)
    src = _strip_imports_packages(src)
    src = _strip_generics(src)
    src = _desugar_class_header(src)    # before modifier strip (uses 'class' keyword)
    src = _strip_modifiers(src)
    src = _map_types(src)
    src = _desugar_string_concat(src)  # before _map_stdlib (needs System.out.println intact)
    src = _desugar_length_field(src)    # before _map_stdlib (handles .length field access)
    src = _map_stdlib(src)
    src = _desugar_new(src)
    src = _normalise_main(src)
    src = _desugar_this(src)
    src = _desugar_enhanced_for(src)
    src = _desugar_try_catch(src)
    src = _desugar_array_types(src)
    src = _desugar_char_array_init(src)  # after array types (needs [N] form)
    src = _desugar_double_index(src)      # after array types (needs type info)
    src = _desugar_varargs(src)
    src = _fixup_constructor(src)
    return src