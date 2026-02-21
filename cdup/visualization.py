from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.syntax import Syntax
from rich.prompt import Prompt
from analysis import calculate_generations

def collect_human_feedback(sorted_classes, codebase, files_data, mode="type1"):
    console = Console()
    TAG_COLORS = ["cyan", "magenta", "yellow", "green", "red", "blue", "orange1", "spring_green1"]
    
    generations = calculate_generations(sorted_classes)
    feedback_results = {}
    
    for i, (content, occurrences) in enumerate(sorted_classes, 1):
        console.clear()
        color = TAG_COLORS[(i - 1) % len(TAG_COLORS)]
        gen = generations.get(i, 1)
        header_text = Text(f"CLONE CLASS #{i} [GEN{gen}] ({len(occurrences)} occurrences):", style=f"bold {color}")
        console.print(header_text)
        
        sorted_occ = sorted(list(occurrences))
        for start, length in sorted_occ:
            start_info = codebase[start]
            end_info = codebase[start + length - 1]
            start_fname = start_info['filename']
            start_line = start_info['line_num']
            end_line = end_info['line_num']
            console.print(f"  - {start_fname}: Lines {start_line} to {end_line}")

        console.print("\n[bold]Snippet Content (Original):[/bold]")
        first_start, first_len = sorted_occ[0]
        ref_info = codebase[first_start]
        ref_end_info = codebase[first_start + first_len - 1]
        ref_fname = ref_info['filename']
        ref_start_line = ref_info['line_num']
        ref_end_line = ref_end_info['line_num']
        
        ref_file_content = next((f['content'] for f in files_data if f['filename'] == ref_fname), "")
        ref_raw_lines = ref_file_content.splitlines()
        snippet_lines = ref_raw_lines[ref_start_line-1 : ref_end_line]
        snippet_text = "\n".join(snippet_lines)
        
        syntax = Syntax(snippet_text, "c", theme="monokai", line_numbers=False)
        console.print(syntax)
        
        if mode == "type2":
            console.print("\n[bold]Parsed Structure (Type 2):[/bold]")
            type2_lines = []
            for idx in range(first_start, first_start + first_len):
                type2_lines.append(codebase[idx].get('t2_norm', ''))
            type2_text = "\n".join(type2_lines)
            syntax_t2 = Syntax(type2_text, "c", theme="monokai", line_numbers=False)
            console.print(syntax_t2)
            
        console.print("")
        
        choices = ["N", "T", "O"]
        choice = Prompt.ask("Classify this clone: [N]oise, [T]rue, [O]ther", choices=choices, default="T").upper()
        
        val_map = {"N": "NOISE", "T": "TRUE", "O": "OTHER"}
        feedback_results[i] = val_map[choice]
        
    console.clear()
    return feedback_results

def display_clone_classes(sorted_classes, codebase, files_data, mode="type1"):
    """
    Displays grouped clone classes with details and code snippets.
    
    Args:
        sorted_classes (list): From core.find_clones
        codebase (list): From data.preprocess_codebase
        files_data (list): From data.read_files
        mode (str): "type1" or "type2" to determine snippet content
    """
    console = Console()
    TAG_COLORS = ["cyan", "magenta", "yellow", "green", "red", "blue", "orange1", "spring_green1"]
    
    normalized_line_to_classes = {} # To return for file viz
    generations = calculate_generations(sorted_classes)
    
    for i, (content, occurrences) in enumerate(sorted_classes, 1):
        color = TAG_COLORS[(i - 1) % len(TAG_COLORS)]
        gen = generations.get(i, 1)
        header_text = Text(f"CLONE CLASS #{i} [GEN{gen}] ({len(occurrences)} occurrences):", style=f"bold {color}")
        console.print(header_text)
        
        sorted_occ = sorted(list(occurrences))
        for start, length in sorted_occ:
            # Retrieve start and end line info from normalized file
            start_info = codebase[start]
            end_info = codebase[start + length - 1]
            
            start_fname = start_info['filename']
            start_line = start_info['line_num']
            end_line = end_info['line_num']
            
            console.print(f"  - {start_fname}: Lines {start_line} to {end_line}")
            
            for idx in range(start, start + length):
                if idx not in normalized_line_to_classes:
                    normalized_line_to_classes[idx] = set()
                normalized_line_to_classes[idx].add(i)

        console.print("  Snippet Content:")
        
        # Reconstruct snippet
        first_start, first_len = sorted_occ[0]
        
        if mode == "type2":
            # For Type 2, show the normalized form from the codebase
            snippet_lines = []
            for idx in range(first_start, first_start + first_len):
                snippet_lines.append(codebase[idx].get('t2_norm', ''))
            snippet_text = "\n".join(snippet_lines)
            
        else:
            # For Type 1 (or default), show original source for readability
            ref_info = codebase[first_start]
            ref_end_info = codebase[first_start + first_len - 1]
            
            ref_fname = ref_info['filename']
            ref_start_line = ref_info['line_num']
            ref_end_line = ref_end_info['line_num']
            
            # Find the correct file content to extract snippet
            ref_file_content = next((f['content'] for f in files_data if f['filename'] == ref_fname), "")
            ref_raw_lines = ref_file_content.splitlines()
            
            # Extract lines (convert 1-based to 0-based index)
            snippet_lines = ref_raw_lines[ref_start_line-1 : ref_end_line]
            snippet_text = "\n".join(snippet_lines)
        
        syntax = Syntax(snippet_text, "c", theme="monokai", line_numbers=False)
        console.print(syntax)
        console.print("") 
        
    if not sorted_classes:
        console.print("No clones found.")
        
    return normalized_line_to_classes

