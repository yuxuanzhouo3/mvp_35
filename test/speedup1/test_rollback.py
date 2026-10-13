from rollback.policy import decide, plan_for


def test_cost_or_cpu_rolls_capacity_back():
    assert decide({"cost_over_budget": True}) == "scale"
    assert decide({"cpu": 0.9}) == "scale"
    assert decide({"error_rate": 0.001, "p95_ratio": 1, "delivery_rate": 0.99}) == "none"
    assert plan_for("scale")["steps"][0] == "config"
