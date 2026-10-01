from rollback.baseline import BASELINE_VERSION
from rollback.policy import decide, plan_for


def test_global_capacity_failure_returns_to_the_baseline():
    assert decide({"cpu": 0.95}) == "scale"
    plan = plan_for("scale")
    assert plan["target"] == BASELINE_VERSION
    assert plan["steps"] == ["config", "traffic", "migrate_down", "pitr_if_needed", "replay", "ai_rules", "verify"]
