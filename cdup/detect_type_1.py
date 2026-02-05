import re
import time
from collections import defaultdict
from rich.console import Console
from rich.text import Text

def find_clones_inverted_index_step_by_step(source_code):
    """
    Detects Type 1 code clones using an inverted index and offset tracking.
    Groups results into clone classes and provides a highlighted visualization.
    """
    
    # --- PHASE 1: PREPROCESSING & NORMALIZATION ---
    print("\n[PHASE 1] Preprocessing & Normalization: Starting...")
    start_time = time.perf_counter()
    
    raw_lines = source_code.splitlines()
    # Holds (original_line_number, normalized_content)
    normalized_file = []
    # Pattern to strip single-line comments for C/Python style
    comment_pattern = re.compile(r'(//.*)|(#.*)')

    for idx, line in enumerate(raw_lines):
        original_num = idx + 1
        # Remove comments and collapse all whitespace to single spaces
        content = re.sub(comment_pattern, '', line)
        content = " ".join(content.split())
        
        # Only index lines that contain logical code
        if content:
            normalized_file.append((original_num, content))
            
    end_time = time.perf_counter()
    print(f"[PHASE 1] Finished: {len(raw_lines)} lines processed in {end_time - start_time:.4f}s.")

    # --- PHASE 2: BUILDING THE INVERTED INDEX ---
    print("\n[PHASE 2] Building Inverted Index: Starting...")
    start_time = time.perf_counter()
    
    # Map each unique line content to its indices in the normalized file
    inverted_index = defaultdict(list)
    for index, (orig_num, content) in enumerate(normalized_file):
        inverted_index[content].append(index)
        
    end_time = time.perf_counter()
    print(f"[PHASE 2] Finished: {len(normalized_file)} logical lines indexed in {end_time - start_time:.4f}s.")

    # --- PHASE 3: SCANNING FOR SEGMENTS (OFFSET METHOD) ---
    print("\n[PHASE 3] Scanning for Clone Segments: Starting...")
    start_time = time.perf_counter()
    
    # Track current matching sequences by their relative distance (offset)
    active_clones = {} 
    completed_clones = []

    for current_index, (orig_num, content) in enumerate(normalized_file):
        matches = inverted_index[content]
        current_offsets = set()
        
        # Calculate offsets for all occurrences of the current line
        for match_index in matches:
            if match_index <= current_index:
                continue # Only look forward to avoid duplicate pairs
            
            offset = match_index - current_index
            current_offsets.add(offset)
            
            # Increment length of sequence for this offset
            if offset in active_clones:
                active_clones[offset] += 1
            else:
                active_clones[offset] = 1
                
        # Identify offsets that did not match this line (broken chains)
        offsets_to_remove = []
        for offset, length in active_clones.items():
            if offset not in current_offsets:
                # Save sequence if it meets the minimum threshold (2 lines)
                if length >= 2:
                    start_A = current_index - length
                    start_B = start_A + offset
                    completed_clones.append((start_A, start_B, length))
                offsets_to_remove.append(offset)
        
        # Purge inactive offsets
        for offset in offsets_to_remove:
            del active_clones[offset]

    # Finalize clones that persist to the end of the file
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
    
    # Group pairwise matches into classes based on identical logical content
    clone_classes = defaultdict(set)

    for start_a, start_b, length in completed_clones:
        # Create a hashable representation of the clone content
        content_tuple = tuple(normalized_file[i][1] for i in range(start_a, start_a + length))
        
        # Insert both occurrences into the set for this content class
        clone_classes[content_tuple].add((start_a, length))
        clone_classes[content_tuple].add((start_b, length))

    highlight_indices = set()
    # Sort classes by frequency (number of occurrences)
    sorted_classes = sorted(clone_classes.items(), key=lambda x: len(x[1]), reverse=True)

    for i, (content, occurrences) in enumerate(sorted_classes, 1):
        print(f"CLONE CLASS #{i} ({len(occurrences)} occurrences):")
        
        # Output occurrences sorted by their position in the file
        sorted_occ = sorted(list(occurrences))
        for start, length in sorted_occ:
            line_start = normalized_file[start][0]
            line_end   = normalized_file[start + length - 1][0]
            print(f"  - Lines {line_start} to {line_end}")
            
            # Record indices for context-aware highlighting
            for idx in range(start, start + length):
                highlight_indices.add(idx)

        print("  Snippet Content:")
        for line in content:
            print(f"    {line}")
        print("")

    if not sorted_classes:
        print("No clones found.")

    end_time = time.perf_counter()
    print(f"[PHASE 4] Finished: {len(completed_clones)} pairs clustered in {end_time - start_time:.4f}s.")

    # --- PHASE 5: VISUALIZATION ---
    print("\n=== VISUALIZATION OF CLONES IN CONTEXT ===")
    start_time = time.perf_counter()
    
    console = Console()
    for i, (orig_num, content) in enumerate(normalized_file):
        # Render line with bold green style if it belongs to any clone class
        line_str = f"Line {orig_num:02d}: '{content}'"
        text = Text(line_str)
        if i in highlight_indices:
            text.stylize("bold green")
        console.print(text)
        
    end_time = time.perf_counter()
    print(f"\n[PHASE 5] Finished: Visualization rendered in {end_time - start_time:.4f}s.")