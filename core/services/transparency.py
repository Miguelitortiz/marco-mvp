"""Section 4.6 transparency report generated from append-only JSONL events."""
import json
import hashlib
from collections import Counter
from pathlib import Path


def transparency_report(path: str | Path) -> dict[str, object]:
    source = Path(path)
    if not source.exists():
        events = []
    else:
        events = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    phases = Counter(event.get("phase") for event in events)
    citations = sum(len(event.get("payload", {}).get("citations", [])) for event in events)
    actors = Counter(event.get("actor") for event in events)
    human_edits = sum(event.get("action_type") == "human_edit" for event in events)
    rollbacks = sum(event.get("action_type") == "rollback" for event in events)
    evidence_inspections = sum(event.get("action_type") == "evidence_inspected" for event in events)
    alerts_attended = sum(
        bool(event.get("payload", {}).get("alert_attended"))
        for event in events
    )
    llm_words = sum(
        len(str(event.get("payload", {}).get("text", "")).split())
        for event in events if str(event.get("actor", "")).upper() == "LLM"
    )
    human_words = sum(
        len(str(event.get("payload", {}).get("text", "")).split())
        for event in events if str(event.get("actor", "")).upper() == "HUMAN"
    )
    generated_words = llm_words + human_words
    return {
        "section": "4.6",
        "events": len(events),
        "phases": dict(phases),
        "tokens": {
            "input": sum(event.get("input_tokens") or 0 for event in events),
            "output": sum(event.get("output_tokens") or 0 for event in events),
        },
        "latency_ms": sum(event.get("latency_ms") or 0 for event in events),
        "citations": citations,
        "evidence": citations,
        "actors": dict(actors),
        "llm_events": actors.get("llm", 0) + actors.get("LLM", 0),
        "human_events": actors.get("human", 0) + actors.get("HUMAN", 0),
        "llm_text_words": llm_words,
        "human_text_words": human_words,
        "authorship_words": {
            "llm": llm_words,
            "human": human_words,
            "total": generated_words,
        },
        "llm_word_share": round(llm_words / generated_words, 4) if generated_words else 0.0,
        "human_word_share": round(human_words / generated_words, 4) if generated_words else 0.0,
        "human_edits": human_edits,
        "reviews": sum(event.get("action_type") in {"review", "human_review"} for event in events),
        "alerts_attended": alerts_attended,
        "evidence_inspections": evidence_inspections,
        "rollbacks": rollbacks,
        "review_time_ms": sum(
            event.get("latency_ms") or 0 for event in events
            if event.get("actor", "").lower() == "human"
        ),
        "chain_verified": _verify_chain(events),
    }


def _verify_chain(events: list[dict[str, object]]) -> bool:
    previous = None
    for event in events:
        if event.get("previous_event_hash") != previous:
            return False
        body = {key: event.get(key) for key in (
            "event_id", "timestamp", "project_id", "phase", "actor", "action_type",
            "payload", "input_tokens", "output_tokens", "latency_ms",
            "previous_event_hash",
        )}
        if isinstance(body["timestamp"], str) and body["timestamp"].endswith("+00:00"):
            body["timestamp"] = body["timestamp"][:-6] + "Z"
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != event.get("event_hash"):
            return False
        previous = event.get("event_hash")
    return True


def export_report(report: dict[str, object], path: str | Path, fmt: str = "json") -> None:
    destination = Path(path)
    if fmt == "json":
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt in {"markdown", "md"}:
        lines = ["# Informe de transparencia", ""]
        for key, value in report.items():
            lines.append(f"- **{key.replace('_', ' ').capitalize()}**: {value}")
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        raise ValueError(f"Unsupported report format: {fmt}")