def display_file_visualization(files_data, normalized_line_to_classes, codebase):
    """
    Renders the full file content with clone tags.
    """
    console = Console()
    TAG_COLORS = ["cyan", "magenta", "yellow", "green", "red", "blue", "orange1", "spring_green1"]
    
    console.print("\n[bold underline]=== VISUALIZATION OF CLONES IN CONTEXT ===[/bold underline]")
    
    # We need a map from (filename, line_idx_0_based) -> normalized_index
    # to efficiently look up tags while iterating lines.
    # codebase stores 1-based line numbers.
    file_line_map = {}
    for idx, item in enumerate(codebase):
        if item['line_num'] != -1: # Skip barriers
            file_line_map[(item['filename'], item['line_num'] - 1)] = idx

    for file_info in files_data:
        filename = file_info['filename']
        raw_lines = file_info['content'].splitlines()
        
        console.print(f"\n[bold]--- File: {filename} ---[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metadata", justify="right", style="dim")
        table.add_column("Code", style="none")

        for i, original_line in enumerate(raw_lines):
            line_num = i + 1
            tags_text = Text(f"Line {line_num:02d}: ", style="dim")
            
            # Lookup using the composite key (filename, raw_index)
            if (filename, i) in file_line_map:
                norm_idx = file_line_map[(filename, i)]
                if norm_idx in normalized_line_to_classes:
                    for class_id in sorted(list(normalized_line_to_classes[norm_idx])):
                        color = TAG_COLORS[(class_id - 1) % len(TAG_COLORS)]
                        tags_text.append(f"[#{class_id}]", style=f"bold {color}")
            
            syntax = Syntax(original_line, "c", theme="monokai", line_numbers=False, code_width=80)
            table.add_row(tags_text, syntax)

        console.print(table)
        
def display_summary(sorted_classes, analysis_rows=None):
    console = Console()
    TAG_COLORS = ["cyan", "magenta", "yellow", "green", "red", "blue", "orange1", "spring_green1"]
    
    console.print("\n")
    summary_table = Table(title="Clone Summary", box=None)
    summary_table.add_column("Clone #", justify="right", style="bold white")
    summary_table.add_column("Gen", justify="center", style="white")
    summary_table.add_column("Occurrences", justify="center", style="magenta")
    summary_table.add_column("Lines", justify="right", style="green")
    
    if analysis_rows:
        summary_table.add_column("Entropy", justify="right", style="yellow")
        summary_table.add_column("Unique Words", justify="right", style="blue")
        summary_table.add_column("Total Words", justify="right", style="cyan")
        summary_table.add_column("TTR", justify="right", style="blue")
        summary_table.add_column("ID Density", justify="right", style="yellow")
        summary_table.add_column("Complexity", justify="right", style="red")
        summary_table.add_column("File Spread", justify="right", style="magenta")
        summary_table.add_column("Dir Spread", justify="right", style="green")

    # Create a lookup for analysis data by clone_id
    analysis_map = {row['clone_id']: row for row in analysis_rows} if analysis_rows else {}
    generations = calculate_generations(sorted_classes)

    for i, (content, occurrences) in enumerate(sorted_classes, 1):
        _, length = next(iter(occurrences))
        color = TAG_COLORS[(i - 1) % len(TAG_COLORS)]
        gen = generations.get(i, 1)
        
        row_data = [
            Text(f"#{i}", style=f"bold {color}"),
            f"G{gen}",
            str(len(occurrences)),
            str(length)
        ]
        
        if analysis_rows and i in analysis_map:
            stats = analysis_map[i]
            row_data.append(str(stats['entropy']))
            row_data.append(str(stats['unique_words']))
            row_data.append(str(stats['total_words']))
            row_data.append(str(stats['ttr']))
            row_data.append(str(stats['identifier_density']))
            row_data.append(str(stats['cyclomatic_complexity']))
            row_data.append(str(stats['cross_file_spread']))
            row_data.append(str(stats['directory_spread']))
            
        summary_table.add_row(*row_data)
        
    console.print(summary_table)