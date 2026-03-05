# CDUP — C/Java Code Duplication Detector

A static analysis tool for detecting code clones across C and Java source files. CDUP parses source code into a language-neutral intermediate representation (IR), constructs a dependency matrix and data-flow DAG, and runs one or more clone detection algorithms over the result.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Installation](#installation)
3. [Pipeline](#pipeline)
4. [CLI Reference](#cli-reference)
   - [parse](#parse)
   - [detect](#detect)
   - [run](#run)
5. [Clone Types](#clone-types)
6. [IR Schema](#ir-schema)
7. [Java Support](#java-support)
8. [Module Reference](#module-reference)

---

## Architecture

```
Source (.c / .java)
        │
        ▼
   Preprocessor          java_preprocess.py  [Java only]
        │
        ▼
     Parser              parse.py
        │   brace scan → segment tree → statement classification
        │   → memory/constant extraction → scope-path assignment
        ▼
   Dependency Matrix      matrix.py
        │   slot × statement matrix; phi-node injection
        ▼
   Data-flow DAG          dag.py
        │   SSA-style def-use edges; synthetic entry nodes
        ▼
   Common IR JSON         (segments + matrix + dag)
        │
        ├──▶  Clone Detection    detect.py   (Types I–IV)
        │
        └──▶  Interpreter VM     vm.py       (tree-walking executor)
```

The IR schema is identical for C and Java output. Cross-language clone detection operates by merging segment lists from both languages and running detection on the union.

---

## Installation

No build step is required. The package runs as a Python module.

**Requirements:** Python ≥ 3.10

Optional dependencies (only needed for specific export features):
- `networkx`, `matplotlib` — DAG PNG rendering (`visualize_dag`)
- `pygraphviz` or `pydot` — hierarchical layout for DAG visualisation

```bash
# Run as a package from its parent directory
python -m cdup <subcommand> [options]
```

---

## Pipeline

### 1. Parsing

`parse.py` processes a C source string in five stages:

1. **Brace scanning** — identifies all `{…}` block boundaries via `_find_nested_pairs`.
2. **Segment extraction** — builds a tree of scoped segments (root, function, loop, branch, struct/class).
3. **Statement classification** — each line is labelled as one of: `decl`, `assign`, `branch`, `loop_head`, `control`, `call`, `func_decl`, or `expr`.
4. **Memory/constant extraction** — variable slots and literal constants are extracted and scoped.
5. **Expression parsing** — RHS expressions are parsed into typed trees by `expr.py` (Pratt parser).

### 2. Dependency Matrix

`matrix.py` converts the segment tree into a flat slot × statement matrix. Each row corresponds to one statement event and records:

- `reads` — scoped slot names read
- `writes` — scoped slot names written
- `decls` — slots declared at this point

Phi nodes are injected at branch reconvergence points and loop entry points (SSA-style).

### 3. Data-flow DAG

`dag.py` constructs a directed acyclic graph (with back-edges for loops) from the matrix. Edge kinds:

| Kind | Meaning |
|------|---------|
| `data_flow` | Standard def-use dependency |
| `phi_loop` | Back-edge into a loop-entry phi node |
| `phi_branch` | Branch-reconvergence phi merging two branch writes |

Each function/root/struct scope receives a synthetic entry node that writes all parameter and constant slots, providing a traceable source for every downstream read.

---

## CLI Reference

All subcommands follow the form:

```bash
python -m cdup <subcommand> --src <path> [options]
```

---

### `parse`

Parse one or more C/Java source files into IR JSON.

```bash
python -m cdup parse --src <file_or_dir> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--src` | *(required)* | Path to a `.c`/`.java` file or directory. Directories are walked recursively. |
| `--include-comments` | `false` | Include comment lines as statements in the IR. |
| `--include-includes` | `false` | Include `#include` directives as statements. |
| `--include-macros` | `false` | Include `#define` and other macro lines. |
| `--output <file>` | stdout | Write the IR JSON to a file instead of stdout. |
| `--export-matrix-csv [file]` | `matrix.csv` | Export the dependency matrix as a CSV file. |
| `--export-dag-dot [file]` | `dag.dot` | Export the DAG as a Graphviz DOT file. |
| `--export-3d-html [file]` | `dag_3d.html` | Export the DAG as an interactive 3-D HTML visualisation. |

**Output format** — top-level keys:

```json
{
  "meta": { "files": [], "total_segments": 0, "total_statements": 0, ... },
  "segments": [ ... ],
  "matrix":   { "slots": [], "rows": [] },
  "dag":      { "nodes": [], "edges": [] }
}
```

---

### `detect`

Detect code clones from source files or a pre-parsed JSON file.

```bash
python -m cdup detect --src <file_or_dir_or_json> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--src` | *(required)* | Path to a `.c`/`.java` file, directory, or a `.json` file produced by `parse`. |
| `--type 1 2 3 4` | `1` | One or more clone types to detect. Multiple values accepted (e.g. `--type 1 2`). |
| `--min-length` | `2` | Minimum clone sequence length (in statements) to report. |
| `--max-freq` | `0` (no limit) | Skip statements that appear more than this many times across all segments. Useful for filtering common boilerplate. |
| `--maximal` / `--no-maximal` | `true` | Filter out clone classes fully subsumed by a longer clone class. |
| `--filter-overlaps` / `--no-filter-overlaps` | `true` | Remove clone classes where all occurrences are in the same segment with overlapping ranges. |
| `--similarity-threshold` | `0.7` | Minimum sequence similarity ratio for Type III detection (0.0–1.0). |
| `--min-length-type3` | `3` | Minimum clone length for Type III detection. |
| `--include-comments` | `false` | Include comments when parsing inline (ignored for pre-parsed JSON input). |
| `--include-includes` | `false` | Include `#include` directives when parsing inline. |
| `--include-macros` | `false` | Include macro statements when parsing inline. |
| `--output <file>` | stdout | Write detection output to a file. |
| `--export-3d-html [file]` | `clone_dag_3d.html` | Export an interactive 3-D DAG + clone visualisation. |

**Output format:**

```json
{
  "meta": {
    "clone_types_detected": [1, 2],
    "total_clone_classes": 12,
    "clone_classes_by_type": { "I": 8, "II": 4 },
    "cross_language_clone_classes": 2,
    "total_occurrences": 31,
    "largest_clone_length": 14,
    ...
  },
  "clone_classes": [
    {
      "id": 1,
      "clone_type": "I",
      "length": 5,
      "statements": [ ... ],
      "occurrences": [
        { "seg_id": 3, "start_stmt_idx": 2, "end_stmt_idx": 6 },
        { "seg_id": 11, "start_stmt_idx": 0, "end_stmt_idx": 4 }
      ]
    }
  ]
}
```

Type II clone entries additionally include a `"normalized"` field containing the identifier-abstracted token sequence.

**Detection ordering note:** Types I, II, and IV are run first. Type III only reports clone pairs not already identified by the other detectors. Type II results that are strict duplicates of Type I results are suppressed in the final output.

---

### `run`

Execute a named function from a pre-parsed IR JSON file using the tree-walking VM.

```bash
python -m cdup run --src <parsed.json> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--src` | *(required)* | Path to a `.json` file produced by `parse`. Raw source is not accepted. |
| `--fn` | `main` | Name of the function to execute. |
| `--args` | `[]` | Space-separated JSON values for the function's parameters (e.g. `'[1,2,3]' 3`). |
| `--max-unroll` | `10000` | Maximum loop iterations before capping execution. |
| `--output [file]` | *(print to stdout)* | If provided, appends the execution trace to the parsed JSON and writes it out. If no path is given, writes back to `--src`. |

**Output (stdout mode):** program `printf` output, one line per call.

**Output (trace mode):** the parsed JSON doc with an appended `"trace"` key containing a list of execution events, each recording:

```json
{
  "kind": "assign",
  "raw": "sum += u[i] * v[i];",
  "seg_id": 4,
  "scope_path": "root.dot_product.loop_1",
  "fn": "dot_product",
  "iteration": 2,
  "read_values":  { "sum": 14, "u": [1,2,3], "i": 2 },
  "write_values": { "sum": 32 },
  "branch_taken": null
}
```

---

## Clone Types

| Type | Label | Algorithm | Description |
|------|-------|-----------|-------------|
| I | `"I"` | Inverted-index suffix scan | Exact match after whitespace normalisation. |
| II | `"II"` | Inverted-index suffix scan | Structural match after identifier abstraction. User-defined identifiers are renamed to positional `VAR_N` tokens; C/Java keywords are preserved. |
| III | `"III"` | Sliding-window `SequenceMatcher` | Near-miss clones. Pairs of segments whose statement sequences exceed `--similarity-threshold` after Type-II normalisation, and are not already covered by Types I/II/IV. |
| IV | `"IV"` | Abstract structural fingerprint | Semantic/structural clones. Segments are fingerprinted by their abstract statement-kind sequence (e.g. `DECL·LOOP·ASSIGN·RETURN`); segments with identical fingerprints and the same length are reported as Type IV. |

The `--maximal` filter removes any clone class whose every occurrence is fully contained within a longer clone class of the same type. This reduces redundant reporting while preserving all structurally distinct clone groups.

---

## IR Schema

### Segment

```json
{
  "id": 4,
  "parent": 1,
  "type": "loop",
  "name": "loop_1",
  "scope_path": "root.dot_product.loop_1",
  "head": "for (int i = 0; i < n; i++) {}",
  "memory": [ { "name": "i", "scoped_name": "root.dot_product.loop_1.i",
                "type": "int", "loop_iterator": true } ],
  "constants": [],
  "stmts": [ { "raw": "sum += u[i] * v[i];", "kind": "assign",
               "l_name": "sum", "r_names": ["sum", "u", "i", "v", "i"] } ]
}
```

**Segment types:** `root`, `function`, `loop`, `branch`, `struct`, `class`

**Statement kinds:** `decl`, `assign`, `branch`, `loop_head`, `control`, `call`, `func_decl`, `expr`

### Matrix row

```json
{
  "kind": "assign",
  "seg_id": 4,
  "scope_path": "root.dot_product.loop_1",
  "raw": "sum += u[i] * v[i];",
  "reads":  ["root.dot_product.sum", "root.dot_product.u", "root.dot_product.loop_1.i", "root.dot_product.v"],
  "writes": ["root.dot_product.sum"],
  "decls":  [],
  "note": null,
  "expr": { "op": "add", "args": [ { "slot": "root.dot_product.sum" }, { "op": "mul", "args": [...] } ] }
}
```

### DAG node / edge

```json
{ "id": 7, "kind": "assign", "seg_id": 4, "scope_path": "...", "raw": "...",
  "reads": [...], "writes": [...], "decls": [...], "note": null }

{ "from": 5, "to": 7, "slot": "root.dot_product.sum", "kind": "data_flow" }
```

---

## Java Support

Java source is handled by a two-stage pipeline:

1. **Preprocessing** (`java_preprocess.py`) — transforms Java into near-C via a sequence of text passes. Key transformations:
   - Access modifiers (`public`, `private`, `static`, …) stripped
   - Java types mapped to C equivalents (`boolean→int`, `String→char*`, `Object→void*`)
   - Generics (`List<T>`) stripped to bare type names
   - `new T[n]` → `malloc(n * sizeof(T))`
   - `System.out.println` → `printf`, `Math.*` → C math equivalents
   - Enhanced-for (`for (T x : col)`) desugared to counted `for` loop
   - `this.field` → `field`

2. **Parsing** (`java_parse.py`) — calls `parse_c_file` on the near-C output, then applies post-processing fixups: language tagging, struct→class reclassification, enhanced-for variable injection.

Limitations: generics are stripped (type arguments lost), interface/abstract method bodies are treated as empty stubs, exception types in `catch` clauses are dropped.

---

## Module Reference

| Module | Responsibility |
|--------|---------------|
| `parse.py` | C brace scanner, segment tree, statement classifier, expression parser integration |
| `expr.py` | Pratt parser for C expression strings → typed expression trees |
| `matrix.py` | Slot × statement dependency matrix; phi-node injection |
| `dag.py` | Data-flow DAG construction; SSA-style def-use edge building |
| `detect.py` | Clone detection algorithms (Types I–IV) |
| `kernel.py` | Expression tree evaluator (`VMKernel`) |
| `vm.py` | Tree-walking interpreter (`VM`); pointer model; execution trace |
| `models.py` | Core IR dataclasses (`Slot`, `Statement`, `Segment`) |
| `java_preprocess.py` | Java → near-C text transformation pipeline |
| `java_parse.py` | Java parse entry point; post-processing fixups |
| `utils.py` | File collection, single-file parsing, multi-file JSON merging |
| `cmds.py` | CLI subcommand implementations (`cmd_parse`, `cmd_detect`, `cmd_run`) |
| `main.py` | Argument parser; entry point |