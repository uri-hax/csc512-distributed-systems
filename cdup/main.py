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
    parser.add_argument("--merge", action="store_true",
                        help="Treat all input files as a single codebase for cross-file clone detection.")
    
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

    # Prepare file data
    files_data = []
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            files_data.append({
                'filename': filepath,
                'content': content
            })
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

    if 1 in args.types:
        print("--- Running Type I Clone Detection ---")
        
        if args.merge:
            # Cross-file detection: pass all files at once
            print("\nMode: Merged (Cross-File Detection)")
            find_clones_inverted_index_step_by_step(files_data)
            
        else:
            # Per-file detection: pass one file at a time
            print("\nMode: Per-File Detection")
            all_results = []
            
            for file_info in files_data:
                print(f"\nAnalyzing File: {file_info['filename']}")
                
                # Wrap single file in list to match signature
                sorted_classes = find_clones_inverted_index_step_by_step([file_info])
                
                for i, (clone_content, occurrences) in enumerate(sorted_classes, 1):
                    _, length = next(iter(occurrences))
                    all_results.append({
                        "file": os.path.basename(file_info['filename']),
                        "clone_id": i,
                        "occurrences": len(occurrences),
                        "length": length
                    })

            # Print Merged Summary Table for per-file mode
            if len(files) > 1 and all_results:
                console = Console()
                print("\n")
                table = Table(title="Merged Clone Summary (Per-File Results)", box=None)
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