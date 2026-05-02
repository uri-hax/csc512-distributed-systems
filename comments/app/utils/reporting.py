from __future__ import annotations

from pathlib import PurePath
from typing import Any, Dict, List, Optional, Sequence, Tuple

POSITIVE_MESSAGES = {
    "all_meaningful": "Comments consistently explain intent and design decisions.",
    "mostly_meaningful": "Most comments add useful context for readers.",
    "professional_language": "Language is appropriate for an academic setting.",
    "good_length": "Comment length is generally clear and useful.",
    "good_coverage": "Comments are distributed across the file well.",
    "has_comments": "The file includes comments.",
    "documentation": "Documentation file detected and evaluated.",
    "text_present": "The document contains written content.",
    "thorough": "The document is comprehensive and insightful.",
    "adequate": "The document covers expected topics with reasonable detail.",
    "well_structured": "The document is clearly organized.",
    "references_code": "The write-up references implementation details.",
    "includes_diagrams": "The write-up includes visual aids.",
}

IMPROVEMENT_MESSAGES = {
    "mixed_quality": "Some comments are useful, but others are too superficial.",
    "mostly_trivial": "Most comments restate code rather than explain reasoning.",
    "all_trivial": "Comments do not provide meaningful insight yet.",
    "short_comments": "Many comments are very short; add more context where needed.",
    "long_comments": "Some comments are too long; tighten wording for clarity.",
    "partial_coverage": "Comment coverage is uneven; add notes in un-commented areas.",
    "low_coverage": "Very little of the file is documented; add explanatory comments.",
    "no_comments": "No comments were found in this file.",
    "text_empty": "The markdown file appears empty or contains placeholder content.",
    "superficial": "The document is present but lacks depth.",
    "minimal": "The document has minimal substantive content.",
    "some_structure": "The document has some structure but can be organized more clearly.",
    "unstructured": "The document needs stronger headings and organization.",
    "todos_present": "Resolve TODO/FIXME placeholders before submission.",
}

ALERT_MESSAGES = {
    "unprofessional_language": "One or more comments use language that is not course-appropriate.",
    "warning_hopelessness_language": "Possible hopelessness language detected in comments.",
    "warning_severe_distress_language": "Possible severe distress language detected in comments.",
    "warning_burnout_language": "Possible burnout language detected in comments.",
}

SUMMARY_PRIORITY = (
    ("no_comments", "This file currently has no comments, so your implementation intent is hard to follow."),
    ("all_trivial", "Comments are present but mostly do not explain meaningful reasoning."),
    ("mostly_trivial", "Many comments are too literal and should explain why decisions were made."),
    ("mixed_quality", "Comment quality is mixed: some notes help, others need more depth."),
    ("partial_coverage", "You have some documentation, but coverage is inconsistent across the file."),
    ("low_coverage", "Comment coverage is low and should be expanded to improve readability."),
    ("all_meaningful", "Comments are strong and consistently helpful for understanding the code."),
    ("mostly_meaningful", "Comments are mostly helpful and communicate intent in key areas."),
)

