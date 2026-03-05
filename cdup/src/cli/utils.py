"""Shared file-collection and JSON-merging utilities for CDUP commands.

Provides helpers used by both the ``parse`` and ``detect`` CLI subcommands:
collecting source files from the filesystem, parsing individual files into
IR JSON, and merging per-file IR blobs into a single combined document.
"""

import os
import sys
import json

from ..parse import parse_c_file
from ..matrix import build_matrix
from ..dag import build_dag
try:
    from ..java_parse import parse_java_file
except ImportError:
    from java_parse import parse_java_file

_SOURCE_EXTENSIONS: tuple = ('.c', '.java')


def _collect_c_files(src: str) -> list:
    """Backward-compatible alias for :func:`_collect_source_files`.

    Args:
        src: Path to a source file or directory.

    Returns:
        List of file paths with ``.c`` or ``.java`` extensions.
    """
    return _collect_source_files(src)


def _collect_source_files(src: str) -> list:
    """Collect ``.c`` and ``.java`` source files from a path or directory.

    Terminates the process with a printed error message if ``src`` does not
    exist, is not a recognised source file, or contains no matching files.

    Args:
        src: Path to a single source file or a directory to walk recursively.

    Returns:
        List of file paths with ``.c`` or ``.java`` extensions.
    """
    if os.path.isfile(src):
        if src.endswith(_SOURCE_EXTENSIONS):
            return [src]
        print(f"Error: '{src}' is not a .c/.java file or directory.")
        sys.exit(1)
    elif os.path.isdir(src):
        files: list = []
        for root, _, fnames in os.walk(src):
            for f in fnames:
                if f.endswith(_SOURCE_EXTENSIONS):
                    files.append(os.path.join(root, f))
        if not files:
            print(f"Error: No .c or .java files found in '{src}'.")
            sys.exit(1)
        return files
    else:
        print(f"Error: '{src}' is not a valid file or directory.")
        sys.exit(1)


def _build_parse_meta(parsed_list: list, skipped_files: list) -> dict:
    """Build summary metadata for the combined parsed JSON output.

    Args:
        parsed_list: Per-file JSON strings produced by :func:`_parse_file`.
        skipped_files: File paths that failed to parse.

    Returns:
        A metadata dict containing file counts, module names, per-type
        segment counts, and total statement count.
    """
    all_files: list = []
    all_modules: set = set()
    seg_type_counts: dict = {
        "root": 0, "function": 0, "loop": 0,
        "branch": 0, "struct": 0, "class": 0,
    }
    total_statements: int = 0

    for parsed_str in parsed_list:
        data = json.loads(parsed_str)
        file_meta = data.get("meta", {})
        all_files.extend(file_meta.get("files", []))
        for seg in data["segments"]:
            t = seg.get("type", "function")
            seg_type_counts[t] = seg_type_counts.get(t, 0) + 1
            total_statements += len(seg.get("stmts", []))
            if "module" in seg:
                all_modules.add(seg["module"])

    return {
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
    """Merge multiple per-file IR JSON strings into a single combined document.

    Segment IDs are renumbered sequentially to avoid collisions across files.
    The dependency matrix and DAG are rebuilt over the full merged segment list.

    Args:
        parsed_list: Per-file JSON strings produced by :func:`_parse_file`.
        skipped_files: File paths that failed to parse. Defaults to ``[]``.

    Returns:
        A JSON string with ``meta``, ``segments``, ``matrix``, and ``dag``
        keys covering all merged files.
    """
    all_segments: list = []
    id_offset: int = 0
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
    matrix = build_matrix(all_segments)
    dag = build_dag(all_segments, matrix)
    return json.dumps(
        {"meta": meta, "segments": all_segments, "matrix": matrix, "dag": dag},
        indent=2,
    )


def _parse_file(filepath: str, include_comments: bool = False,
                include_includes: bool = False, include_macros: bool = False) -> tuple:
    """Parse a single ``.c`` or ``.java`` file into an IR JSON string.

    Args:
        filepath: Absolute or relative path to the source file.
        include_comments: Whether to include comment statements in the IR.
        include_includes: Whether to include ``#include`` directives.
        include_macros: Whether to include ``#define`` and other macro lines.

    Returns:
        ``(json_str, None)`` on success, or ``(None, filepath)`` if the file
        could not be read or parsed.
    """
    try:
        with open(filepath, 'r', errors='replace') as f:
            content = f.read()
    except (OSError, IOError) as e:
        print(f"Warning: Skipping '{filepath}': {e}")
        return None, filepath

    filename: str = os.path.basename(filepath)
    module: str = os.path.basename(os.path.dirname(os.path.abspath(filepath)))
    is_java: bool = filepath.endswith('.java')

    try:
        if is_java:
            p = parse_java_file(content)
        else:
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
    seg_type_counts: dict = {
        "root": 0, "function": 0, "loop": 0,
        "branch": 0, "struct": 0, "class": 0,
    }
    total_statements: int = 0
    for seg in data["segments"]:
        seg["file"] = filename
        seg["module"] = module
        seg["language"] = "java" if is_java else "c"
        t = seg.get("type", "function")
        seg_type_counts[t] = seg_type_counts.get(t, 0) + 1
        total_statements += len(seg.get("stmts", []))

    matrix = build_matrix(data["segments"])
    dag = build_dag(data["segments"], matrix)

    ordered = {
        "meta": {
            "files": [filename],
            "total_files": 1,
            "skipped_files": [],
            "total_skipped_files": 0,
            "total_modules": 1,
            "modules": [module],
            "total_segments": sum(seg_type_counts.values()),
            "segments_by_type": seg_type_counts,
            "total_statements": total_statements,
            "language": "java" if is_java else "c",
        },
        "segments": data["segments"],
        "matrix": matrix,
        "dag": dag,
    }
    return json.dumps(ordered, indent=2), None