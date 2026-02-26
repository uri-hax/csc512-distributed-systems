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

def analyze_clones(sorted_classes, clone_type, codebase, files_data=None):
    """
    Performs Exploratory Data Analysis (EDA) on detected clones and returns a list of dictionaries.
    Includes the file and line locations to allow cross-referencing with ground truth labels.
    """
    rows = []
    
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