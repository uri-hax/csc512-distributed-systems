import json
from ..detect import detect_clones
from .utils import _collect_c_files, _parse_file, _merge_parsed_jsons

def _parse_files(filepaths, include_comments, include_includes, include_macros):
    """Parse a list of files, returning (parsed_list, skipped_list)."""
    results = [_parse_file(fp, include_comments, include_includes, include_macros) for fp in filepaths]
    parsed_list = [r for r, _ in results if r is not None]
    skipped_list = [s for _, s in results if s is not None]
    return parsed_list, skipped_list


def _build_parsed_str(parsed_list, skipped_list):
    """Merge parsed files into a single JSON string."""
    if len(parsed_list) == 1:
        # Single file: inject skipped into its meta for completeness
        data = json.loads(parsed_list[0])
        data["meta"]["skipped_files"] = skipped_list
        data["meta"]["total_skipped_files"] = len(skipped_list)
        return json.dumps(data, indent=2)
    return _merge_parsed_jsons(parsed_list, skipped_list)


def cmd_parse(args):
    c_files = _collect_c_files(args.src)
    parsed_list, skipped_list = _parse_files(c_files, args.include_comments, args.include_includes, args.include_macros)

    if not parsed_list:
        print("Error: No files could be parsed successfully.")
        exit(1)

    result = _build_parsed_str(parsed_list, skipped_list)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(result)
        print(f"Parsed output written to {args.output}")
    else:
        print(result)

def cmd_detect(args):
    src = args.src
    types = args.type
    skipped_list = []

    if src.endswith('.json'):
        with open(src, 'r') as f: parsed_str_for_detect = f.read()
        data = json.loads(parsed_str_for_detect)
        norm_level = data.get("meta", {}).get("norm_level", 1)
        if norm_level == 2 and 1 in types:
            print("Error: Input JSON was normalized at Type II level. Cannot run Type I detection.")
            exit(1)
    else:
        c_files = _collect_c_files(src)
        parsed_list, skipped_list = _parse_files(c_files, args.include_comments, args.include_includes, args.include_macros)
        if not parsed_list:
            print("Error: No files could be parsed successfully.")
            exit(1)
        parsed_str_for_detect = _build_parsed_str(parsed_list, skipped_list)

    results_by_type = {}
    for t in sorted(types):
        result_str = detect_clones(parsed_str_for_detect, type_2_norm=(t == 2), maximal=args.maximal,
                                   min_length=args.min_length, max_freq=args.max_freq,
                                   filter_overlaps=args.filter_overlaps, include_comments=args.include_comments,
                                   include_includes=args.include_includes, include_macros=args.include_macros)
        results_by_type[t] = json.loads(result_str)["clone_classes"]

    type1_fingerprints = set()
    if 1 in results_by_type:
        for clone in results_by_type[1]:
            fp = frozenset(
                (o["seg_id"], o["start_stmt_idx"], o["end_stmt_idx"])
                for o in clone["occurrences"]
            )
            type1_fingerprints.add(fp)

    all_clone_classes = []
    for t in sorted(types):
        for clone in results_by_type[t]:
            if t == 2 and 1 in results_by_type:
                fp = frozenset(
                    (o["seg_id"], o["start_stmt_idx"], o["end_stmt_idx"])
                    for o in clone["occurrences"]
                )
                if fp in type1_fingerprints:
                    continue
            all_clone_classes.append(clone)
    for i, clone in enumerate(all_clone_classes, 1):
        clone["id"] = i

    # --- Build detection metadata ---
    parse_meta = json.loads(parsed_str_for_detect).get("meta", {})
    seg_by_id_meta = {seg["id"]: seg for seg in json.loads(parsed_str_for_detect)["segments"]}

    total_occurrences = sum(len(c["occurrences"]) for c in all_clone_classes)
    total_cloned_stmts = sum(
        c["length"] * len(c["occurrences"]) for c in all_clone_classes
    )
    clones_by_type = {}
    for c in all_clone_classes:
        ct = c["clone_type"]
        clones_by_type[ct] = clones_by_type.get(ct, 0) + 1

    # Files and modules involved in at least one clone
    cloned_seg_ids = set(
        o["seg_id"] for c in all_clone_classes for o in c["occurrences"]
    )
    cloned_files = set()
    cloned_modules = set()
    for sid in cloned_seg_ids:
        seg = seg_by_id_meta.get(sid, {})
        if "file" in seg:
            cloned_files.add(seg["file"])
        if "module" in seg:
            cloned_modules.add(seg["module"])

    largest_clone = max((c["length"] for c in all_clone_classes), default=0)
    most_occurrences = max((len(c["occurrences"]) for c in all_clone_classes), default=0)

    # Segment duplication: count how many clone classes touch each seg
    seg_clone_count = {}
    for c in all_clone_classes:
        for o in c["occurrences"]:
            sid = o["seg_id"]
            seg_clone_count[sid] = seg_clone_count.get(sid, 0) + 1
    most_cloned_seg_id = max(seg_clone_count, key=seg_clone_count.get) if seg_clone_count else None
    most_cloned_seg_file = seg_by_id_meta.get(most_cloned_seg_id, {}).get("file") if most_cloned_seg_id is not None else None

    detect_meta = {
        # Detection settings
        "clone_types_detected": sorted(types),
        "min_length": args.min_length,
        "max_freq": args.max_freq,
        "maximal_filter": args.maximal,
        "overlap_filter": args.filter_overlaps,
        # Source corpus stats (from parse)
        "total_files_scanned": parse_meta.get("total_files", len(parse_meta.get("files", []))),
        "total_files_skipped": len(skipped_list),
        "skipped_files": skipped_list,
        "total_modules": parse_meta.get("total_modules", 0),
        "total_segments": parse_meta.get("total_segments", 0),
        "total_statements": parse_meta.get("total_statements", 0),
        # Clone summary
        "total_clone_classes": len(all_clone_classes),
        "clone_classes_by_type": clones_by_type,
        "total_occurrences": total_occurrences,
        "total_cloned_statements": total_cloned_stmts,
        "largest_clone_length": largest_clone,
        "most_occurrences_in_class": most_occurrences,
        # Coverage
        "files_with_clones": sorted(cloned_files),
        "total_files_with_clones": len(cloned_files),
        "modules_with_clones": sorted(cloned_modules),
        "total_modules_with_clones": len(cloned_modules),
        "most_cloned_seg_id": most_cloned_seg_id,
        "most_cloned_seg_file": most_cloned_seg_file,
        "total_segments_with_clones": len(seg_clone_count),
    }

    all_results = {"meta": detect_meta, "clone_classes": all_clone_classes}
    final = json.dumps(all_results, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(final)
        print(f"Detection output written to {args.output}")
    else:
        print(final)