import re
import time
from collections import defaultdict
from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.syntax import Syntax

def find_clones_inverted_index_step_by_step(files_data):
    """
    Detects Type 1 code clones using an inverted index and offset tracking.
    Supports single or multiple files.
    
    Args:
        files_data (list): List of dicts, each with 'filename' and 'content'.
        
    Groups results into clone classes and provides a tagged visualization.
    """
    console = Console()
    TAG_COLORS = ["cyan", "magenta", "yellow", "green", "red", "blue", "orange1", "spring_green1"]
    
    # --- PHASE 1: PREPROCESSING & NORMALIZATION ---
    print("\n[PHASE 1] Preprocessing & Normalization: Starting...")
    start_time = time.perf_counter()
    
    # normalized_file stores: (filename, original_line_num, content)
    normalized_file = []
    
    # Map: (filename, raw_line_index) -> normalized_index
    file_line_map = {}
    
    comment_pattern = re.compile(r'(//.*)|(#.*)')
    
    total_raw_lines = 0

    for file_info in files_data:
        filename = file_info['filename']
        raw_lines = file_info['content'].splitlines()
        total_raw_lines += len(raw_lines)
        
        for idx, line in enumerate(raw_lines):
            original_num = idx + 1
            content = re.sub(comment_pattern, '', line)
            content = " ".join(content.split())
            
            if content:
                file_line_map[(filename, idx)] = len(normalized_file)
                normalized_file.append((filename, original_num, content))
        
        # Insert a unique barrier to prevent clones from crossing file boundaries
        normalized_file.append((filename, -1, f"__FILE_BARRIER_{filename}__"))

    end_time = time.perf_counter()
    print(f"[PHASE 1] Finished: {total_raw_lines} lines processed in {end_time - start_time:.4f}s.")

    # --- PHASE 2: BUILDING THE INVERTED INDEX ---
    print("\n[PHASE 2] Building Inverted Index: Starting...")
    start_time = time.perf_counter()
    
    inverted_index = defaultdict(list)
    for index, (fname, orig_num, content) in enumerate(normalized_file):
        inverted_index[content].append(index)
        
    end_time = time.perf_counter()
    print(f"[PHASE 2] Finished: {len(normalized_file)} logical lines indexed in {end_time - start_time:.4f}s.")

    # --- PHASE 3: SCANNING FOR SEGMENTS (OFFSET METHOD) ---
    print("\n[PHASE 3] Scanning for Clone Segments: Starting...")
    start_time = time.perf_counter()
    
    active_clones = {} 
    completed_clones = []

    for current_index, (fname, orig_num, content) in enumerate(normalized_file):
        matches = inverted_index[content]
        current_offsets = set()
        
        for match_index in matches:
            if match_index <= current_index:
                continue 
            
            offset = match_index - current_index
            current_offsets.add(offset)
            
            if offset in active_clones:
                active_clones[offset] += 1
            else:
                active_clones[offset] = 1
                
        offsets_to_remove = []
        for offset, length in active_clones.items():
            if offset not in current_offsets:
                if length >= 2:
                    start_A = current_index - length
                    start_B = start_A + offset
                    completed_clones.append((start_A, start_B, length))
                offsets_to_remove.append(offset)
        
        for offset in offsets_to_remove:
            del active_clones[offset]

    for offset, length in active_clones.items():
         if length >= 2:
            start_A = len(normalized_file) - length
            start_B = start_A + offset
            completed_clones.append((start_A, start_B, length))

    end_time = time.perf_counter()
    print(f"[PHASE 3] Finished: {len(normalized_file)} iterations in {end_time - start_time:.4f}s.")
    
    # --- PHASE 4: CLUSTERING CLONE CLASSES ---
    print("\n[PHASE 4] Clustering Clone Classes: Starting...")
    start_time = time.perf_counter()
    
    clone_classes = defaultdict(set)
    # The content tuple should only include the text content, not metadata
    for start_a, start_b, length in completed_clones:
        content_tuple = tuple(normalized_file[i][2] for i in range(start_a, start_a + length))
        clone_classes[content_tuple].add((start_a, length))
        clone_classes[content_tuple].add((start_b, length))

    # Mapping: normalized_index -> set of clone class IDs
    normalized_line_to_classes = defaultdict(set)
    sorted_classes = sorted(clone_classes.items(), key=lambda x: len(x[1]), reverse=True)

    for i, (content, occurrences) in enumerate(sorted_classes, 1):
        color = TAG_COLORS[(i - 1) % len(TAG_COLORS)]
        header_text = Text(f"CLONE CLASS #{i} ({len(occurrences)} occurrences):", style=f"bold {color}")
        console.print(header_text)
        
        sorted_occ = sorted(list(occurrences))
        for start, length in sorted_occ:
            # Retrieve start and end line info from normalized file
            start_fname, start_line, _ = normalized_file[start]
            end_fname, end_line, _ = normalized_file[start + length - 1]
            
            print(f"  - {start_fname}: Lines {start_line} to {end_line}")
            
            for idx in range(start, start + length):
                normalized_line_to_classes[idx].add(i)

        print("  Snippet Content:")
        # Reconstruct snippet from original source code for better readability
        first_start, first_len = sorted_occ[0]
        ref_fname, ref_start_line, _ = normalized_file[first_start]
        ref_end_line = normalized_file[first_start + first_len - 1][1]
        
        # Find the correct file content to extract snippet
        ref_file_content = next(f['content'] for f in files_data if f['filename'] == ref_fname)
        ref_raw_lines = ref_file_content.splitlines()
        
        # Extract lines (convert 1-based to 0-based index)
        snippet_lines = ref_raw_lines[ref_start_line-1 : ref_end_line]
        snippet_text = "\n".join(snippet_lines)
        
        syntax = Syntax(snippet_text, "c", theme="monokai", line_numbers=False)
        console.print(syntax)
        print("") 

    if not sorted_classes:
        print("No clones found.")

    end_time = time.perf_counter()
    print(f"[PHASE 4] Finished: {len(completed_clones)} pairs clustered in {end_time - start_time:.4f}s.")

    # --- PHASE 5: VISUALIZATION ---
    print("\n=== VISUALIZATION OF CLONES IN CONTEXT ===")
    start_time = time.perf_counter()
    
    for file_info in files_data:
        filename = file_info['filename']
        raw_lines = file_info['content'].splitlines()
        
        print(f"\n--- File: {filename} ---")
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
    
    end_time = time.perf_counter()
    print(f"\n[PHASE 5] Finished: Visualization rendered in {end_time - start_time:.4f}s.")

    # --- SUMMARY TABLE ---
    print("\n")
    summary_table = Table(title="Clone Summary", box=None)
    summary_table.add_column("Clone #", justify="right", style="bold white") # Removed generic cyan style
    summary_table.add_column("Occurrences", justify="center", style="magenta")
    summary_table.add_column("Sequence Length", justify="right", style="green")

    for i, (content, occurrences) in enumerate(sorted_classes, 1):
        _, length = next(iter(occurrences))
        color = TAG_COLORS[(i - 1) % len(TAG_COLORS)]
        
        # Add row with colored Clone # cell
        summary_table.add_row(
            Text(f"#{i}", style=f"bold {color}"),
            str(len(occurrences)),
            str(length)
        )
        
    console.print(summary_table)

    return sorted_classes
