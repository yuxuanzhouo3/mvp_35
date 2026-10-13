from rollback.policy import decide, plan_for


def test_compliance_risk_rolls_ai_back_to_rules():
    assert decide({"ai_compliance": True}) == "ai"
    assert "ai_rules" in plan_for("ai")["steps"]
