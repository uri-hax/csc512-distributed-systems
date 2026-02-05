import argparse
import os
import sys
from rich.console import Console
from rich.table import Table
from .detect_type_1 import find_clones_inverted_index_step_by_step

def main():
    parser = argparse.ArgumentParser(description="CDUP: Simple Code Duplication Detector")
    parser.add_argument("path", help="Path to the directory or file to scan")
    parser.add_argument("--types", nargs="+", type=int, default=[1], 
                        help="Types of clones to detect (e.g., --types 1 2). Default is 1.")
    
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"Error: Path '{args.path}' does not exist.")
        sys.exit(1)

    # Collect C files
    files = []
    if os.path.isfile(args.path):
        if args.path.endswith(('.c', '.h')):
            files.append(args.path)
    else:
        for root, _, filenames in os.walk(args.path):
            for filename in filenames:
                if filename.endswith(('.c', '.h')):
                    files.append(os.path.join(root, filename))

    if not files:
        print("No C/H files found to scan.")
        return

    print(f"Scanning {len(files)} files for clones...\n")

    # Aggregate results: list of (filename, class_id, occurrences_count, sequence_length)
    all_results = []

    if 1 in args.types:
        print("--- Running Type I Clone Detection ---")
        
        for filepath in files:
            print(f"\nAnalyzing File: {filepath}")
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                # Get structured results from the detector
                sorted_classes = find_clones_inverted_index_step_by_step(content)
                
                # Process results for the global summary
                for i, (clone_content, occurrences) in enumerate(sorted_classes, 1):
                    _, length = next(iter(occurrences))
                    all_results.append({
                        "file": os.path.basename(filepath),
                        "clone_id": i,
                        "occurrences": len(occurrences),
                        "length": length
                    })
                    
            except Exception as e:
                print(f"Error reading {filepath}: {e}")

    # Print Merged Summary Table if more than one file was processed
    if len(files) > 1 and all_results:
        console = Console()
        print("\n")
        table = Table(title="Merged Clone Summary (All Files)", box=None)
        table.add_column("File", style="bold white")
        table.add_column("Clone #", justify="right", style="cyan")
        table.add_column("Occurrences", justify="center", style="magenta")
        table.add_column("Sequence Length", justify="right", style="green")

        for row in all_results:
            table.add_row(
                row["file"],
                f"#{row['clone_id']}",
                str(row["occurrences"]),
                str(row["length"])
            )
        
        console.print(table)

if __name__ == "__main__":
    main()
