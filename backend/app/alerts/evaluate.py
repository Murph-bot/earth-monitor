"""Rule evaluation against one freshly-written metric.

Two rule types:
- threshold:            params {op: lt|lte|gt|gte, value: float}
- baseline_deviation:   params {days: int=90, pct: float=0.2} — fires when the
                        value deviates from the AOI's own trailing mean by
                        more than pct. A field-specific baseline: harvest
                        phenology beats a global NDVI cutoff.

A rule only fires on scenes acquired on or after the day it was created:
the 30-day backfill of a new AOI must not replay old imagery as alerts.

Every fired rule writes one 'in_app' notification row. The
UNIQUE(alert_rule_id, scene_id) anchor makes re-analysis a no-op — the same
scene can never notify twice for the same rule. Daily values have no scene;
their anchor is (alert_rule_id, metric_date).
"""

import operator
from datetime import date
from typing import Any

import psycopg
import structlog
from psycopg.types.json import Jsonb

log = structlog.get_logger()

_OPS = {"lt": operator.lt, "lte": operator.le, "gt": operator.gt, "gte": operator.ge}
_OP_WORDS = {"lt": "below", "lte": "at or below", "gt": "above", "gte": "at or above"}


def _baseline_hit(
    conn: psycopg.Connection,
    aoi_id: object,
    scene_id: int | None,
    metric_name: str,
    value: float,
    on_date: date,
    params: dict[str, Any],
) -> tuple[bool, str]:
    days = int(params.get("days", 90))
    pct = float(params.get("pct", 0.2))
    if scene_id is None:  # daily source: history is the earlier days
        row = conn.execute(
            """SELECT avg(value), count(*) FROM daily_metrics
               WHERE aoi_id = %s AND metric_name = %s AND date < %s
                 AND date >= %s::date - (%s || ' days')::interval""",
            (aoi_id, metric_name, on_date, on_date, days),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT avg(value), count(*) FROM metrics
               WHERE aoi_id = %s AND metric_name = %s AND scene_id != %s
                 AND valid_pixel_pct >= 0.5
                 AND date >= %s::date - (%s || ' days')::interval""",
            (aoi_id, metric_name, scene_id, on_date, days),
        ).fetchone()
    mean, n = (row[0], row[1]) if row else (None, 0)
    if mean is None or mean == 0 or n < 3:
        return False, ""  # not enough history for a meaningful baseline
    deviation = abs(value - mean) / abs(mean)
    hit = deviation > pct
    detail = f"{deviation * 100:.0f}% off its {days}d baseline ({mean:.3f})"
    return hit, detail


def evaluate_metric(
    conn: psycopg.Connection,
    *,
    aoi_id: object,
    scene_id: int | None,
    sensor_id: str,
    metric_name: str,
    value: float,
    valid_pixel_pct: float,
    date: date,
) -> int:
    """Fire matching rules for one metric write; returns notifications sent."""
    rules = conn.execute(
        """SELECT r.id, r.user_id, r.rule_type, r.params, a.name
           FROM alert_rules r JOIN aois a ON a.id = r.aoi_id
           WHERE r.aoi_id = %s AND r.metric_name = %s AND r.enabled
             AND (r.sensor_id IS NULL OR r.sensor_id = %s)
             AND %s >= r.min_valid_pixel_pct
             AND %s >= r.created_at::date""",
        (aoi_id, metric_name, sensor_id, valid_pixel_pct, date),
    ).fetchall()

    fired = 0
    for rule_id, user_id, rule_type, params, aoi_name in rules:
        if rule_type == "threshold":
            op, threshold = params["op"], float(params["value"])
            hit = _OPS[op](value, threshold)
            detail = f"{_OP_WORDS[op]} {threshold}"
        else:
            hit, detail = _baseline_hit(conn, aoi_id, scene_id, metric_name, value, date, params)
        if not hit:
            continue
        title = f"{metric_name} {detail} — {aoi_name}"
        cur = conn.execute(
            """INSERT INTO notifications
                   (alert_rule_id, user_id, scene_id, metric_date, channel, title, body, payload)
               VALUES (%s, %s, %s, %s, 'in_app', %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            (
                rule_id,
                user_id,
                scene_id,
                date,
                title,
                f"{metric_name} = {value:.4f} on {date} "
                f"({valid_pixel_pct * 100:.0f}% valid pixels)",
                Jsonb(
                    {
                        "metric_name": metric_name,
                        "sensor_id": sensor_id,
                        "value": value,
                        "valid_pixel_pct": valid_pixel_pct,
                        "date": str(date),
                        "aoi_id": str(aoi_id),
                    }
                ),
            ),
        )
        fired += cur.rowcount
    if fired:
        log.info("alerts_fired", aoi_id=str(aoi_id), metric_name=metric_name, count=fired)
    return fired
