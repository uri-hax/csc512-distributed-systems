import json
import re
import hashlib
from collections import defaultdict

def _normalize_stmt(stmt: str) -> str:
    return " ".join(stmt.split()).lower()

def _tokenize(stmt: str) -> list:
    token_pattern = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"|[A-Za-z_]\w*|\d+\.\d+|\d+|[^\s\w]')
    return token_pattern.findall(stmt)

C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "inline",
    "int", "long", "register", "restrict", "return", "short", "signed", "sizeof",
    "static", "struct", "switch", "typedef", "union", "unsigned", "void",
    "volatile", "while", "NULL", "true", "false"
}

def _normalize_stmt_type2(stmt: str) -> str:
    tokens = _tokenize(stmt)
    identifier_map = {}
    result_tokens = []
    for token in tokens:
        if token.startswith('"'):
            result_tokens.append("STR_LIT")
        elif re.fullmatch(r'\d+\.\d+|\d+', token):
            result_tokens.append("NUM_LIT")
        elif token in C_KEYWORDS:
            result_tokens.append(token)
        elif re.fullmatch(r'[A-Za-z_]\w*', token):
            if token not in identifier_map:
                identifier_map[token] = f"VAR_{len(identifier_map)}"
            result_tokens.append(identifier_map[token])
        else:
            result_tokens.append(token)
    return " ".join(result_tokens)

