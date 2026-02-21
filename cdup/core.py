from collections import defaultdict

def find_clones(normalized_lines):
    """
    Generic Type 1 Clone Detection Algorithm.
    
    Args:
        normalized_lines (list[str]): List of normalized code lines.
        
    Returns:
        list: Sorted list of clone classes. 
              Each class is a tuple: (content_tuple, set_of_occurrences).
              Each occurrence is a tuple: (start_index, length).
    """
    # --- PHASE 2: INVERTED INDEX ---
    inverted_index = defaultdict(list)
    for index, content in enumerate(normalized_lines):
        inverted_index[content].append(index)
        
    # --- PHASE 3: OFFSET SCANNING ---
    active_clones = {} 
    completed_clones = []

    for current_index, content in enumerate(normalized_lines):
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

    # Flush remaining active clones
    for offset, length in active_clones.items():
         if length >= 2:
            start_A = len(normalized_lines) - length
            start_B = start_A + offset
            completed_clones.append((start_A, start_B, length))
    
    # --- PHASE 4: CLUSTERING ---
    clone_classes = defaultdict(set)
    for start_a, start_b, length in completed_clones:
        # Extract the content tuple to identify unique clone logical content
        content_tuple = tuple(normalized_lines[i] for i in range(start_a, start_a + length))
        clone_classes[content_tuple].add((start_a, length))
        clone_classes[content_tuple].add((start_b, length))

    # Sort by number of occurrences (descending)
    sorted_classes = sorted(clone_classes.items(), key=lambda x: len(x[1]), reverse=True)

    return sorted_classes