"""Alert rule evaluation — runs inside the analysis writer's transaction so
a crash can't leave a metric without its evaluated notifications, and the
(alert_rule_id, scene_id) unique key keeps reprocessing idempotent.
"""
