"""Small, explainable experiments for content and publishing time.

The agent records the choices made for each post, then compares only groups
with enough observations. It recommends a schedule change; it never changes
the calendar from a noisy sample.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
import re
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def normalise(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def choose_slot_time(slot: dict, day: date) -> tuple[str, dict]:
    """Return a deterministic weekly time-window choice for an opt-in slot."""
    candidates = [str(t) for t in slot.get("time_candidates", []) if t]
    default = str(slot.get("time", ""))
    if not candidates:
        return default, {"active": False, "selected_time": default}
    if default not in candidates:
        candidates.insert(0, default)
    # Weeks, rather than run count, make a rerun produce the same schedule.
    monday = day - timedelta(days=day.weekday())
    index = (monday.toordinal() // 7) % len(candidates)
    selected = candidates[index]
    return selected, {
        "active": True,
        "selected_time": selected,
        "candidates": candidates,
        "week_index": index,
    }


def classify_hook(hook: str, evidence_type: str = "") -> str:
    plain = normalise(hook)
    if evidence_type == "case_study":
        return "case_study"
    if evidence_type == "framework":
        return "framework"
    if any(token in plain for token in ("cost", "budget", "pay", "price", "expensive")):
        return "cost"
    if any(token in plain for token in ("wrong", "mistake", "fails", "avoid")):
        return "correction"
    if any(token in plain for token in ("not", "versus", "vs")):
        return "distinction"
    if '"' in hook or "everyone says" in plain:
        return "objection"
    return "claim"


def post_metadata(post: dict, schedule_experiment: dict | None = None) -> dict:
    """Metadata that lets outcomes be compared without re-reading every post."""
    hook = post.get("hook", "")
    evidence = post.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    return {
        "hook_type": classify_hook(hook, str(evidence.get("type", ""))),
        "evidence_type": evidence.get("type", ""),
        "format": post.get("format", ""),
        "pillar": post.get("pillar", ""),
        "hook_words": len(hook.split()),
        "hook_characters": len(hook),
        "visual_treatment": (
            "kinetic_typography" if post.get("format") == "reel" else "carousel"
        ),
        "schedule": schedule_experiment or {},
    }


def published_metadata(content_root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """Index published post metadata by media ID and caption opening."""
    by_id: dict[str, dict] = {}
    by_hook: dict[str, dict] = {}
    for path in content_root.rglob("post.json") if content_root.exists() else []:
        try:
            post = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        metadata = post.get("experiment") or post_metadata(post)
        if media_id := str(post.get("media_id") or ""):
            by_id[media_id] = metadata
        caption = post.get("caption") or ""
        if first_line := normalise(caption.splitlines()[0] if caption else post.get("hook", "")):
            by_hook[first_line] = metadata
    return by_id, by_hook


def enrich_rows(rows: list[dict], content_root: Path) -> list[dict]:
    by_id, by_hook = published_metadata(content_root)
    for row in rows:
        metadata = by_id.get(str(row.get("id") or ""))
        if not metadata:
            metadata = by_hook.get(normalise(row.get("hook", "")))
        if metadata:
            row["experiment"] = metadata
    return rows


def _score(row: dict) -> float:
    """Save/send rate per 1,000 reached; a useful, volume-normalised signal."""
    reach = float(row.get("reach") or 0)
    if reach <= 0:
        return 0.0
    return 1000 * (float(row.get("saved") or 0) + float(row.get("shares") or 0)) / reach


def timing_recommendations(rows: list[dict], min_samples: int = 3) -> list[dict]:
    """Summarise comparable posting windows; never claim a winner prematurely."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        try:
            posted = datetime.fromisoformat(str(row.get("posted") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        # India has no daylight-saving changes, so a fixed offset is both
        # correct and portable to minimal Windows/Python installations.
        posted = posted.astimezone(IST)
        metadata = row.get("experiment")
        metadata = metadata if isinstance(metadata, dict) else {}
        label = posted.strftime("%a %H:00")
        if metadata.get("pillar") and metadata.get("format"):
            label += f" · {metadata['pillar']}/{metadata['format']}"
        grouped[label].append(row)

    out: list[dict] = []
    for window, group in sorted(grouped.items()):
        if len(group) < min_samples:
            continue
        scores = sorted(_score(row) for row in group)
        midpoint = len(scores) // 2
        median_score = (scores[midpoint] if len(scores) % 2 else
                        (scores[midpoint - 1] + scores[midpoint]) / 2)
        watches = [float(row.get("avg_watch_time") or 0) for row in group if row.get("avg_watch_time")]
        out.append({
            "window": window,
            "posts": len(group),
            "median_save_share_per_1000_reach": round(median_score, 2),
            "mean_avg_watch_time": round(sum(watches) / len(watches), 2) if watches else None,
        })
    return out


def timing_markdown(recommendations: list[dict]) -> str:
    if not recommendations:
        return (
            "# Timing experiments\n\n"
            "Not enough comparable posts yet. The agent will report a window only "
            "after it has at least three observations.\n"
        )
    lines = [
        "# Timing experiments",
        "",
        "These are descriptive results, not automatic schedule changes. Compare "
        "windows only after enough like-for-like posts exist.",
        "",
        "| IST window | Posts | Median saves + shares / 1,000 reach | Mean Reel watch time |",
        "|---|---:|---:|---:|",
    ]
    for result in recommendations:
        watch = "—" if result["mean_avg_watch_time"] is None else result["mean_avg_watch_time"]
        lines.append(
            f"| {result['window']} | {result['posts']} | "
            f"{result['median_save_share_per_1000_reach']} | {watch} |"
        )
    return "\n".join(lines) + "\n"