def detect_clones(json_str: str, type_2_norm: bool = False, maximal: bool = True,
                  min_length: int = 2, max_freq: int = 0,
                  filter_overlaps: bool = True, include_comments: bool = False,
                  include_includes: bool = False, include_macros: bool = False) -> str:
    """
    Detect Type I or Type II clones depending on type_2_norm flag.
    - type_2_norm=False (default): Type I — exact match after whitespace normalization
    - type_2_norm=True:            Type II — structural match after identifier abstraction,
                                   excluding pairs already caught by Type I
    - maximal=True (default):      Filter out clone classes fully subsumed by longer ones
    - min_length=2 (default):      Minimum clone sequence length to report
    - max_freq=0 (default):        Skip statements appearing more than this many times
                                   across all segments (0 = no limit). Useful for filtering
                                   common boilerplate like 'return 0;' that would otherwise
                                   produce massive inverted index entries and slow things down.
    """
    data = json.loads(json_str)
    segments = data["segments"]
    seg_by_id = {seg["id"]: seg for seg in segments} 
    clone_type = "II" if type_2_norm else "I"

    def _is_comment(stmt: str) -> bool:
        return stmt.startswith("//") or stmt.startswith("/*")

    def _is_include(stmt: str) -> bool:
        return stmt.startswith("#") and stmt[1:].lstrip().startswith("include")

    def _is_macro(stmt: str) -> bool:
        return stmt.startswith("#") and not stmt[1:].lstrip().startswith("include")

    def _should_skip(stmt: str) -> bool:
        if not include_comments and _is_comment(stmt):
            return True
        if not include_includes and _is_include(stmt):
            return True
        if not include_macros and _is_macro(stmt):
            return True
        return False

    children = defaultdict(list)
    for seg in segments:
        if seg["id"] != 0 and seg["parent"] != seg["id"]:
            children[seg["parent"]].append(seg["id"])
    for p in children:
        children[p].sort()

    seg_hashes = {}
    global_hash_to_id = {}

    def get_block_type_id(seg_id):
        if seg_id in seg_hashes:
            return seg_hashes[seg_id]
            
        seg = seg_by_id[seg_id]
        child_list = children.get(seg_id, [])
        
        hashed_stmts = []
        child_idx = 0
        for stmt in seg["statements"]:
            if _should_skip(stmt):
                continue

            if type_2_norm:
                base_stmt = _normalize_stmt_type2(stmt)
                target = "{ }" if "{ }" in base_stmt else "{}"
            else:
                base_stmt = _normalize_stmt(stmt)
                target = "{}"

            while target in base_stmt and child_idx < len(child_list):
                c_type_id = get_block_type_id(child_list[child_idx])
                base_stmt = base_stmt.replace(target, f"<BLOCK_TYPE_{c_type_id}>", 1)
                child_idx += 1
            hashed_stmts.append(base_stmt)
            
        combined = " ".join(hashed_stmts)
        h_full = hashlib.sha256(combined.encode()).hexdigest()
        if h_full not in global_hash_to_id:
            global_hash_to_id[h_full] = len(global_hash_to_id) + 1
        block_type_id = global_hash_to_id[h_full]
        seg_hashes[seg_id] = block_type_id
        return block_type_id
    
    for seg in segments:
        get_block_type_id(seg["id"])

    flat = []
    for seg in segments:
        child_list = children.get(seg["id"], [])
        child_idx = 0
        for stmt_idx, stmt in enumerate(seg["statements"]):
            if _should_skip(stmt):
                continue
            norm1 = _normalize_stmt(stmt)
            norm = _normalize_stmt_type2(stmt) if type_2_norm else norm1

            while "{}" in norm1 and child_idx < len(child_list):
                c_type_id = seg_hashes[child_list[child_idx]]
                replacement = f"<BLOCK_TYPE_{c_type_id}>"
                norm1 = norm1.replace("{}", replacement, 1)
                
                if type_2_norm:

                    if "{ }" in norm:
                        norm = norm.replace("{ }", replacement, 1)
                    else:
                        norm = norm.replace("{}", replacement, 1)
                else:
                    norm = norm1
                    
                child_idx += 1
                
            flat.append((seg["id"], stmt_idx, norm, norm1))
        flat.append(None)

    inverted_index = defaultdict(list)
    for flat_idx, entry in enumerate(flat):
        if entry is not None:
            seg_id, stmt_idx, norm, norm1 = entry
            inverted_index[norm].append(flat_idx)

    if max_freq > 0:
        inverted_index = {k: v for k, v in inverted_index.items() if len(v) <= max_freq}

    active_clones = {}
    completed_clones = []

    for current_idx, entry in enumerate(flat):
        if entry is None:
            for offset, length in active_clones.items():
                if length >= min_length:
                    start_a = current_idx - length
                    start_b = start_a + offset
                    completed_clones.append((start_a, start_b, length))
            active_clones = {}
            continue
        _, _, norm, _ = entry
        matches = inverted_index.get(norm, [])
        current_offsets = set()
        for match_idx in matches:
            if match_idx <= current_idx:
                continue
            if flat[match_idx] is None:
                continue
            offset = match_idx - current_idx
            current_offsets.add(offset)
            if offset in active_clones:
                active_clones[offset] += 1
            else:
                active_clones[offset] = 1
        offsets_to_remove = []
        for offset, length in active_clones.items():
            if offset not in current_offsets:
                if length >= min_length:
                    start_a = current_idx - length
                    start_b = start_a + offset
                    completed_clones.append((start_a, start_b, length))
                offsets_to_remove.append(offset)
        for offset in offsets_to_remove:
            del active_clones[offset]
    for offset, length in active_clones.items():
        if length >= min_length:
            start_a = len(flat) - length
            start_b = start_a + offset
            completed_clones.append((start_a, start_b, length))

    def flat_range_to_occurrence(start_flat, length):
        seg_id = flat[start_flat][0]
        start_stmt = flat[start_flat][1]
        end_stmt = flat[start_flat + length - 1][1]
        return (seg_id, start_stmt, end_stmt)

    clone_classes = defaultdict(set)
    for start_a, start_b, length in completed_clones:
        content_tuple = tuple(
            flat[i][2] for i in range(start_a, start_a + length) if flat[i] is not None
        )
        clone_classes[content_tuple].add(flat_range_to_occurrence(start_a, length))
        clone_classes[content_tuple].add(flat_range_to_occurrence(start_b, length))

    if type_2_norm:
        expanded_classes = {}
        type1_classes = {}

        for content_tuple, occurrences in clone_classes.items():
            norm1_groups = defaultdict(set)
            for occ in occurrences:
                seg_id, start_stmt, end_stmt = occ
                norm1 = tuple(
                    flat[idx][3] for idx in range(len(flat)) 
                    if flat[idx] is not None and flat[idx][0] == seg_id and flat[idx][1] >= start_stmt and flat[idx][1] <= end_stmt
                )
                norm1_groups[norm1].add(occ)

            for norm1_tuple, norm1_occs in norm1_groups.items():
                if len(norm1_occs) >= 2:
                    if norm1_tuple not in type1_classes:
                        type1_classes[norm1_tuple] = set()
                    type1_classes[norm1_tuple].update(norm1_occs)

            if len(occurrences) >= 2:
                expanded_classes[content_tuple] = occurrences

        clone_classes = expanded_classes
    else:
        type1_classes = {}

    def get_hashed_original_stmts(seg_id, start_idx, end_idx):
        original = seg_by_id[seg_id]["statements"]
        child_list = children.get(seg_id, [])
        child_offset = 0
        for i in range(start_idx):
            child_offset += original[i].count("{}") 
        hashed_stmts = []
        current_child_idx = child_offset
        for i in range(start_idx, end_idx + 1):
            stmt = original[i]
            if _should_skip(stmt):
                continue
            while "{}" in stmt and current_child_idx < len(child_list):
                c_type_id = seg_hashes[child_list[current_child_idx]]
                stmt = stmt.replace("{}", f"<BLOCK_TYPE_{c_type_id}>", 1)
                current_child_idx += 1
            hashed_stmts.append(stmt) 
        return hashed_stmts

    clone_class_list = []
    for norm1_tuple, occurrences in sorted(type1_classes.items(), key=lambda x: len(x[1]), reverse=True):
        first_seg_id, first_start, first_end = sorted(occurrences)[0]
        hashed_stmts = get_hashed_original_stmts(first_seg_id, first_start, first_end)
        
        clone_class_list.append({
            "id": 0,
            "clone_type": "I",
            "length": len(norm1_tuple),
            "statements": hashed_stmts,
            "occurrences": [
                {"seg_id": s, "start_stmt_idx": st, "end_stmt_idx": en}
                for s, st, en in sorted(occurrences)
            ]
        })

    for clone_id, (content_tuple, occurrences) in enumerate(
        sorted(clone_classes.items(), key=lambda x: len(x[1]), reverse=True), 1
    ):
        first_seg_id, first_start, first_end = sorted(occurrences)[0]
        actual_clone_type = "II" if type_2_norm else "I"
        hashed_stmts = get_hashed_original_stmts(first_seg_id, first_start, first_end)

        entry = {
            "id": clone_id,
            "clone_type": actual_clone_type,
            "length": len(content_tuple),
            "statements": hashed_stmts,
            "occurrences": [
                {
                    "seg_id": seg_id,
                    "start_stmt_idx": start_stmt,
                    "end_stmt_idx": end_stmt
                }
                for seg_id, start_stmt, end_stmt in sorted(occurrences)
            ]
        }
        if actual_clone_type == "II":
            entry["normalized"] = list(content_tuple)

        clone_class_list.append(entry)

    if maximal:
        covered_by_type = {"I": set(), "II": set()}
        sorted_by_length = sorted(clone_class_list, key=lambda x: x["length"], reverse=True)
        final_classes = []
        for clone in sorted_by_length:
            ct = clone["clone_type"]
            eligible_covered = covered_by_type["I"] if ct == "I" else (
                covered_by_type["I"] | covered_by_type["II"]
            )
            occs = [(o["seg_id"], o["start_stmt_idx"], o["end_stmt_idx"]) for o in clone["occurrences"]]
            if all(
                any(
                    seg == cseg and cs <= start and end <= ce
                    for (cseg, cs, ce) in eligible_covered
                )
                for (seg, start, end) in occs
            ):
                continue
            covered_by_type[ct].update(occs)
            final_classes.append(clone)
        for i, clone in enumerate(final_classes, 1):
            clone["id"] = i
        clone_class_list = final_classes

    if filter_overlaps:
        def ranges_overlap(a_start, a_end, b_start, b_end):
            return a_start <= b_end and b_start <= a_end

        final_classes = []
        for clone in clone_class_list:
            occs = [(o["seg_id"], o["start_stmt_idx"], o["end_stmt_idx"])
                    for o in clone["occurrences"]]
            all_same_seg = len(set(seg for seg, _, _ in occs)) == 1
            if all_same_seg:
                has_overlap = any(
                    ranges_overlap(s1, e1, s2, e2)
                    for i, (_, s1, e1) in enumerate(occs)
                    for (_, s2, e2) in occs[i+1:]
                )
                if has_overlap:
                    continue
            final_classes.append(clone)
        for i, clone in enumerate(final_classes, 1):
            clone["id"] = i
        clone_class_list = final_classes

    result = {"clone_classes": clone_class_list}
    return json.dumps(result, indent=2)