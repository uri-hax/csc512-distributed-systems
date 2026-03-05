"""Parse a Java source file into the common CDUP IR JSON.

Architecture:
  Java source
      │
      ▼
  preprocess_java()          [java_preprocess.py]
      │   strips modifiers, maps types, desugars syntax
      │   result is near-C that parse_c_file can handle
      ▼
  parse_c_file()             [parse.py]
      │   brace scanner, segment tree, classify stmts,
      │   extract memory/constants, attach expr trees,
      │   build matrix + DAG
      ▼
  _java_fixup()              [this file]
      │   post-process: set language="java", fix scope paths
      │   (class lives between root and methods),
      │   annotate enhanced-for vars, clean up preprocessor
      │   artefacts from the segment JSON
      ▼
  Common IR JSON             (identical schema to C output)

The Common IR schema is unchanged — segments have the same keys whether
the source was C or Java.  Cross-language clone detection works by simply
merging the segment lists from C and Java parse outputs and running
detect_clones on the union.
"""

import json
import re

try:
    from .java_preprocess import preprocess_java
    from .parse import parse_c_file
except ImportError:
    from java_preprocess import preprocess_java
    from parse import parse_c_file


# ---------------------------------------------------------------------------
# Post-processing fixups
# ---------------------------------------------------------------------------

def _fixup_language_tag(segments: list) -> list:
    """Annotate every segment with ``language="java"``.

    Args:
        segments: List of segment dicts from the parsed IR.

    Returns:
        The same list with ``language`` set on every segment.
    """
    for seg in segments:
        seg["language"] = "java"
    return segments


def _fixup_seg_types(segments: list) -> list:
    """Rename struct segments from Java class declarations to ``type="class"``.

    Detects class segments by checking whether they have any direct
    ``function``-type children.

    Args:
        segments: List of segment dicts from the parsed IR.

    Returns:
        The same list with qualifying struct segments re-typed as ``"class"``.
    """
    has_fn_child = set()
    for seg in segments:
        parent = seg.get("parent")
        if seg.get("type") == "function" and parent is not None:
            has_fn_child.add(parent)
    for seg in segments:
        if seg.get("type") == "struct" and seg["id"] in has_fn_child:
            seg["type"] = "class"
    return segments


def _fixup_enhanced_for_vars(segments: list) -> list:
    """Process enhanced-for loop variable annotations emitted by the preprocessor.

    The preprocessor emits a sentinel comment for each enhanced-for variable::

        /* __efor_var__ TYPE VAR COLLECTION */

    This function extracts the annotation, injects a memory slot for ``VAR``
    into the corresponding loop segment, and removes the comment statement.

    Args:
        segments: List of segment dicts from the parsed IR.

    Returns:
        The same list with enhanced-for memory slots injected and sentinel
        comments removed.
    """
    _EFOR_RE = re.compile(r'/\*\s*__efor_var__\s+(\S+)\s+(\S+)\s+(\S+)\s*\*/')

    efor_queue = []
    for seg in segments:
        stmts = seg.get("stmts", [])
        to_remove = []
        for idx, st in enumerate(stmts):
            m = _EFOR_RE.search(st.get("raw", ""))
            if m:
                efor_queue.append({
                    "parent_seg_id": seg["id"],
                    "stmt_idx":      idx,
                    "var_type":      m.group(1),
                    "var_name":      m.group(2),
                    "collection":    m.group(3),
                })
                to_remove.append(idx)
        for idx in reversed(to_remove):
            stmts.pop(idx)

    if not efor_queue:
        return segments

    children_of = {}
    for seg in segments:
        pid = seg.get("parent")
        if pid is not None and pid != seg["id"]:
            children_of.setdefault(pid, []).append(seg["id"])

    seg_by_id = {seg["id"]: seg for seg in segments}

    for efor in efor_queue:
        parent_id  = efor["parent_seg_id"]
        var_name   = efor["var_name"]
        var_type   = efor["var_type"]
        collection = efor["collection"]
        children   = children_of.get(parent_id, [])
        loop_segs  = [seg_by_id[c] for c in children
                      if seg_by_id.get(c, {}).get("type") == "loop"]
        for loop_seg in loop_segs:
            scope_path = loop_seg.get("scope_path", "")
            slot = {
                "name":              var_name,
                "scoped_name":       f"{scope_path}.{var_name}",
                "type":              var_type,
                "constant":          False,
                "enhanced_for_var":  True,
                "collection":        collection,
            }
            mem = loop_seg.setdefault("memory", [])
            if not any(s["name"] == var_name for s in mem):
                mem.insert(0, slot)
            break

    return segments


def _fixup_remove_catch_void(segments: list) -> list:
    """Rename ``void*`` types in catch-block memory slots to ``"exception"``.

    Args:
        segments: List of segment dicts from the parsed IR.

    Returns:
        The same list with ``void*`` slot types renamed in branch segments.
    """
    for seg in segments:
        for slot in seg.get("memory", []):
            if slot.get("type") == "void*" and seg.get("type") == "branch":
                slot["type"] = "exception"
    return segments


def _java_fixup(ir: dict) -> dict:
    """Apply all Java-specific post-processing fixups to the parsed IR.

    Runs :func:`_fixup_language_tag`, :func:`_fixup_seg_types`,
    :func:`_fixup_enhanced_for_vars`, and :func:`_fixup_remove_catch_void`
    in order.

    Args:
        ir: Parsed IR dict (as returned by :func:`parse_c_file` after JSON
            deserialisation).

    Returns:
        The modified IR dict with Java annotations applied.
    """
    segs = ir.get("segments", [])
    segs = _fixup_language_tag(segs)
    segs = _fixup_seg_types(segs)
    segs = _fixup_enhanced_for_vars(segs)
    segs = _fixup_remove_catch_void(segs)
    ir["segments"] = segs
    return ir


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_java_file(file_str: str) -> str:
    """Parse a Java source string and return Common IR JSON.

    The output schema is identical to :func:`parse_c_file` — segments with
    ``id``, ``parent``, ``type``, ``name``, ``scope_path``, ``head``,
    ``memory``, ``constants``, and ``stmts``, plus ``matrix`` and ``dag`` —
    with ``language: "java"`` added to every segment.

    Args:
        file_str: Raw Java source code as a string.

    Returns:
        A JSON string conforming to the Common IR schema.
    """
    near_c   = preprocess_java(file_str)
    raw_json = parse_c_file(near_c)
    ir       = json.loads(raw_json)
    ir       = _java_fixup(ir)
    return json.dumps(ir, indent=2)