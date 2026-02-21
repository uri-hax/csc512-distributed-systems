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
        tuple: (codebase, normalized_lines_t1, normalized_lines_t2)
            - codebase: List of dicts {'filename': str, 'line_num': int, 'original': str, 't2_norm': str}
            - normalized_lines_t1: List of strings (Type 1 content)
            - normalized_lines_t2: List of strings (Type 2 content)
    """
    codebase = []
    normalized_lines_t1 = []
    normalized_lines_t2 = []
    
    comment_pattern = re.compile(r'(//.*)|(#.*)')
    
    for file_info in files_data:
        filename = file_info['filename']
        raw_lines = file_info['content'].splitlines()
        
        for idx, line in enumerate(raw_lines):
            original_num = idx + 1
            # Type 1 Normalization: Remove comments
            content = re.sub(comment_pattern, '', line)
            # Type 1 Normalization: Collapse whitespace
            content_t1 = " ".join(content.split())
            
            if content_t1:
                # Type 2 Normalization: Blind renaming (ignore literals/identifiers)
                content_t2 = normalize_type_2(content_t1)
                
                # Add to flat representation
                codebase.append({
                    'filename': filename,
                    'line_num': original_num,
                    'original': line,
                    't2_norm': content_t2
                })
                normalized_lines_t1.append(content_t1)
                normalized_lines_t2.append(content_t2)
        
        # Insert barrier to prevent cross-file clones
        barrier = f"__FILE_BARRIER_{filename}__"
        codebase.append({
            'filename': filename,
            'line_num': -1,
            'original': "",
            't2_norm': barrier
        })
        normalized_lines_t1.append(barrier)
        normalized_lines_t2.append(barrier)
        
    return codebase, normalized_lines_t1, normalized_lines_t2

def normalize_type_2(line_content):
    """
    Applies Type 2 normalization (Blind Renaming).
    Replaces literals and identifiers with generic tokens.
    Preserves C keywords and structural punctuation.
    """
    # 1. Strings: "Hello" -> ""
    line_content = re.sub(r'"([^"\\]|\\.)*"', '""', line_content)
    
    # 2. Chars: 'a' -> ''
    line_content = re.sub(r"'([^'\\]|\\.)*'", "''", line_content)
    
    # 3. Hex/Floats/Ints -> <NUM>
    line_content = re.sub(r'\b0x[0-9a-fA-F]+\b', '<NUM>', line_content)
    line_content = re.sub(r'\b\d+\.\d+([eE][-+]?\d+)?\b', '<NUM>', line_content)
    line_content = re.sub(r'\b\d+\b', '<NUM>', line_content)
    
    # 4. Identifiers -> <ID> (Skip Keywords)
    c_keywords = {
        'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
        'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if',
        'int', 'long', 'register', 'return', 'short', 'signed', 'sizeof', 'static',
        'struct', 'switch', 'typedef', 'union', 'unsigned', 'void', 'volatile', 'while',
        'include', 'define', 'ifdef', 'endif', 'elif', 'else', 'ifndef', 'pragma'
    }
    
    def replace_id(match):
        word = match.group(0)
        return word if word in c_keywords else '<ID>'
    
    line_content = re.sub(r'\b[a-zA-Z_]\w*\b', replace_id, line_content)
    
    return line_content