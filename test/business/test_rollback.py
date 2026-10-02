from rollback.policy import decide, plan_for


def test_storage_and_traffic_rollback_include_pitr():
    assert decide({"schema_failed": True}) == "storage"
    assert decide({"kpi_gap": True}) == "storage"
    steps = plan_for("storage")["steps"]
    assert "migrate_down" in steps
    assert "pitr_if_needed" in steps
    assert "traffic" in plan_for("service")["steps"]
