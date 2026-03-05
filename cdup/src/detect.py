"""Clone detection engine for the CDUP pipeline.

Implements four clone-detection strategies over the parsed IR JSON:

- **Type I**   — Exact clones (whitespace-normalised match).
- **Type II**  — Structural clones (identifier-abstracted match).
- **Type III** — Near-miss clones (sliding-window sequence similarity).
- **Type IV**  — Semantic clones (abstract structural fingerprint match).

Entry points:
    :func:`detect_clones` — Type I / II detection.
    :func:`detect_type3`  — Type III near-miss detection.
    :func:`detect_type4`  — Type IV semantic detection.
"""

import json
import re
import hashlib
from collections import defaultdict
from difflib import SequenceMatcher

def _normalize_stmt(stmt: str) -> str:
    """Normalise a statement for Type I (exact) clone comparison.

    Collapses all internal whitespace and lower-cases the result.

    Args:
        stmt: Raw statement string.

    Returns:
        Whitespace-collapsed, lower-cased statement string.
    """
    return " ".join(stmt.split()).lower()

def _tokenize(stmt: str) -> list:
    """Tokenise a statement string into identifiers, numbers, strings, and operators.

    Args:
        stmt: Raw statement string to tokenise.

    Returns:
        List of token strings in source order.
    """
    token_pattern = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"|[A-Za-z_]\w*|\d+\.\d+|\d+|[^\s\w]')
    return token_pattern.findall(stmt)

_C_KEYWORDS: set = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "inline",
    "int", "long", "register", "restrict", "return", "short", "signed", "sizeof",
    "static", "struct", "switch", "typedef", "union", "unsigned", "void",
    "volatile", "while", "NULL", "true", "false"
}

# Unified keyword set for cross-language Type II/III normalization.
# Both C and Java keywords are treated as structural tokens (not abstracted).
_KEYWORDS: set = _C_KEYWORDS | {
    "boolean", "byte", "class", "extends", "final", "implements", "import",
    "instanceof", "interface", "new", "package", "private", "protected",
    "public", "super", "this", "throw", "throws", "try", "catch", "finally",
    "abstract", "assert", "native", "synchronized", "transient", "strictfp",
}

def _normalize_stmt_type2(stmt: str) -> str:
    """Normalise a statement for Type II (structural) clone comparison.

    String literals become ``STR_LIT``, numeric literals become ``NUM_LIT``,
    and user-defined identifiers are renamed to positional ``VAR_N`` tokens
    while C/Java keywords are preserved as structural anchors.

    Args:
        stmt: Raw statement string.

    Returns:
        Normalised token string suitable for Type II matching.
    """
    tokens = _tokenize(stmt)
    identifier_map = {}
    result_tokens = []
    for token in tokens:
        if token.startswith('"'):
            result_tokens.append("STR_LIT")
        elif re.fullmatch(r'\d+\.\d+|\d+', token):
            result_tokens.append("NUM_LIT")
        elif token in _C_KEYWORDS:
            result_tokens.append(token)
        elif re.fullmatch(r'[A-Za-z_]\w*', token):
            if token not in identifier_map:
                identifier_map[token] = f"VAR_{len(identifier_map)}"
            result_tokens.append(identifier_map[token])
        else:
            result_tokens.append(token)
    return " ".join(result_tokens)

def _get_raw(stmt) -> str:
    """Extract raw string from a stmt, whether it is a classified dict or a plain string."""
    if isinstance(stmt, dict):
        return stmt.get("raw", "")
    return stmt

