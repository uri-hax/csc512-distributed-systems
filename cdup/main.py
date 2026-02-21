import argparse
import os
import sys
import time
import csv
from rich.console import Console

from data import read_files, preprocess_codebase
from core import find_clones
from visualization import display_clone_classes, display_file_visualization, display_summary, collect_human_feedback
from analysis import analyze_clones

def main():
    parser = argparse.ArgumentParser(description="CDUP: Simple Code Duplication Detector")
    parser.add_argument("path", help="Path to the directory or file to scan")
    parser.add_argument("--types", nargs="+", type=int, default=[1], 
                        help="Types of clones to detect (e.g., --types 1 2). Default is 1.")
    parser.add_argument("--merge", action="store_true",
                        help="Treat all input files as a single codebase for cross-file clone detection.")
    parser.add_argument("--analyze", type=str, metavar="OUTPUT_CSV",
                        help="Run Exploratory Data Analysis (EDA) on clones and save to the specified CSV file.")
    parser.add_argument("--human_feedback", action="store_true",
                        help="Interactively classify each clone as NOISE, TRUE, or OTHER.")
    
    args = parser.parse_args()
    console = Console()
    
    analysis_rows = []

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
    
    # Phase 1: Preprocess (Type 1 & 2)
    codebase, normalized_lines_t1, normalized_lines_t2 = preprocess_codebase(files_data)

    if 1 in args.types:
        console.print("--- Running Type I Clone Detection ---")
        
        if args.merge:
            console.print("\n[bold]Mode: Merged (Cross-File Detection)[/bold]")
            
            start_time = time.perf_counter()
            sorted_classes = find_clones(normalized_lines_t1)
            end_time = time.perf_counter()
            console.print(f"[dim]Detection took {end_time - start_time:.4f}s[/dim]\n")
            
            current_analysis = []
            if args.analyze:
                current_analysis = analyze_clones(sorted_classes, clone_type=1, codebase=codebase, files_data=files_data)
                
            if args.human_feedback:
                feedback = collect_human_feedback(sorted_classes, codebase, files_data, mode="type1")
                if args.analyze:
                    for row in current_analysis:
                        row['human_feedback'] = feedback.get(row['clone_id'], "")
                        
            if args.analyze:
                analysis_rows.extend(current_analysis)
            
            # Phase 4 & 5: Visualization
            normalized_line_to_classes = display_clone_classes(sorted_classes, codebase, files_data, mode="type1")
            display_file_visualization(files_data, normalized_line_to_classes, codebase)
            display_summary(sorted_classes, current_analysis if args.analyze else None)
            
        else:
            # Per-file detection: we need to slice the codebase and normalized_lines per file
            console.print("\n[bold]Mode: Per-File Detection[/bold]")
            all_results = []
            
            for file_info in files_data:
                console.print(f"\nAnalyzing File: {file_info['filename']}")
                
                single_codebase, single_normalized_t1, _ = preprocess_codebase([file_info])
                sorted_classes = find_clones(single_normalized_t1)
                
                current_analysis = []
                if args.analyze:
                    current_analysis = analyze_clones(sorted_classes, clone_type=1, codebase=single_codebase, files_data=[file_info])
                
                if args.human_feedback:
                    feedback = collect_human_feedback(sorted_classes, single_codebase, [file_info], mode="type1")
                    if args.analyze:
                        for row in current_analysis:
                            row['human_feedback'] = feedback.get(row['clone_id'], "")
                
                if args.analyze:
                    analysis_rows.extend(current_analysis)
                
                for i, (content, occurrences) in enumerate(sorted_classes, 1):
                    _, length = next(iter(occurrences))
                    all_results.append({
                        "file": os.path.basename(file_info['filename']),
                        "clone_id": i,
                        "occurrences": len(occurrences),
                        "length": length
                    })
                    
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

    if 2 in args.types:
        console.print("\n--- Running Type II Clone Detection (Blind Renaming) ---")
        
        if args.merge:
            console.print("\n[bold]Mode: Merged (Cross-File Detection)[/bold]")
            
            start_time = time.perf_counter()
            sorted_classes = find_clones(normalized_lines_t2)
            end_time = time.perf_counter()
            console.print(f"[dim]Detection took {end_time - start_time:.4f}s[/dim]\n")
            
            current_analysis = []
            if args.analyze:
                current_analysis = analyze_clones(sorted_classes, clone_type=2, codebase=codebase, files_data=files_data)
                
            if args.human_feedback:
                feedback = collect_human_feedback(sorted_classes, codebase, files_data, mode="type2")
                if args.analyze:
                    for row in current_analysis:
                        row['human_feedback'] = feedback.get(row['clone_id'], "")
                        
            if args.analyze:
                analysis_rows.extend(current_analysis)
            
            # Phase 4 & 5: Visualization
            normalized_line_to_classes = display_clone_classes(sorted_classes, codebase, files_data, mode="type2")
            display_file_visualization(files_data, normalized_line_to_classes, codebase)
            display_summary(sorted_classes, current_analysis if args.analyze else None)
            
        else:
            console.print("\n[bold]Mode: Per-File Detection[/bold]")
            all_results = []
            
            for file_info in files_data:
                console.print(f"\nAnalyzing File: {file_info['filename']}")
                
                single_codebase, _, single_normalized_t2 = preprocess_codebase([file_info])
                sorted_classes = find_clones(single_normalized_t2)
                
                current_analysis = []
                if args.analyze:
                    current_analysis = analyze_clones(sorted_classes, clone_type=2, codebase=single_codebase, files_data=[file_info])
                
                if args.human_feedback:
                    feedback = collect_human_feedback(sorted_classes, single_codebase, [file_info], mode="type2")
                    if args.analyze:
                        for row in current_analysis:
                            row['human_feedback'] = feedback.get(row['clone_id'], "")
                
                if args.analyze:
                    analysis_rows.extend(current_analysis)
                
                for i, (content, occurrences) in enumerate(sorted_classes, 1):
                    _, length = next(iter(occurrences))
                    all_results.append({
                        "file": os.path.basename(file_info['filename']),
                        "clone_id": i,
                        "occurrences": len(occurrences),
                        "length": length
                    })

            if len(files) > 1 and all_results:
                console.print("\n")
                from rich.table import Table
                table = Table(title="Merged Clone Summary (Type 2 Per-File Results)", box=None)
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

    if args.analyze and analysis_rows:
        fieldnames = ["clone_type", "clone_id", "generation", "occurrences", "line_length", "char_length", "entropy", "unique_words", "total_words", "ttr", "identifier_density", "cyclomatic_complexity", "cross_file_spread", "directory_spread", "original_code", "type2_code", "locations"]
        if args.human_feedback:
            fieldnames.append("human_feedback")
            
        with open(args.analyze, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(analysis_rows)
        console.print(f"\n[bold green]Analysis saved to {args.analyze}[/bold green]")

if __name__ == "__main__":
    main()