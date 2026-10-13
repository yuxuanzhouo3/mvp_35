from config.flags import load_flags
from rollback.policy import decide, plan_for


def test_payment_failure_rolls_back_config_and_schema():
    assert load_flags()["payment.raas"] is False
    assert load_flags()["auth.mfa"] is False
    assert decide({"payment_failure_rate": 0.01}) == "payment"
    steps = plan_for("payment")["steps"]
    assert "config" in steps
    assert "migrate_down" in steps
