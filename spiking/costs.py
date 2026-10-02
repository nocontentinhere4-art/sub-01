"""Append-only GPU cost log (JSON lines). A `start` line is written at creation, the full record on stop.

A pod that was started but never stopped (crashed process) stays in `open_pods()` and is counted in the totals up
to now, at its recorded rate, so the budget caps stay conservative.
"""
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sleep import ROME
from state_io import append_jsonl


def _now():
    return datetime.now(timezone.utc)


def _parse(s):
    return datetime.fromisoformat(s)


class CostLog:
    def __init__(self, path, clock=_now):
        self.path = Path(path)
        self.clock = clock
        self._lock = threading.Lock()

    def _append(self, rec):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            append_jsonl(self.path, rec)

    def rows(self):
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue                                     # a torn last line from a crash
        return out

    def start(self, pod_id, name, gpu, cost_per_hr, purpose):
        self._append({"event": "start", "pod_id": pod_id, "name": name, "gpu": gpu,
                      "cost_per_hr": float(cost_per_hr or 0.0), "start": self.clock().isoformat(),
                      "purpose": purpose})

    def _split(self):
        """(starts by pod_id, closed records); a start without a stop is open."""
        starts, closed = {}, []
        for r in self.rows():
            if r.get("event") == "start":
                starts[r["pod_id"]] = r
            elif "stop" in r:
                starts.pop(r.get("pod_id"), None)
                closed.append(r)
        return starts, closed

    def stop(self, pod_id, reason):
        """Write the full record for a pod; hours and cost come from wall time and its hourly rate."""
        starts, _ = self._split()
        s = starts.get(pod_id)
        if s is None:
            return None
        end = self.clock()
        hours = max(0.0, (end - _parse(s["start"])).total_seconds() / 3600)
        rec = {"pod_id": pod_id, "name": s["name"], "gpu": s["gpu"], "cost_per_hr": s["cost_per_hr"],
               "start": s["start"], "stop": end.isoformat(), "hours": round(hours, 4),
               "cost_usd": round(hours * s["cost_per_hr"], 4), "reason": reason, "purpose": s["purpose"]}
        self._append(rec)
        return rec

    def open_pods(self):
        return list(self._split()[0].values())

    def _records(self):
        """Closed records plus open starts valued up to now."""
        starts, closed = self._split()
        out = list(closed)
        for s in starts.values():
            hours = max(0.0, (self.clock() - _parse(s["start"])).total_seconds() / 3600)
            out.append(s | {"hours": hours, "cost_usd": hours * s["cost_per_hr"]})
        return out

    def total_hours(self):
        return sum(r["hours"] for r in self._records())

    def hours_since(self, days):
        """GPU hours of pods started in the last `days` days (rolling window)."""
        cut = self.clock() - timedelta(days=days)
        return sum(r["hours"] for r in self._records() if _parse(r["start"]) >= cut)

    def total_usd(self):
        return sum(r["cost_usd"] for r in self._records())

    def hours_on(self, date):
        """GPU hours started on a local (Asia/Tokyo) date; `date` is a date or an ISO string."""
        d = date.isoformat() if hasattr(date, "isoformat") and not isinstance(date, str) else str(date)
        return sum(r["hours"] for r in self._records() if _parse(r["start"]).astimezone(ROME).date().isoformat() == d)

    def summary(self):
        return {"total_usd": round(self.total_usd(), 3), "hours": round(self.total_hours(), 3)}
