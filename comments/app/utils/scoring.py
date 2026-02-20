from typing import Any, Dict, List

from app.core.config import WORD_RE, TRIVIAL, STRUCTURAL, UNPROF, TODO_RE

def _words(text: str) -> List[str]:
	return WORD_RE.findall((text or "").lower())

def _is_trivial(text: str) -> bool:
	if not text or len(_words(text)) == 0:
		return True
	if TRIVIAL.search(text):
		return True
	
	return len(_words(text)) == 1

def _is_meaningful(text: str) -> bool:
	if not text:
		return False
	if STRUCTURAL.search(text):
		return True

	words = _words(text)
	return len(words) >= 8

def _has_unprofessional(text: str) -> bool:
	return bool(UNPROF.search(text))

def score_submission(raw: Dict[str, Any]) -> Dict[str, Any]:
	files = raw.get("files", [])
	scored = [score_file(f) for f in files]
	cleaned = [{k: v for k, v in f.items() if k not in ("score", "subscores")} for f in scored]
	
	raw_clean = dict(raw)
	raw_clean["files"] = cleaned
	per_file = [{"path": f.get("path"), "tags": f.get("tags", [])} for f in scored]
	
	return {"submission": raw_clean, "tags": {"files": per_file}}

def score_file(f: Dict[str, Any]) -> Dict[str, Any]:
	lines = int(f.get("lines") or 0)
	comment_lines_count = int(f.get("comment_lines") or 0)
	code_lines = max(1, lines - comment_lines_count)
	comments = f.get("comments") or []

	# File level metrics
	comment_line_nums: List[int] = []
	todo_count = 0
	trivial = 0
	meaningful = 0
	unprofessional_flags = 0
	total_words = 0

	# Analyze each comment
	for c in comments:
		text = (c.get("text") or "")
		start = int(c.get("line") or 0)
		span = max(1, text.count("\n") + 1) if text else 1
		for ln in range(start, start + span):
			comment_line_nums.append(ln)
		if TODO_RE.search(text):
			todo_count += 1
		if _has_unprofessional(text):
			unprofessional_flags += 1
		if _is_trivial(text):
			trivial += 1
		if _is_meaningful(text):
			meaningful += 1
		total_words += len(_words(text))

	tags: List[str] = []

	# Comments: If the file has comments or not.
	if not comments:
		tags.append("no_comments")
	else:
		tags.append("has_comments")

	# Quality: trivial vs meaningful
	total_comments = len(comments)
	if total_comments:
		if meaningful == total_comments:
			tags.append("all_meaningful")
		elif trivial == total_comments:
			tags.append("all_trivial")
		else:
			if meaningful > trivial:
				tags.append("mostly_meaningful")
			elif trivial > meaningful:
				tags.append("mostly_trivial")
			else:
				tags.append("mixed_quality")

	# Professionalism: Presence of unprofessional language
	if unprofessional_flags:
		tags.append("unprofessional_language")
	else:
		tags.append("professional_language")

	# Length: average words per comment
	if total_comments:
		avg_words = total_words / total_comments if total_comments else 0
		lo, hi = (10, 30)
		if avg_words < lo:
			tags.append("short_comments")
		elif avg_words > hi:
			tags.append("long_comments")
		else:
			tags.append("good_length")

	# Density: comment lines vs code lines
	if comment_lines_count <= 0:
		tags.append("no_comment_density")
	else:
		# rough thresholds: high ~ >=20% of code lines, good ~ >=10%
		threshold_high = max(1, code_lines // 5)
		threshold_good = max(1, code_lines // 10)
		if comment_lines_count >= threshold_high:
			tags.append("high_density")
		elif comment_lines_count >= threshold_good:
			tags.append("good_density")
		else:
			tags.append("low_density")

	# Coverage: count how many code "zones" contain comments
	zone_size = 15
	code_lines = max(1, lines - comment_lines_count)
	num_zones = max(1, (code_lines + zone_size - 1) // zone_size)
	zones_covered = set()
	for ln in comment_line_nums:
		if ln <= 0:
			continue
		zone_idx = (ln - 1) // zone_size
		zones_covered.add(zone_idx)
	covered = len(zones_covered)
	if covered >= num_zones:
		tags.append("good_coverage")
	elif covered > 0:
		tags.append("partial_coverage")
	else:
		tags.append("low_coverage")

	# Todo: Are there any TODOs or similar tags in the comments?
	if todo_count > 0:
		tags.append("todos_present")

	seen = set()
	unique = []
	for t in tags:
		if t not in seen:
			seen.add(t)
			unique.append(t)

	out = dict(f)
	out.pop("score", None)
	out.pop("subscores", None)
	out["tags"] = unique

	return out
