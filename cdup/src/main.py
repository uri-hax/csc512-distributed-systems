import argparse
from .cli.cmds import cmd_parse, cmd_detect


if __name__ == "__main__":

    # Initialize parser
    parser = argparse.ArgumentParser(
        description="CDUP: C Code Duplication Detector",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Setup args for the parse subcommand
    parse_parser = subparsers.add_parser("parse", help="Parse C source files into structured JSON")
    parse_parser.add_argument("--src", required=True, help="Path to a .c file or directory")
    parse_parser.add_argument(
        "--include-comments",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include comments as statements (default: False)"
    )
    parse_parser.add_argument(
        "--include-includes",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include #include statements (default: False)"
    )
    parse_parser.add_argument(
        "--include-macros",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include macro statements like #define, #if, etc. (default: False)"
    )
    parse_parser.add_argument("--output", help="Write output to this file (default: stdout)")

    # Setup args for the detect subcommand
    detect_parser = subparsers.add_parser("detect", help="Detect clones from C source or parsed JSON")
    detect_parser.add_argument("--src", required=True, help="Path to a .c file, directory, or parsed .json")
    detect_parser.add_argument(
        "--type",
        nargs="+",
        type=int,
        choices=[1, 2],
        default=[1],
        help="Clone types to detect: 1, 2, or '1 2' for both (default: 1)"
    )
    detect_parser.add_argument(
        "--include-comments",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include comments as statements (default: False)"
    )
    detect_parser.add_argument(
        "--include-includes",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include #include statements (default: False)"
    )
    detect_parser.add_argument(
        "--include-macros",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include macro statements like #define, #if, etc. (default: False)"
    )
    detect_parser.add_argument(
        "--output",
        help="Write output to this file (default: stdout)"
    )
    detect_parser.add_argument(
        "--maximal",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Filter subsumed clone classes, keeping only maximal sequences (default: true)"
    )
    detect_parser.add_argument(
        "--min-length",
        type=int,
        default=2,
        dest="min_length",
        help="Minimum clone sequence length to report (default: 2)"
    )
    detect_parser.add_argument(
        "--max-freq",
        type=int,
        default=0,
        dest="max_freq",
        help="Skip statements appearing more than this many times (0 = no limit, default: 0)"
    )
    detect_parser.add_argument(
        "--filter-overlaps",
        action=argparse.BooleanOptionalAction,
        default=True,
        dest="filter_overlaps",
        help="Filter clone classes where all occurrences are in the same segment "
            "with overlapping ranges (default: true)"
    )

    args = parser.parse_args()

    # Execute appropriate command
    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "detect":
        cmd_detect(args)