def _dedupe(items: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out

def _comment_density(lines: int, comment_lines: int) -> float:
    if lines <= 0:
        return 0.0
    return (comment_lines / lines) * 100.0

def _display_path(path: str, target: Optional[str]) -> str:
    if not path:
        return "unknown"
    if not target:
        return path

    path_parts = PurePath(path).parts
    target_parts = PurePath(target).parts

    if len(path_parts) >= len(target_parts) and path_parts[: len(target_parts)] == target_parts:
        rel_parts = path_parts[len(target_parts) :]
        if rel_parts:
            return str(PurePath(*rel_parts))
    return path

def _primary_summary(tags: Sequence[str]) -> str:
    tag_set = set(tags)
    for tag, summary in SUMMARY_PRIORITY:
        if tag in tag_set:
            return summary
    if "thorough" in tag_set:
        return "This document is detailed and demonstrates strong understanding."
    if "adequate" in tag_set:
        return "This document addresses core expectations with reasonable detail."
    if "minimal" in tag_set or "text_empty" in tag_set:
        return "This document needs substantially more content before submission."
    return "Feedback generated from available scoring tags."

def file_student_feedback(file_data: Dict[str, Any], target: Optional[str] = None) -> Dict[str, Any]:
    tags = _dedupe([str(t) for t in (file_data.get("tags") or [])])
    path = str(file_data.get("path") or "")
    lines = int(file_data.get("lines") or 0)
    comment_lines = int(file_data.get("comment_lines") or 0)
    density = _comment_density(lines, comment_lines)

    strengths = _dedupe([POSITIVE_MESSAGES[t] for t in tags if t in POSITIVE_MESSAGES])
    improvements = _dedupe([IMPROVEMENT_MESSAGES[t] for t in tags if t in IMPROVEMENT_MESSAGES])
    alerts = _dedupe([ALERT_MESSAGES[t] for t in tags if t in ALERT_MESSAGES])

    return {
        "path": path,
        "display_path": _display_path(path, target),
        "lines": lines,
        "comment_lines": comment_lines,
        "comment_density_pct": round(density, 1),
        "summary": _primary_summary(tags),
        "strengths": strengths,
        "improvements": improvements,
        "alerts": alerts,
    }

def _join_messages(messages: Sequence[str]) -> str:
    unique = _dedupe(messages)
    if not unique:
        return "None noted."
    return "; ".join(unique)

def _rollup(items: Sequence[Dict[str, Any]], key: str) -> List[str]:
    values: List[str] = []
    for item in items:
        for value in item.get(key, []):
            values.append(str(value))
    return _dedupe(values)

def submission_student_feedback(target: str, files: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    target = str(target or "")
    file_feedback = [file_student_feedback(f, target=target) for f in files]
    strengths = _rollup(file_feedback, "strengths")
    improvements = _rollup(file_feedback, "improvements")
    alerts = _rollup(file_feedback, "alerts")

    total_files = len(files)
    total_lines = sum(int(f.get("lines") or 0) for f in files)
    total_comment_lines = sum(int(f.get("comment_lines") or 0) for f in files)
    density = _comment_density(total_lines, total_comment_lines)

    lines: List[str] = []
    lines.append("Student Feedback Report")
    lines.append(f"Submission target: {target or 'unknown'}")
    lines.append(f"Files analyzed: {total_files}")
    lines.append(f"Total lines: {total_lines}")
    lines.append(f"Comment lines: {total_comment_lines} ({density:.1f}% density)")
    lines.append("")
    lines.append("Overall strengths:")
    lines.append(f"- {_join_messages(strengths)}")
    lines.append("Overall improvements:")
    lines.append(f"- {_join_messages(improvements)}")
    lines.append("Alerts:")
    lines.append(f"- {_join_messages(alerts)}")
    lines.append("")
    lines.append("File-by-file notes:")

    if not file_feedback:
        lines.append("- No analyzable files were found.")
    else:
        for idx, item in enumerate(file_feedback, start=1):
            lines.append(f"{idx}. {item['display_path']} ({item['comment_density_pct']}% comment density)")
            lines.append(f"   Summary: {item['summary']}")
            if item["strengths"]:
                lines.append(f"   Strengths: {_join_messages(item['strengths'])}")
            if item["improvements"]:
                lines.append(f"   Improvements: {_join_messages(item['improvements'])}")
            if item["alerts"]:
                lines.append(f"   Alerts: {_join_messages(item['alerts'])}")

    report_text = "\n".join(lines)

    return {
        "overview": {
            "total_files": total_files,
            "total_lines": total_lines,
            "total_comment_lines": total_comment_lines,
            "comment_density_pct": round(density, 1),
        },
        "strengths": strengths,
        "improvements": improvements,
        "alerts": alerts,
        "files": file_feedback,
        "raw_text": report_text,
    }
