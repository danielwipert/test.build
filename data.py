"""Synthetic factory + line data for the MVP demo."""
import json
import os
from datetime import datetime, timedelta

FACTORIES = {
    "FAC-01": {"name": "Northfield Apparel Plant", "location": "Tirupur, IN"}
}

LINES = {
    "LINE-A1": {
        "factory_id": "FAC-01",
        "product": "Knit T-Shirts",
        "current_metrics": {
            "throughput_pct": 91.0,
            "defect_rate_pct": 6.8,
            "downtime_minutes_today": 12.0,
        },
        "kpi_baselines": {
            "throughput_pct": 90.0,
            "defect_rate_pct": 2.5,
            "downtime_minutes_today": 15.0,
        },
        "safety_incidents_this_week": 0,
    },
    "LINE-B2": {
        "factory_id": "FAC-01",
        "product": "Woven Polo Shirts",
        "current_metrics": {
            "throughput_pct": 62.0,
            "defect_rate_pct": 3.1,
            "downtime_minutes_today": 78.0,
        },
        "kpi_baselines": {
            "throughput_pct": 88.0,
            "defect_rate_pct": 2.8,
            "downtime_minutes_today": 20.0,
        },
        "safety_incidents_this_week": 1,
    },
    "LINE-C3": {
        "factory_id": "FAC-01",
        "product": "Denim Jeans",
        "current_metrics": {
            "throughput_pct": 84.0,
            "defect_rate_pct": 2.2,
            "downtime_minutes_today": 18.0,
        },
        "kpi_baselines": {
            "throughput_pct": 85.0,
            "defect_rate_pct": 2.4,
            "downtime_minutes_today": 22.0,
        },
        "safety_incidents_this_week": 0,
    },
}

# Anchor incidents to a recent fixed date for deterministic demo
_ANCHOR = datetime(2026, 5, 8, 8, 0, 0)

INCIDENT_LOG = [
    {
        "timestamp": _ANCHOR.isoformat(),
        "line_id": "LINE-B2",
        "description": "Sewing station 4 jammed at shift start; cleared after 22 min.",
    },
    {
        "timestamp": (_ANCHOR - timedelta(hours=3)).isoformat(),
        "line_id": "LINE-A1",
        "description": "QC sampling flagged elevated stitch defects on lot 88-A.",
    },
    {
        "timestamp": (_ANCHOR - timedelta(days=1, hours=4)).isoformat(),
        "line_id": "LINE-C3",
        "description": "Indigo dye batch arrived 6 hours late from Supplier S-14.",
    },
]

PWOS = {
    "PWO-1001": {
        "line_id": "LINE-A1",
        "expected_start": (_ANCHOR - timedelta(hours=2)).isoformat(),
        "actual_start": (_ANCHOR - timedelta(hours=2)).isoformat(),
        "supplier": "S-09",
    },
    "PWO-1002": {
        "line_id": "LINE-B2",
        "expected_start": (_ANCHOR - timedelta(hours=1)).isoformat(),
        "actual_start": (_ANCHOR - timedelta(minutes=10)).isoformat(),
        "supplier": "S-12",
    },
    "PWO-1003": {
        "line_id": "LINE-C3",
        "expected_start": (_ANCHOR - timedelta(hours=10)).isoformat(),
        "actual_start": (_ANCHOR - timedelta(hours=4)).isoformat(),
        "supplier": "S-14",
    },
}


def get_line_snapshot(line_id: str) -> dict:
    """Return everything known about a line."""
    if line_id not in LINES:
        raise KeyError(f"Unknown line_id: {line_id}")
    line = LINES[line_id]
    factory = FACTORIES[line["factory_id"]]
    incidents = [i for i in INCIDENT_LOG if i["line_id"] == line_id]
    pwos = {k: v for k, v in PWOS.items() if v["line_id"] == line_id}
    return {
        "line_id": line_id,
        "factory_id": line["factory_id"],
        "factory_name": factory["name"],
        "product": line["product"],
        "current_metrics": line["current_metrics"],
        "kpi_baselines": line["kpi_baselines"],
        "safety_incidents_this_week": line["safety_incidents_this_week"],
        "recent_incidents": incidents,
        "pwos": pwos,
    }


def load_standards() -> list:
    path = os.path.join(os.path.dirname(__file__), "standards.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
