import json

def _pair_opn_cls(cls_open_sequence: list, open_idx: list, cls_idx: list) -> list:
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

    # Build the root segment by removing all top-level {} blocks from file_str
    root_seg = file_str
    for i in sorted(range(len(pairs)), key=lambda i: pairs[i][0], reverse=True):
        if parents[i] == i:  # root-level segment
            root_seg = root_seg[:pairs[i][0]] + root_seg[pairs[i][1]:]

    return [root_seg] + segs

def _parse_statements(seg: str, include_comments: bool = False, include_includes: bool = False, include_macros: bool = False) -> list:
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
        # Handle string literals
        if seg[i] == '"' and depth == 0:
            current += seg[i]
            i += 1
            while i < len(seg):
                current += seg[i]
                if seg[i] == '\\':  # skip escaped characters
                    i += 1
                    if i < len(seg):
                        current += seg[i]
                elif seg[i] == '"':
                    i += 1
                    break
                i += 1
        # Handle char literals — skip content so '{' '(' etc. don't confuse depth tracking
        elif seg[i] == "'" and depth == 0:
            current += seg[i]
            i += 1
            while i < len(seg):
                current += seg[i]
                if seg[i] == '\\':  # skip escaped character e.g. '\n', '\\'
                    i += 1
                    if i < len(seg):
                        current += seg[i]
                elif seg[i] == "'":
                    i += 1
                    break
                i += 1
        # Handle single line comments
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
        # Handle multi-line comments
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

def _error_handling(bcos, pcos, boidx, bcidx, poidx, pcidx) -> None:
    if not bcos:
        return  # no braces is fine (e.g. header-only file)
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

def _get_seg_type(header: str) -> str:
    """Determine segment type from its header statement in the parent."""
    if header is None:
        return "root"
    h = header.strip()
    for keyword in ["for ", "while ", "if ", "else", "switch ", "do{"]:
        if h.startswith(keyword):
            return "logic"
    if h.startswith("struct "):
        return "struct"
    return "function"

def parse_c_file(file_str: str, include_comments: bool = False, include_includes: bool = False, include_macros: bool = False) -> str:

    # --- Character scanner: comment- and string-aware ---
    # Skips over string literals, line comments, and block comments so that
    # braces/parens inside them are never counted.
    b_cls_open_sequence = []
    p_cls_open_sequence = []
    open_bidx = []
    cls_bidx = []
    open_pidx = []
    cls_pidx = []

    i = 0
    in_line_comment = False
    in_block_comment = False
    in_string = False
    in_char_literal = False

    while i < len(file_str):
        c = file_str[i]

        # --- Exit states ---
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
                i += 2  # skip escaped character (and the char after it)
            elif c == '"':
                in_string = False
                i += 1
            else:
                i += 1
            continue

        if in_char_literal:
            if c == '\\':
                i += 2  # skip escaped character e.g. '\n', '\\'
            elif c == "'":
                in_char_literal = False
                i += 1
            else:
                i += 1
            continue

        # --- Enter states (check two-char tokens before single-char) ---
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

        # --- Normal character scanning ---
        if c == '{':
            b_cls_open_sequence.append(1)
            open_bidx.append(i + 1)
        elif c == '}':
            b_cls_open_sequence.append(0)
            cls_bidx.append(i)
        elif c == '(':
            p_cls_open_sequence.append(1)
            open_pidx.append(i + 1)
        elif c == ')':
            p_cls_open_sequence.append(0)
            cls_pidx.append(i)

        i += 1

    # Error handling — raises ValueError instead of calling exit(1)
    _error_handling(
        b_cls_open_sequence,
        p_cls_open_sequence,
        open_bidx,
        cls_bidx,
        open_pidx,
        cls_pidx
    )

    # Get the pairs for () and {}
    bpairs = _pair_opn_cls(b_cls_open_sequence, open_bidx, cls_bidx)
    ppairs = _pair_opn_cls(p_cls_open_sequence, open_pidx, cls_pidx)

    # Sort pairs in order of opening index
    bpairs = sorted(bpairs, key=lambda row: row[0])
    ppairs = sorted(ppairs, key=lambda row: row[0])

    # Find nested pairs
    bparents = _find_nested_pairs(b_cls_open_sequence)
    pparents = _find_nested_pairs(p_cls_open_sequence)

    # Parse each code segment
    bsegs = _parse_code_segs(file_str, bpairs, bparents)
    psegs = _parse_code_segs(file_str, ppairs, pparents)

    # Align parents array with new root segment
    bparents = [0 if bparents[i] == i else bparents[i] + 1 for i in range(len(bparents))]
    pparents = [0 if pparents[i] == i else pparents[i] + 1 for i in range(len(pparents))]
    bparents = [0] + bparents
    pparents = [0] + pparents

    # Cleaning the segments
    cleaned_segs = []
    for i in range(len(bsegs)):
        seg = bsegs[i]
        lines = seg.splitlines()
        seg = ""
        for line in lines:
            clean_line = line.strip()
            if clean_line != "":
                seg = seg + clean_line + "\n"
        seg = seg[0 : len(seg)-1]
        cleaned_segs.append(seg)

    # Extracting statements
    bseg_stmnts = []
    for i in range(len(cleaned_segs)):
        bseg_stmnts.append(_parse_statements(cleaned_segs[i], include_comments, include_includes, include_macros))

    # Build header info for each segment
    children_of = {}
    for seg_id in range(len(bsegs)):
        parent_id = bparents[seg_id]
        if seg_id == 0:
            continue
        if parent_id not in children_of:
            children_of[parent_id] = []
        children_of[parent_id].append(seg_id)

    def get_block_statements(stmnts):
        return [(idx, s) for idx, s in enumerate(stmnts) if "{}" in s]

    seg_headers = {0: (None, None)}
    for parent_id, child_ids in children_of.items():
        block_stmnts = get_block_statements(bseg_stmnts[parent_id])
        for i, child_id in enumerate(child_ids):
            if i < len(block_stmnts):
                stmt_idx, stmt_str = block_stmnts[i]
                seg_headers[child_id] = (stmt_str, stmt_idx)
            else:
                seg_headers[child_id] = (None, None)

    # Build the final segments list
    segments = []
    for seg_id in range(len(bsegs)):
        header_str, header_idx = seg_headers.get(seg_id, (None, None))
        seg_type = _get_seg_type(header_str)
        segments.append({
            "id": seg_id,
            "parent": bparents[seg_id],
            "type": seg_type,
            "header": header_str,
            "header_idx": header_idx,
            "statements": bseg_stmnts[seg_id]
        })

    result = {"segments": segments}
    return json.dumps(result, indent=2)