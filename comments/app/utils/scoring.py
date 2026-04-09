from typing import Any, Dict, List
import os

from app.utils.llm import analyze_comments, analyze_markdown

def static_score_markdown(f: Dict[str, Any], text: str) -> Dict[str, Any]:
	tags: List[str] = ["documentation"]
	stripped = text.strip()

	if not stripped:
		tags.append("text_empty")
	else:
		tags.append("text_present")

	return f | {"tags": tags}

def static_score_code(f: Dict[str, Any]) -> Dict[str, Any]:
	comments = f.get("comments") or []
	tags: List[str] = []

	if not comments:
		tags.append("no_comments")
	else:
		tags.append("has_comments")

	return f | {"tags": tags}

def score_markdown(f: Dict[str, Any]) -> Dict[str, Any]:
	path = f.get("path") or ""
	text = f.get("comments")[0].get("text", "") if f.get("comments") else ""

	if not text.strip():
		return static_score_markdown(f, text)

	llm_result = analyze_markdown(path, text)
	if llm_result is not None:
		tags = ["documentation"]
		tags.extend(llm_result.get("tags", []))

		seen = set()
		unique = [t for t in tags if t not in seen and not seen.add(t)]

		return f | {"tags": unique}

	return static_score_markdown(f, text)

def score_code(f: Dict[str, Any]) -> Dict[str, Any]:
	path = f.get("path") or ""
	comments = f.get("comments") or []

	if not comments:
		return static_score_code(f)

	llm_result = analyze_comments(path, comments)
	if llm_result is not None:
		tags: List[str] = []
		tags.append("has_comments")
		tags.extend(llm_result.get("tags", []))

		lines = int(f.get("lines") or 0)
		comment_lines_count = int(f.get("comment_lines") or 0)
		comment_line_nums: List[int] = []

		for c in comments:
			text = (c.get("text") or "")
			start = int(c.get("line") or 0)
			span = max(1, text.count("\n") + 1) if text else 1
			for ln in range(start, start + span):
				comment_line_nums.append(ln)

		zone_size = 15
		code_lines = max(1, lines - comment_lines_count)
		num_zones = max(1, (code_lines + zone_size - 1) // zone_size)
		zones_covered = set()

		for ln in comment_line_nums:
			if ln <= 0:
				continue
			zones_covered.add((ln - 1) // zone_size)
		covered = len(zones_covered)
		if covered >= num_zones:
			tags.append("good_coverage")
		elif covered > 0:
			tags.append("partial_coverage")
		else:
			tags.append("low_coverage")

		seen = set()
		unique = [t for t in tags if t not in seen and not seen.add(t)]

		return f | {"tags": unique}
	return static_score_code(f)

def score_file(f: Dict[str, Any]) -> Dict[str, Any]:
	path = f.get("path") or ""
	_, ext = os.path.splitext(path)

	if ext.lower() in {'.md', '.markdown'}:
		return score_markdown(f)

	return score_code(f)
