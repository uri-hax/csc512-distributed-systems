#!/usr/bin/env python3
import os

from app.core.structs import LANG_TO_COMMENT_TOKENS
from app.utils.extractor import extract_comments
from app.utils.scoring import score_file

exts = set(list(LANG_TO_COMMENT_TOKENS.keys())) | {'.md', '.markdown'}

# Analyze an entire submission 
def submission(target, ignored_dirs=None):
    total_files, total_lines, total_comments = 0, 0, 0
    result_files = []

    ignored_dirs = ignored_dirs or []
    ignored_set, ignored_abs = set(), set()
    for d in ignored_dirs:
        if os.path.isabs(d):
            ignored_abs.add(os.path.abspath(d))
        else:
            ignored_set.add(d.strip('/'))

    for root, dirs, files in os.walk(target, topdown=True):
        pruned = []
        for d in dirs:
            full = os.path.abspath(os.path.join(root, d))
            rel = os.path.relpath(full, start=target)
            if d in ignored_set or rel in ignored_set or full in ignored_abs:
                continue
            pruned.append(d)

        dirs[:] = pruned

        for f in files:
            _, ext = os.path.splitext(f)
            if ext.lower() in exts:
                path = os.path.join(root, f)
                file_details = file(path)

                total_files += 1
                total_lines += file_details.get('lines', 0)
                total_comments += file_details.get('comment_lines', 0)

                result_files.append(file_details)
    
    data = {
        'target': os.path.abspath(target),
        'summary': {
            'total_files': total_files,
            'total_lines': total_lines,
            'total_comment_lines': total_comments
        },
        'files': result_files
    }

    return data

# Analyze a single file
def file(target):
    lines = 0

    try:
        with open(target, 'r', errors='ignore') as fh:
            for _ in fh:
                lines += 1
    except Exception:
        return {'path': target, 'lines': 0, 'comment_lines': 0, 'comments': [], 'error': 'read_error'}

    try:
        comments_list = extract_comments(target)
    except Exception:
        comments_list = []

    comment_lines = 0
    for c in comments_list:
        t = c.get('text', '')
        if t:
            comment_lines += t.count('\n') + 1

    raw = {'path': target, 'lines': lines, 'comment_lines': comment_lines, 'comments': comments_list}
    return score_file(raw)

