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
    else:
        destination.write_text("\n".join(f"- **{key}**: {value}" for key, value in report.items()), encoding="utf-8")
