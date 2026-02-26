import os
import re

def read_files(file_paths):
    """
    Reads content from a list of file paths.
    
    Args:
        file_paths (list): List of file paths to read.
        
    Returns:
        list: List of dicts {'filename': str, 'content': str}
    """
    files_data = []
    for filepath in file_paths:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            files_data.append({
                'filename': filepath,
                'content': content
            })
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
    return files_data

def preprocess_codebase(files_data):
    """
    Normalizes code for Type 1 detection (strips comments and whitespace).
    Builds a flat 'codebase' list mapping indices to file locations.
    
    Args:
        files_data (list): List of dicts {'filename': str, 'content': str}
        
    Returns:
        tuple: (codebase, normalized_lines)
            - codebase: List of dicts {'filename': str, 'line_num': int, 'original': str}
            - normalized_lines: List of strings (the content to run detection on)
    """
    codebase = []
    normalized_lines = []
    
    comment_pattern = re.compile(r'(//.*)|(#.*)')
    
    for file_info in files_data:
        filename = file_info['filename']
        raw_lines = file_info['content'].splitlines()
        
        for idx, line in enumerate(raw_lines):
            original_num = idx + 1
            # Type 1 Normalization: Remove comments
            content = re.sub(comment_pattern, '', line)
            # Type 1 Normalization: Collapse whitespace
            content = " ".join(content.split())
            
            if content:
                # Add to flat representation
                codebase.append({
                    'filename': filename,
                    'line_num': original_num,
                    'original': line # Store original for context if needed, though we have files_data
                })
                normalized_lines.append(content)
        
        # Insert barrier to prevent cross-file clones
        barrier = f"__FILE_BARRIER_{filename}__"
        codebase.append({
            'filename': filename,
            'line_num': -1,
            'original': ""
        })
        normalized_lines.append(barrier)
        
    return codebase, normalized_lines
