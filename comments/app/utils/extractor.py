from pathlib import Path

from app.core.structs import LANG_TO_COMMENT_TOKENS

def extract_comments(file_path):
    p = Path(file_path)

    try:
        src = p.read_text(errors='ignore')
    except Exception:
        return []
    
    tokens = LANG_TO_COMMENT_TOKENS.get(p.suffix.lower(), {'line': ['#', '//'], 'block': [('/*', '*/')]})
    line_tokens = tokens.get('line', [])
    block_tokens = tokens.get('block', [])
    quote_tokens = ['"""', "'''", '"', "'", '`']

    n, i, line, col = len(src), 0, 1, 0
    comments = []

    # Helper to advance through the source while tracking line/column positions
    def advance(to):
        nonlocal i, line, col
        segment = src[i:to]
        nl = segment.count('\n')

        if nl:
            line += nl
            col = len(segment.rsplit('\n', 1)[-1])
        else:
            col += len(segment)
        i = to

    while i < n:
        # Skip string literals in code
        matched = False 
        for q_token in quote_tokens:
            if src.startswith(q_token, i):
                end = src.find(q_token, i + len(q_token))
                advance(end + len(q_token) if end != -1 else n)
                matched = True
                break
        if matched:
            continue

        # Extract block comments
        for start, end_token in block_tokens:
            if src.startswith(start, i):
                start_line, start_col = line, col
                end = src.find(end_token, i + len(start))
                content = src[i + len(start):end] if end != -1 else src[i + len(start):]
                advance(end + len(end_token) if end != -1 else n)
                
                comments.append({
                    'text': content.strip(),
                    'line': start_line,
                    'column': start_col,
                    'type': 'block'
                })
                matched = True
                break
        if matched:
            continue

        # Extract line comments
        for line_token in line_tokens:
            if src.startswith(line_token, i):
                start_line, start_col = line, col
                end = src.find('\n', i)
                content = src[i + len(line_token):end] if end != -1 else src[i + len(line_token):]
                advance(end if end != -1 else n)

                comments.append({
                    'text': content.strip(),
                    'line': start_line,
                    'column': start_col,
                    'type': 'line'
                })
                break
        if matched:
            continue

        advance(i + 1)

    # Filter bash shebang
    if src.startswith("#!") and p.suffix.lower() in {".sh", ".bash"}:
        comments = [
            c for c in comments
            if not (c["type"] == "line" and c["line"] == 1)
        ]

    # Merge consecutive line comments
    if not comments:
        return comments

    merged = []
    for c in comments:
        if (
            merged
            and c.get('type') == 'line'
            and merged[-1].get('type') == 'line'
            and c['line'] == merged[-1]['line'] + 1
            and c['column'] == merged[-1]['column']
        ):
            merged[-1]["text"] += "\n" + c["text"]
        else:
            merged.append(c)

    # Normalize comment text
    for c in merged:
        c["text"] = " ".join(c["text"].split())

    return merged
