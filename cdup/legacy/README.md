# CDUP: Code Duplication Detection Tool

A high-performance Python utility for identifying Type 1 clones (exact matches ignoring comments and whitespace) in C source code using an inverted index and offset-based sequence tracking.

## Algorithm Overview

The detection engine operates in five distinct phases:

1.  **Normalization**: Source code is stripped of comments (single and multi-line) and all whitespace sequences are collapsed into single spaces. Empty lines are discarded to ensure continuity across vertical gaps.
2.  **Inverted Indexing**: Each unique normalized line is mapped to a list of its occurrence indices within the codebase.
3.  **Forward-Looking Offset Scanning**: The tool iterates through the normalized line sequence. For each line, it calculates the "offset" (distance) to all subsequent identical lines.
    *   **Offset Tracking**: Contiguous sequences of identical lines at the same relative distance are tracked as active clone candidates.
    *   **Maximal Matching**: Only the longest possible contiguous sequences are recorded; sub-segments of larger clones are suppressed to minimize noise.
4.  **Clone Class Clustering**: Pairwise matches are aggregated into "Clone Classes" based on identical logical content. Each class represents a unique snippet found in N locations.
5.  **Multi-File Aggregation**: When using `--merge`, files are concatenated with unique "barrier tokens" to prevent matches from spanning across file boundaries while allowing cross-file detection.

## CLI Usage

### Basic Usage
Scan a single file or directory for per-file clones:
```bash
python3 -m cdup.main path/to/source/
```

### Merged (Cross-File) Detection
Detect clones that exist across different files in the same directory:
```bash
python3 -m cdup.main path/to/source/ --merge
```

## Output Features

-   **Tagged Visualization**: Overlapping clones are identified by color-coded tags (e.g., `[#1]`, `[#2]`) aligned in a metadata column.
-   **Syntax Highlighting**: Source snippets and file context are rendered with C-syntax highlighting via the `rich` library.
-   **Execution Metrics**: Each phase reports iteration counts and wall-clock timing for performance diagnostics.
-   **Summary Tables**: A tabular view of all detected clone classes, their frequency, and their logical line length.

## Requirements

-   Python 3.8+
-   `rich` library
