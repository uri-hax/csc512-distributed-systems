import os
import json
from ..parse import parse_c_file

def _collect_c_files(src: str) -> list:
    if os.path.isfile(src):
        if src.endswith('.c'):
            return [src]
        else:
            print(f"Error: '{src}' is not a .c file or directory.")
            exit(1)
    elif os.path.isdir(src):
        c_files = []
        for root, _, files in os.walk(src):
            for f in files:
                if f.endswith('.c'):
                    c_files.append(os.path.join(root, f))
        if not c_files:
            print(f"Error: No .c files found in '{src}'.")
            exit(1)
        return c_files
    else:
        print(f"Error: '{src}' is not a valid file or directory.")
        exit(1)

def _build_parse_meta(parsed_list: list, skipped_files: list) -> dict:
    """Build summary metadata for the parsed JSON output."""
    all_files = []
    all_modules = set()
    seg_type_counts = {"root": 0, "function": 0, "logic": 0, "struct": 0}
    total_statements = 0

    for parsed_str in parsed_list:
        data = json.loads(parsed_str)
        file_meta = data.get("meta", {})
        all_files.extend(file_meta.get("files", []))
        for seg in data["segments"]:
            seg_type_counts[seg.get("type", "function")] = seg_type_counts.get(seg.get("type", "function"), 0) + 1
            total_statements += len(seg.get("statements", []))
            if "module" in seg:
                all_modules.add(seg["module"])

    return {
        "type": "parsed",
        "norm_level": 1,
        "files": all_files,
        "total_files": len(all_files),
        "skipped_files": skipped_files,
        "total_skipped_files": len(skipped_files),
        "total_modules": len(all_modules),
        "modules": sorted(all_modules),
        "total_segments": sum(seg_type_counts.values()),
        "segments_by_type": seg_type_counts,
        "total_statements": total_statements,
    }


def _merge_parsed_jsons(parsed_list: list, skipped_files: list = None) -> str:
    all_segments = []
    id_offset = 0
    skipped_files = skipped_files or []

    for parsed_str in parsed_list:
        data = json.loads(parsed_str)
        segments = data["segments"]
        for seg in segments:
            new_seg = dict(seg)
            new_seg["id"] = seg["id"] + id_offset
            new_seg["parent"] = seg["parent"] + id_offset
            all_segments.append(new_seg)
        id_offset += len(segments)

    meta = _build_parse_meta(parsed_list, skipped_files)
    return json.dumps({"meta": meta, "segments": all_segments}, indent=2)


def _parse_file(filepath: str, include_comments: bool = False, include_includes: bool = False, include_macros: bool = False) -> str:
    try:
        with open(filepath, 'r', errors='replace') as f:
            content = f.read()
    except (OSError, IOError) as e:
        print(f"Warning: Skipping '{filepath}': {e}")
        return None, filepath
    filename = os.path.basename(filepath)
    module = os.path.basename(os.path.dirname(os.path.abspath(filepath)))

    try:
        p = parse_c_file(content, include_comments, include_includes, include_macros)
    except ValueError as e:
        print(f"Warning: Skipping '{filepath}': {e}")
        return None, filepath
    except (OSError, IOError) as e:
        print(f"Warning: Skipping '{filepath}': {e}")
        return None, filepath
    except Exception as e:
        print(f"Warning: Skipping '{filepath}' due to unexpected error: {e}")
        return None, filepath

    data = json.loads(p)
    # Count segment types and statements for per-file summary
    seg_type_counts = {"root": 0, "function": 0, "logic": 0, "struct": 0}
    total_statements = 0
    for seg in data["segments"]:
        seg["file"] = filename
        seg["module"] = module
        seg_type_counts[seg.get("type", "function")] = seg_type_counts.get(seg.get("type", "function"), 0) + 1
        total_statements += len(seg.get("statements", []))

    ordered = {
        "meta": {
            "type": "parsed",
            "norm_level": 1,
            "files": [filename],
            "total_files": 1,
            "skipped_files": [],
            "total_skipped_files": 0,
            "total_modules": 1,
            "modules": [module],
            "total_segments": sum(seg_type_counts.values()),
            "segments_by_type": seg_type_counts,
            "total_statements": total_statements,
        },
        "segments": data["segments"]
    }
    return json.dumps(ordered, indent=2), None