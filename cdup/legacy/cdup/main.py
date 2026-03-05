import argparse
import os
import sys
import time
from rich.console import Console

from .data import read_files, preprocess_codebase
from .core import find_clones
from .visualization import display_clone_classes, display_file_visualization, display_summary

def main():
    parser = argparse.ArgumentParser(description="CDUP: Simple Code Duplication Detector")
    parser.add_argument("path", help="Path to the directory or file to scan")
    parser.add_argument("--types", nargs="+", type=int, default=[1], 
                        help="Types of clones to detect (e.g., --types 1 2). Default is 1.")
    parser.add_argument("--merge", action="store_true",
                        help="Treat all input files as a single codebase for cross-file clone detection.")
    
    args = parser.parse_args()
    console = Console()

    if not os.path.exists(args.path):
        console.print(f"[red]Error: Path '{args.path}' does not exist.[/red]")
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
        console.print("[yellow]No C/H files found to scan.[/yellow]")
        return

    console.print(f"Scanning {len(files)} files for clones...\n")

    # Phase 1: Read Files
    files_data = read_files(files)
    
    # Phase 1: Preprocess (Type 1)
    # TODO: Add Type 2 preprocessing here when implemented
    codebase, normalized_lines = preprocess_codebase(files_data)

    if 1 in args.types:
        console.print("--- Running Type I Clone Detection ---")
        
        if args.merge:
            console.print("\n[bold]Mode: Merged (Cross-File Detection)[/bold]")
            
            start_time = time.perf_counter()
            sorted_classes = find_clones(normalized_lines)
            end_time = time.perf_counter()
            console.print(f"[dim]Detection took {end_time - start_time:.4f}s[/dim]\n")
            
            # Phase 4 & 5: Visualization
            normalized_line_to_classes = display_clone_classes(sorted_classes, codebase, files_data)
            display_file_visualization(files_data, normalized_line_to_classes, codebase)
            display_summary(sorted_classes)
            
        else:
            # Per-file detection: we need to slice the codebase and normalized_lines per file
            console.print("\n[bold]Mode: Per-File Detection[/bold]")
            all_results = []
            
            # We can't easily re-use the generic 'preprocess_codebase' output for per-file without
            # complex slicing because of the barriers. 
            # It's safer/cleaner to just re-process each file individually for this mode,
            # OR refactor preprocess_codebase to return grouped data.
            # For now, re-processing is negligible performance hit for the benefit of simplicity.
            
            for file_info in files_data:
                console.print(f"\nAnalyzing File: {file_info['filename']}")
                
                single_codebase, single_normalized = preprocess_codebase([file_info])
                sorted_classes = find_clones(single_normalized)
                
                for i, (content, occurrences) in enumerate(sorted_classes, 1):
                    _, length = next(iter(occurrences))
                    all_results.append({
                        "file": os.path.basename(file_info['filename']),
                        "clone_id": i,
                        "occurrences": len(occurrences),
                        "length": length
                    })
                    
                # Optional: Show detailed per-file results? 
                # The original code only showed the summary table for per-file mode.
                # Let's keep it consistent with original behavior for now.

            # Print Merged Summary Table for per-file mode
            if len(files) > 1 and all_results:
                console.print("\n")
                from rich.table import Table
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
