"""Entry point for the CDUP command-line interface.

Exposes three subcommands:

- ``parse``  — parse C/Java source into structured IR JSON.
- ``detect`` — detect clones from source files or a parsed JSON file.
- ``run``    — execute a parsed JSON file with the interpreter VM.
"""

import argparse
from .cli.cmds import cmd_parse, cmd_detect, cmd_run


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="CDUP: C/Java Code Duplication Detector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- parse subcommand ---
    parse_parser = subparsers.add_parser("parse", help="Parse C source files into structured JSON")
    parse_parser.add_argument("--src", required=True, help="Path to a .c file or directory")
    parse_parser.add_argument(
        "--include-comments",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include comments as statements (default: False)",
    )
    parse_parser.add_argument(
        "--include-includes",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include #include statements (default: False)",
    )
    parse_parser.add_argument(
        "--include-macros",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include macro statements like #define, #if, etc. (default: False)",
    )
    parse_parser.add_argument(
        "--export-matrix-csv",
        nargs="?",
        const="matrix.csv",
        help="Export the dependency matrix as a CSV file. If no filename provided, defaults to matrix.csv.",
    )
    parse_parser.add_argument(
        "--export-dag-dot",
        nargs="?",
        const="dag.dot",
        help="Export the DAG as a Graphviz DOT file. If no filename provided, defaults to dag.dot.",
    )
    parse_parser.add_argument(
        "--export-3d-html",
        nargs="?",
        const="dag_3d.html",
        help="Export the DAG as an interactive 3D HTML visualization. Defaults to dag_3d.html.",
    )
    parse_parser.add_argument("--output", help="Write output to this file (default: stdout)")

    # --- detect subcommand ---
    detect_parser = subparsers.add_parser("detect", help="Detect clones from C source or parsed JSON")
    detect_parser.add_argument(
        "--src", required=True,
        help="Path to a .c file, directory, or parsed .json",
    )
    detect_parser.add_argument(
        "--type",
        nargs="+",
        type=int,
        choices=[1, 2, 3, 4],
        default=[1],
        help="Clone types to detect: 1, 2, 3, 4, or any combination (default: 1). "
             "Type 3 = near-miss clones, Type 4 = semantic/structural clones.",
    )
    detect_parser.add_argument(
        "--include-comments",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include comments as statements when parsing inline (default: False)",
    )
    detect_parser.add_argument(
        "--include-includes",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include #include statements when parsing inline (default: False)",
    )
    detect_parser.add_argument(
        "--include-macros",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include macro statements when parsing inline (default: False)",
    )
    detect_parser.add_argument(
        "--output",
        help="Write output to this file (default: stdout)",
    )
    detect_parser.add_argument(
        "--maximal",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Filter subsumed clone classes, keeping only maximal sequences (default: true)",
    )
    detect_parser.add_argument(
        "--min-length",
        type=int,
        default=2,
        dest="min_length",
        help="Minimum clone sequence length to report (default: 2)",
    )
    detect_parser.add_argument(
        "--max-freq",
        type=int,
        default=0,
        dest="max_freq",
        help="Skip statements appearing more than this many times (0 = no limit, default: 0)",
    )
    detect_parser.add_argument(
        "--filter-overlaps",
        action=argparse.BooleanOptionalAction,
        default=True,
        dest="filter_overlaps",
        help="Filter clone classes where all occurrences are in the same segment "
             "with overlapping ranges (default: true)",
    )
    detect_parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.7,
        dest="similarity_threshold",
        help="Minimum similarity for Type III near-miss clones (default: 0.7)",
    )
    detect_parser.add_argument(
        "--min-length-type3",
        type=int,
        default=3,
        dest="min_length_type3",
        help="Minimum clone sequence length for Type III detection (default: 3)",
    )
    detect_parser.add_argument(
        "--export-3d-html",
        nargs="?",
        const="clone_dag_3d.html",
        help="Export an interactive 3D DAG+clone visualization. Defaults to clone_dag_3d.html.",
    )

    # --- run subcommand ---
    run_parser = subparsers.add_parser("run", help="Execute a parsed JSON file with the VM")
    run_parser.add_argument(
        "--src",
        required=True,
        help="Path to a parsed .json file (produced by the parse command)",
    )
    run_parser.add_argument(
        "--fn",
        default="main",
        help="Function to execute (default: main)",
    )
    run_parser.add_argument(
        "--args",
        nargs="*",
        default=[],
        help="Positional arguments to --fn as JSON values (e.g. '[1,2,3]' '[4,5,6]' 3)",
    )
    run_parser.add_argument(
        "--max-unroll",
        type=int,
        default=10_000,
        dest="max_unroll",
        help="Maximum loop iterations before capping (default: 10000)",
    )
    run_parser.add_argument(
        "--output",
        nargs="?",
        const="",
        help="Append trace to parsed JSON and write it out. "
             "If no path given, writes back to --src. "
             "If omitted entirely, prints program output to stdout.",
    )

    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "detect":
        cmd_detect(args)
    elif args.command == "run":
        cmd_run(args)