def detect_clones(json_str: str, type_2_norm: bool = False, maximal: bool = True,
                  min_length: int = 2, max_freq: int = 0,
                  filter_overlaps: bool = True) -> str:
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

    Filtering of comments, includes, and macros is handled at parse time.
    detect_clones operates on already-filtered statements.
    """
    data = json.loads(json_str)
    segments = data["segments"]
    seg_by_id = {seg["id"]: seg for seg in segments}

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
        for stmt in seg["stmts"]:
            raw = _get_raw(stmt)
            if type_2_norm:
                base_stmt = _normalize_stmt_type2(raw)
                target = "{ }" if "{ }" in base_stmt else "{}"
            else:
                base_stmt = _normalize_stmt(raw)
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
        for stmt_idx, stmt in enumerate(seg["stmts"]):
            raw = _get_raw(stmt)
            norm1 = _normalize_stmt(raw)
            norm = _normalize_stmt_type2(raw) if type_2_norm else norm1

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
                    if flat[idx] is not None and flat[idx][0] == seg_id
                    and flat[idx][1] >= start_stmt and flat[idx][1] <= end_stmt
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
        original = seg_by_id[seg_id]["stmts"]
        child_list = children.get(seg_id, [])
        # Count how many {} appear in statements before start_idx to find child offset
        child_offset = sum(_get_raw(original[i]).count("{}") for i in range(start_idx))
        hashed_stmts = []
        current_child_idx = child_offset
        for i in range(start_idx, end_idx + 1):
            stmt = _get_raw(original[i])
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
                {"seg_id": seg_id, "start_stmt_idx": start_stmt, "end_stmt_idx": end_stmt}
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
                any(seg == cseg and cs <= start and end <= ce for (cseg, cs, ce) in eligible_covered)
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
            occs = [(o["seg_id"], o["start_stmt_idx"], o["end_stmt_idx"]) for o in clone["occurrences"]]
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

    return json.dumps({"clone_classes": clone_class_list}, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE III — Near-miss clone detection
#
# Reuses the existing Type II normalization pipeline, then compares
# sliding windows across segments using SequenceMatcher.  Clones with
# threshold ≤ similarity < 1.0 are reported (sim=1.0 is already Type I/II).
# ═══════════════════════════════════════════════════════════════════════════════

def _build_flat_sequences(segments: list, children: dict) -> tuple:
    """Build per-segment statement sequences with block-type hashes for Type III detection.

    Each sequence entry is a ``(stmt_idx, norm2_str, raw_str)`` triple where
    ``norm2_str`` has ``{}`` placeholders replaced with structural block-type
    hashes so child-block structure is captured without requiring exact text.

    Args:
        segments: List of segment dicts from the parsed IR.
        children: Mapping of parent segment ID to ordered list of child IDs.

    Returns:
        A ``(sequences, seg_hashes)`` tuple where ``sequences`` is a dict
        mapping segment ID to list of ``(stmt_idx, norm2_str, raw_str)``
        triples, and ``seg_hashes`` maps segment ID to integer type ID.
    """
    seg_by_id = {seg["id"]: seg for seg in segments}
    seg_hashes = {}
    global_hash_to_id = {}

    def get_block_type_id(seg_id):
        if seg_id in seg_hashes:
            return seg_hashes[seg_id]
        seg = seg_by_id[seg_id]
        child_list = children.get(seg_id, [])
        hashed_stmts = []
        child_idx = 0
        for stmt in seg["stmts"]:
            raw = _get_raw(stmt)
            base_stmt = _normalize_stmt_type2(raw)
            target = "{ }" if "{ }" in base_stmt else "{}"
            while target in base_stmt and child_idx < len(child_list):
                c_type_id = get_block_type_id(child_list[child_idx])
                base_stmt = base_stmt.replace(target, f"<BLOCK_TYPE_{c_type_id}>", 1)
                child_idx += 1
            hashed_stmts.append(base_stmt)
        combined = " ".join(hashed_stmts)
        h_full = hashlib.sha256(combined.encode()).hexdigest()
        if h_full not in global_hash_to_id:
            global_hash_to_id[h_full] = len(global_hash_to_id) + 1
        seg_hashes[seg_id] = global_hash_to_id[h_full]
        return seg_hashes[seg_id]

    for seg in segments:
        get_block_type_id(seg["id"])

    sequences = {}
    for seg in segments:
        child_list = children.get(seg["id"], [])
        child_idx = 0
        seq = []
        for stmt_idx, stmt in enumerate(seg["stmts"]):
            raw = _get_raw(stmt)
            norm = _normalize_stmt_type2(raw)
            target = "{ }" if "{ }" in norm else "{}"
            while target in norm and child_idx < len(child_list):
                c_type_id = seg_hashes[child_list[child_idx]]
                norm = norm.replace(target, f"<BLOCK_TYPE_{c_type_id}>", 1)
                child_idx += 1
            seq.append((stmt_idx, norm, raw))
        sequences[seg["id"]] = seq

    return sequences, seg_hashes


def _sequence_similarity(seq_a, seq_b):
    """Token-level similarity between two statement sequences. Returns float [0..1]."""
    if not seq_a or not seq_b:
        return 0.0
    str_a = "\n".join(s[1] for s in seq_a)
    str_b = "\n".join(s[1] for s in seq_b)
    return SequenceMatcher(None, str_a, str_b).ratio()


def _get_diff_regions(seq_a, seq_b):
    """Return differing statement indices between two sequences."""
    norms_a = [s[1] for s in seq_a]
    norms_b = [s[1] for s in seq_b]
    sm = SequenceMatcher(None, norms_a, norms_b)
    diffs_a = set(range(len(norms_a)))
    diffs_b = set(range(len(norms_b)))
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i1, i2):
                diffs_a.discard(k)
            for k in range(j1, j2):
                diffs_b.discard(k)
    return sorted(diffs_a), sorted(diffs_b)


def detect_type3(json_str: str,
                 similarity_threshold: float = 0.7,
                 min_length: int = 3,
                 window_sizes: list = None,
                 exclude_seg_pairs: set = None) -> str:
    """
    Detect Type III (near-miss) clones.

    Builds Type-II-normalized statement sequences, then compares all
    segment-pair sliding windows.  Windows with threshold ≤ sim < 1.0
    are reported with their differing statement indices.

    Args:
        json_str:             Merged IR JSON string.
        similarity_threshold: Minimum similarity to qualify (default 0.7).
        min_length:           Minimum statements in a clone window (default 3).
        window_sizes:         Window sizes to try; default [min_length..10].
        exclude_seg_pairs:    Set of (seg_a, seg_b) tuples (canonical: min first)
                              to skip — typically pairs already covered by
                              Type I, II, or IV detection.
    """
    data = json.loads(json_str)
    segments = data["segments"]
    seg_by_id = {seg["id"]: seg for seg in segments}

    if exclude_seg_pairs is None:
        exclude_seg_pairs = set()

    children = defaultdict(list)
    for seg in segments:
        if seg["id"] != 0 and seg["parent"] != seg["id"]:
            children[seg["parent"]].append(seg["id"])
    for p in children:
        children[p].sort()

    sequences, _ = _build_flat_sequences(segments, children)

    if window_sizes is None:
        max_seq = max((len(seq) for seq in sequences.values() if seq), default=min_length)
        window_sizes = list(range(min_length, min(11, max_seq + 1)))

    clone_pairs = []
    seg_ids = sorted(sequences.keys())

    # Only compare function-level segments (skip loops, branches — they're
    # already covered as part of their parent function's window).
    fn_types = {"function", "root", "class"}

    for i_idx, seg_a_id in enumerate(seg_ids):
        seq_a = sequences[seg_a_id]
        if len(seq_a) < min_length:
            continue
        seg_a_type = seg_by_id.get(seg_a_id, {}).get("type", "")
        if seg_a_type not in fn_types:
            continue
        for seg_b_id in seg_ids[i_idx:]:
            seq_b = sequences[seg_b_id]
            if len(seq_b) < min_length:
                continue
            seg_b_type = seg_by_id.get(seg_b_id, {}).get("type", "")
            if seg_b_type not in fn_types:
                continue
            # Skip pairs already covered by other clone types
            canon_pair = (min(seg_a_id, seg_b_id), max(seg_a_id, seg_b_id))
            if canon_pair in exclude_seg_pairs:
                continue
            seq_b = sequences[seg_b_id]
            if len(seq_b) < min_length:
                continue
            for w in window_sizes:
                if w > len(seq_a) or w > len(seq_b):
                    continue
                for start_a in range(len(seq_a) - w + 1):
                    window_a = seq_a[start_a:start_a + w]
                    start_b_min = (start_a + 1) if seg_a_id == seg_b_id else 0
                    for start_b in range(start_b_min, len(seq_b) - w + 1):
                        if seg_a_id == seg_b_id:
                            if not (start_a + w <= start_b or start_b + w <= start_a):
                                continue
                        window_b = seq_b[start_b:start_b + w]
                        sim = _sequence_similarity(window_a, window_b)
                        if similarity_threshold <= sim < 1.0:
                            diffs_a, diffs_b = _get_diff_regions(window_a, window_b)
                            clone_pairs.append({
                                "seg_a": seg_a_id, "start_a": window_a[0][0],
                                "end_a": window_a[-1][0],
                                "seg_b": seg_b_id, "start_b": window_b[0][0],
                                "end_b": window_b[-1][0],
                                "similarity": round(sim, 4), "length": w,
                                "diffs_a": diffs_a, "diffs_b": diffs_b,
                            })

    # --- Maximal subsumption filter ---
    clone_pairs.sort(key=lambda c: (-c["length"], -c["similarity"]))

    def _subsumes(big, small):
        return (big["seg_a"] == small["seg_a"] and big["seg_b"] == small["seg_b"]
                and big["start_a"] <= small["start_a"] and big["end_a"] >= small["end_a"]
                and big["start_b"] <= small["start_b"] and big["end_b"] >= small["end_b"])

    maximal = []
    for cp in clone_pairs:
        if any(_subsumes(m, cp) for m in maximal):
            continue
        maximal.append(cp)
    clone_pairs = maximal

    # --- Best-per-segment-pair filter ---
    # For each unique (segA, segB) pair, keep only the single best match
    # (longest, then highest similarity).  This eliminates the sliding-window
    # explosion where the same two functions produce dozens of overlapping
    # windows at different offsets.
    pair_best = {}
    for cp in clone_pairs:
        pair_key = (min(cp["seg_a"], cp["seg_b"]), max(cp["seg_a"], cp["seg_b"]))
        prev = pair_best.get(pair_key)
        if prev is None or (cp["length"], cp["similarity"]) > (prev["length"], prev["similarity"]):
            pair_best[pair_key] = cp
    clone_pairs = list(pair_best.values())

    # --- Diff-ratio filter ---
    # Only keep clones where the differing statements are a small fraction
    # of the clone length.  This eliminates "shared idiom" matches (e.g.
    # two different functions that both start with `int x = 0; while(...)`)
    # while keeping true near-misses (1-2 statements changed out of 5+).
    max_diff_ratio = 0.5  # at most 50% of statements can differ
    clone_pairs = [
        cp for cp in clone_pairs
        if max(len(cp["diffs_a"]), len(cp["diffs_b"])) / cp["length"] <= max_diff_ratio
    ]

    # --- Dedup symmetric pairs ---
    clone_pairs.sort(key=lambda c: (-c["similarity"], -c["length"]))
    seen_regions = set()
    filtered = []
    for cp in clone_pairs:
        key = (cp["seg_a"], cp["start_a"], cp["seg_b"], cp["start_b"])
        rev_key = (cp["seg_b"], cp["start_b"], cp["seg_a"], cp["start_a"])
        if key not in seen_regions and rev_key not in seen_regions:
            seen_regions.add(key)
            seg_a = seg_by_id[cp["seg_a"]]
            seg_b = seg_by_id[cp["seg_b"]]
            cp["scope_a"] = seg_a.get("scope_path", "")
            cp["scope_b"] = seg_b.get("scope_path", "")
            cp["file_a"] = seg_a.get("file", "")
            cp["file_b"] = seg_b.get("file", "")
            cp["language_a"] = seg_a.get("language", "c")
            cp["language_b"] = seg_b.get("language", "c")
            cp["stmts_a"] = [_get_raw(seg_a["stmts"][i])
                             for i in range(cp["start_a"], cp["end_a"] + 1)
                             if i < len(seg_a["stmts"])]
            cp["stmts_b"] = [_get_raw(seg_b["stmts"][i])
                             for i in range(cp["start_b"], cp["end_b"] + 1)
                             if i < len(seg_b["stmts"])]
            filtered.append(cp)

    # --- Cluster into clone classes via connected components ---
    # Build a graph: segments are nodes, filtered pairs are edges.
    # Connected components become clone classes (like Type I/II/IV).
    # Each segment's occurrence data comes from the best pair that
    # included it (highest similarity).

    # Union-Find
    parent_uf = {}
    def find(x):
        while parent_uf.get(x, x) != x:
            parent_uf[x] = parent_uf.get(parent_uf[x], parent_uf[x])
            x = parent_uf[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent_uf[ra] = rb

    # Build occurrence info keyed by seg_id (keep highest-sim version)
    seg_occurrence = {}  # seg_id -> occurrence dict
    seg_best_sim = {}    # seg_id -> best similarity seen

    for cp in filtered:
        union(cp["seg_a"], cp["seg_b"])

        for side in ("a", "b"):
            sid = cp[f"seg_{side}"]
            sim = cp["similarity"]
            if sid not in seg_best_sim or sim > seg_best_sim[sid]:
                seg_best_sim[sid] = sim
                seg_occurrence[sid] = {
                    "seg_id": sid,
                    "start_stmt_idx": cp[f"start_{side}"],
                    "end_stmt_idx": cp[f"end_{side}"],
                    "scope_path": cp[f"scope_{side}"],
                    "file": cp[f"file_{side}"],
                    "language": cp[f"language_{side}"],
                    "statements": cp[f"stmts_{side}"],
                    "diff_indices": cp[f"diffs_{side}"],
                }

    # Group segments by their component root
    from collections import defaultdict as _dd
    components = _dd(set)
    for cp in filtered:
        root = find(cp["seg_a"])
        components[root].add(cp["seg_a"])
        components[root].add(cp["seg_b"])

    # Track per-class similarity range and pairwise info
    class_pairs = _dd(list)  # root -> list of filtered pairs
    for cp in filtered:
        class_pairs[find(cp["seg_a"])].append(cp)

    clone_classes = []
    for idx, (root, seg_ids) in enumerate(
        sorted(components.items(), key=lambda x: -len(x[1])), 1
    ):
        pairs = class_pairs[root]
        sims = [cp["similarity"] for cp in pairs]
        lengths = [cp["length"] for cp in pairs]
        occs = [seg_occurrence[sid] for sid in sorted(seg_ids) if sid in seg_occurrence]
        if len(occs) < 2:
            continue

        languages = set(o["language"] for o in occs)
        cross_lang = len(languages) > 1

        clone_classes.append({
            "id": idx,
            "clone_type": "III",
            "cross_language": cross_lang,
            "num_occurrences": len(occs),
            "similarity_min": round(min(sims), 4),
            "similarity_max": round(max(sims), 4),
            "similarity": round(max(sims), 4),
            "length": max(lengths),
            "occurrences": occs,
        })

    # Re-number
    for i, cc in enumerate(clone_classes, 1):
        cc["id"] = i

    return json.dumps({"clone_classes": clone_classes}, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE IV (simplified) — Semantic / structural clone detection
#
# Builds a structural fingerprint per function-level segment from:
#   1. Abstract statement-kind sequence  (assign / branch / loop / return …)
#   2. Read/write count pattern per stmt
#   3. Recursive child-block shape
# Functions with identical fingerprints are Type IV clones — same algorithm
# in different variable names, types, or even languages.
# ═══════════════════════════════════════════════════════════════════════════════

_KIND_MAP: dict = {
    "assign": "A", "decl_assign": "A", "compound_assign": "A",
    "increment": "A", "decrement": "A",
    "decl": "D",
    "return": "R", "break": "B", "continue": "C",
    "call": "K", "method_call": "K",
    "printf": "IO", "println": "IO", "print": "IO", "scanf": "IO",
    "if": "IF", "else": "ELSE", "else_if": "ELIF",
    "while": "W", "for": "F", "do_while": "DW",
    "switch": "SW", "case": "CASE",
    "try": "TRY", "catch": "CATCH",
}


def _abstract_kind(kind: str) -> str:
    """Map a concrete statement kind to its one-letter abstract category.

    Args:
        kind: A statement kind string such as ``"assign"`` or ``"branch"``.

    Returns:
        A short abstract category string (e.g. ``"A"``, ``"IF"``) or
        ``"X"`` for unrecognised kinds.
    """
    return _KIND_MAP.get(kind, "X")


def _get_kind(stmt) -> str:
    """Return the ``kind`` field from a statement dict, or an empty string.

    Args:
        stmt: A classified statement dict or any other value.

    Returns:
        The ``"kind"`` value if ``stmt`` is a dict, otherwise ``""``.
    """
    if isinstance(stmt, dict):
        return stmt.get("kind", "")
    return ""


def _structural_fingerprint(seg, children_map, seg_by_id, depth=0):
    """Recursive structural fingerprint for a segment and its children."""
    stmts = seg.get("stmts", [])
    kind_seq = []
    child_list = children_map.get(seg["id"], [])
    child_idx = 0

    for stmt in stmts:
        raw = _get_raw(stmt)
        kind = _get_kind(stmt)

        if kind:
            ak = _abstract_kind(kind)
        else:
            raw_lower = raw.strip().lower()
            if raw_lower.startswith("return"):      ak = "R"
            elif raw_lower.startswith(("if", "else if")): ak = "IF"
            elif raw_lower.startswith("else"):       ak = "ELSE"
            elif raw_lower.startswith("for"):        ak = "F"
            elif raw_lower.startswith("while"):      ak = "W"
            elif "=" in raw and not raw.strip().startswith("="): ak = "A"
            else: ak = "X"

        if "{}" in raw and child_idx < len(child_list):
            child_seg = seg_by_id.get(child_list[child_idx])
            if child_seg:
                child_fp = _structural_fingerprint(child_seg, children_map, seg_by_id, depth + 1)
                kind_seq.append((ak, "BLOCK", child_fp))
            else:
                kind_seq.append((ak, "BLOCK", ()))
            child_idx += 1
        else:
            kind_seq.append((ak,))

    return tuple(kind_seq)


def _count_rw(stmt) -> tuple:
    """Count the read and write names present in a statement dict.

    Args:
        stmt: A classified statement dict or any other value.

    Returns:
        A ``(reads, writes)`` tuple of non-negative integers.
    """
    if isinstance(stmt, dict):
        reads = len(stmt.get("r_names", []))
        writes = 1 if stmt.get("l_name") else 0
        return (reads, writes)
    return (0, 0)


def _semantic_signature(seg, children_map, seg_by_id):
    """Combine structural fingerprint + data-flow summary + child types."""
    fp = _structural_fingerprint(seg, children_map, seg_by_id)
    rw_pattern = tuple(_count_rw(s) for s in seg.get("stmts", []))
    child_list = children_map.get(seg["id"], [])
    child_types = tuple(seg_by_id[c].get("type", "?") for c in child_list if c in seg_by_id)
    return (fp, rw_pattern, child_types)


def detect_type4(json_str: str, min_length: int = 2) -> str:
    """
    Detect simplified Type IV (semantic) clones.

    Groups function-level segments by structural + data-flow fingerprint.
    Functions with identical fingerprints are semantic clones — same
    algorithm, different surface syntax.  Especially effective for
    cross-language detection (C ↔ Java).

    Args:
        json_str:   Merged IR JSON string.
        min_length: Minimum statements in a function to consider (default 2).
    """
    data = json.loads(json_str)
    segments = data["segments"]
    seg_by_id = {seg["id"]: seg for seg in segments}

    children = defaultdict(list)
    for seg in segments:
        if seg["id"] != 0 and seg["parent"] != seg["id"]:
            children[seg["parent"]].append(seg["id"])
    for p in children:
        children[p].sort()

    fn_segments = [
        seg for seg in segments
        if seg.get("type") == "function"
        and len(seg.get("stmts", [])) >= min_length
    ]

    sig_groups = defaultdict(list)
    for seg in fn_segments:
        sig = _semantic_signature(seg, children, seg_by_id)
        sig_hash = hashlib.sha256(repr(sig).encode()).hexdigest()
        sig_groups[sig_hash].append(seg)

    clone_classes = []
    clone_id = 0
    for sig_hash, group in sorted(sig_groups.items(), key=lambda x: -len(x[1])):
        if len(group) < 2:
            continue
        clone_id += 1
        languages = set(seg.get("language", "c") for seg in group)
        cross_lang = len(languages) > 1
        occurrences = []
        for seg in group:
            stmts = seg.get("stmts", [])
            occurrences.append({
                "seg_id": seg["id"],
                "start_stmt_idx": 0,
                "end_stmt_idx": len(stmts) - 1,
                "scope_path": seg.get("scope_path", ""),
                "file": seg.get("file", ""),
                "language": seg.get("language", "c"),
                "function_name": seg.get("name", ""),
                "statements": [_get_raw(s) for s in stmts],
            })
        clone_classes.append({
            "id": clone_id,
            "clone_type": "IV",
            "cross_language": cross_lang,
            "num_occurrences": len(occurrences),
            "signature_hash": sig_hash[:16],
            "occurrences": occurrences,
        })

    return json.dumps({"clone_classes": clone_classes}, indent=2)