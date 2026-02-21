import csv
import math
import re
import json
import os
from collections import Counter

def calculate_entropy(text):
    if not text:
        return 0.0
    freq = Counter(text)
    length = len(text)
    entropy = 0.0
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

def calculate_generations(sorted_classes):
    """
    Identifies hierarchical relationships between clone classes based on both content and physical location.
    If Clone B's content is a contiguous sub-sequence of Clone A's content, 
    Clone B is only considered a descendant of Clone A if *all* of its physical occurrences
    are fully contained within the physical boundaries of Clone A's occurrences.
    
    Returns:
        dict: Mapping of clone_id (1-based) to generation number (1-based).
    """
    n = len(sorted_classes)
    parents = [[] for _ in range(n)]
    
    for i in range(n):
        content_i, occ_i = sorted_classes[i]
        len_i = len(content_i)
        
        for j in range(n):
            if i == j: continue
            content_j, occ_j = sorted_classes[j]
            len_j = len(content_j)
            
            # Fast check: Is class i even a content substring of class j?
            is_substring = False
            if len_i < len_j:
                for start in range(len_j - len_i + 1):
                    if content_j[start : start + len_i] == content_i:
                        is_substring = True
                        break
            
            if is_substring:
                # Content matches. Now check physical occurrences.
                # Every occurrence of 'i' must be fully inside *some* occurrence of 'j'
                all_i_contained = True
                for start_i, length_i in occ_i:
                    end_i = start_i + length_i
                    
                    # Does this specific occurrence of 'i' fall within any occurrence of 'j'?
                    contained_in_j = False
                    for start_j, length_j in occ_j:
                        end_j = start_j + length_j
                        
                        if start_i >= start_j and end_i <= end_j:
                            contained_in_j = True
                            break # Found a parent occurrence covering this child occurrence
                    
                    if not contained_in_j:
                        all_i_contained = False
                        break # Found an independent occurrence of 'i'
                
                if all_i_contained:
                    parents[i].append(j)
    
    generations = {}
    memo = {}

    def get_gen(idx):
        if idx in memo:
            return memo[idx]
        if not parents[idx]:
            memo[idx] = 1
            return 1
        
        res = 1 + max(get_gen(p) for p in parents[idx])
        memo[idx] = res
        return res

    for i in range(n):
        generations[i + 1] = get_gen(i)
        
    return generations

def analyze_clones(sorted_classes, clone_type, codebase, files_data=None):
    """
    Performs Exploratory Data Analysis (EDA) on detected clones and returns a list of dictionaries.
    Includes the file and line locations to allow cross-referencing with ground truth labels.
    """
    rows = []
    generations = calculate_generations(sorted_classes)
    
    # C keywords to exclude from identifier count
    c_keywords = {
        'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
        'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if',
        'int', 'long', 'register', 'return', 'short', 'signed', 'sizeof', 'static',
        'struct', 'switch', 'typedef', 'union', 'unsigned', 'void', 'volatile', 'while',
        'include', 'define', 'ifdef', 'endif', 'elif', 'else', 'ifndef', 'pragma'
    }

    # Cyclomatic complexity patterns
    complexity_pattern = re.compile(r'\b(if|for|while|case|catch)\b|\?|&&|\|\|')
    
    for i, (content_tuple, occurrences) in enumerate(sorted_classes, 1):
        # The content of the clone block
        full_text = " ".join(content_tuple)
        
        # Word analysis
        words = re.findall(r'\w+', full_text)
        total_words = len(words)
        unique_words = len(set(words))
        
        # Type-Token Ratio
        ttr = round(unique_words / total_words, 4) if total_words > 0 else 0.0
        
        # Identifier density
        identifiers = [w for w in words if not w.isdigit() and w not in c_keywords]
        identifier_density = round(len(identifiers) / total_words, 4) if total_words > 0 else 0.0
        
        # Cyclomatic complexity
        cyclomatic_complexity = len(re.findall(complexity_pattern, full_text))
        
        # Location mapping
        locations = []
        unique_files = set()
        unique_dirs = set()
        
        sorted_occ = sorted(list(occurrences))
        for start, length in sorted_occ:
            start_info = codebase[start]
            end_info = codebase[start + length - 1]
            file_path = start_info['filename']
            locations.append({
                "file": file_path,
                "start_line": start_info['line_num'],
                "end_line": end_info['line_num']
            })
            unique_files.add(file_path)
            unique_dirs.add(os.path.dirname(file_path))
            
        # Extract original and type2 code from the first occurrence
        first_start, first_length = sorted_occ[0]
        ref_info = codebase[first_start]
        ref_end_info = codebase[first_start + first_length - 1]
        
        original_code = ""
        if files_data:
            ref_fname = ref_info['filename']
            ref_start_line = ref_info['line_num']
            ref_end_line = ref_end_info['line_num']
            ref_file_content = next((f['content'] for f in files_data if f['filename'] == ref_fname), "")
            ref_raw_lines = ref_file_content.splitlines()
            snippet_lines = ref_raw_lines[ref_start_line-1 : ref_end_line]
            original_code = "\n".join(snippet_lines)
            
        type2_lines = []
        for idx in range(first_start, first_start + first_length):
            type2_lines.append(codebase[idx].get('t2_norm', ''))
        type2_code = "\n".join(type2_lines)
        
        row = {
            "clone_type": f"Type {clone_type}",
            "clone_id": i,
            "generation": generations.get(i, 1),
            "occurrences": len(occurrences),
            "line_length": len(content_tuple),
            "char_length": len(full_text),
            "entropy": round(calculate_entropy(full_text), 4),
            "unique_words": unique_words,
            "total_words": total_words,
            "ttr": ttr,
            "identifier_density": identifier_density,
            "cyclomatic_complexity": cyclomatic_complexity,
            "cross_file_spread": len(unique_files),
            "directory_spread": len(unique_dirs),
            "original_code": original_code,
            "type2_code": type2_code,
            "locations": json.dumps(locations)
        }
        rows.append(row)
        
    return rows