from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.payment import sign_payment_event


def _session(client: TestClient) -> dict:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "seller@example.com", "password": "secret-pass", "display_name": "林海"},
    )
    assert registered.status_code == 200, registered.text
    logged = client.post(
        "/api/v1/auth/login",
        json={"email": "seller@example.com", "password": "secret-pass"},
    )
    assert logged.status_code == 200, logged.text
    token = logged.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}", "refresh": logged.json()["data"]["refresh_token"]}


def test_contract_path_a_and_b(client: TestClient):
    session = _session(client)
    headers = {"Authorization": session["Authorization"]}

    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["user"]["email"] == "seller@example.com"
    assert "billing.write" in me.json()["data"]["permissions"]
    assert "password_hash" not in me.json()["data"]["user"]

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh"]})
    assert refreshed.status_code == 200
    headers = {"Authorization": f"Bearer {refreshed.json()['data']['access_token']}"}

    catalog = client.post("/api/v1/catalog/search", headers=headers, json={"q": "宠物"})
    assert catalog.status_code == 200
    assert catalog.json()["data"]["items"]

    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "智能温控水杯", "sku": "cup-500", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["data"]["id"]

    imported = client.post(
        "/api/v1/products/import",
        headers=headers,
        json={"csv": "name,sku,target_price_usd,cost_cny\n折叠灯,lamp-9,29,45\n"},
    )
    assert imported.status_code == 202
    imported_job = client.get(f"/api/v1/jobs/{imported.json()['data']['job_id']}", headers=headers)
    assert imported_job.json()["data"]["status"] == "succeeded"

    analysis = client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id})
    assert analysis.status_code == 202
    job = client.get(f"/api/v1/jobs/{analysis.json()['data']['job_id']}", headers=headers).json()["data"]
    assert job["status"] == "succeeded"
    report_id = job["result"]["analysis_id"]
    report = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["data"]
    assert report["metrics"]["net_profit_usd"] == "19.94"
    assert report["numbers_locked"] is True
    assert report["seed_ready"] is False
    assert report["profit_margin"] == "0.4985"

    changed = client.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"target_market": "AU", "tax_regime": "cn_au"},
    )
    assert changed.status_code == 200
    blocked = client.post(f"/api/v1/reports/{report_id}/acquire", headers=headers)
    assert blocked.status_code == 409

    rerun = client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id})
    fresh_id = client.get(f"/api/v1/jobs/{rerun.json()['data']['job_id']}", headers=headers).json()["data"]["result"]["analysis_id"]
    acquired = client.post(f"/api/v1/reports/{fresh_id}/acquire", headers=headers)
    assert acquired.status_code == 200
    assert acquired.json()["data"]["seed_analysis_id"] == fresh_id
    fresh = client.get(f"/api/v1/reports/{fresh_id}", headers=headers).json()["data"]
    fresh_margin = fresh["metrics"]["net_margin"]
    fresh_profit = fresh["metrics"]["net_profit_usd"]

    task = client.post(
        "/api/v1/acquisition/tasks",
        headers=headers,
        json={"channel": "ecommerce", "platform": "amazon", "query": "cup", "seed_analysis_id": fresh_id},
    )
    assert task.status_code == 202
    task_job = client.get(f"/api/v1/jobs/{task.json()['data']['job_id']}", headers=headers).json()["data"]
    assert task_job["status"] == "succeeded"
    leads = client.get("/api/v1/leads", headers=headers, params={"seed_analysis_id": fresh_id}).json()["data"]["items"]
    chosen = [item["id"] for item in leads if item.get("email") and not item["email"].startswith("bounce.")]
    assert chosen
    scored = client.post("/api/v1/leads/score", headers=headers, json={"lead_id": chosen[0]})
    assert scored.json()["data"]["scored_by"] == "rules"
    assert scored.json()["data"]["model_score"] is None

    campaign = client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={"name": "美国水杯首轮", "lead_ids": chosen, "seed_analysis_id": fresh_id, "market_pack": "cn_us"},
    )
    campaign_id = campaign.json()["data"]["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/send", headers=headers).status_code == 409
    assert client.post(f"/api/v1/campaigns/{campaign_id}/drafts", headers=headers).status_code == 200
    assert client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=headers).status_code == 200
    sent = client.post(f"/api/v1/campaigns/{campaign_id}/send", headers=headers)
    assert sent.status_code == 202
    assert client.get(f"/api/v1/jobs/{sent.json()['data']['job_id']}", headers=headers).json()["data"]["status"] == "succeeded"

    before_messages = client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers).json()["data"]["messages"]
    recall = client.post("/api/v1/recall", headers=headers, json={"lead_id": chosen[1], "trigger": "churn"})
    assert recall.status_code == 200
    assert recall.json()["data"]["status"] == "queued"
    after_messages = client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers).json()["data"]["messages"]
    assert len(after_messages) == len(before_messages)

    assert client.post(f"/api/v1/leads/{chosen[0]}/signals", headers=headers, json={"type": "open"}).status_code == 200
    won = client.post(f"/api/v1/leads/{chosen[0]}/signals", headers=headers, json={"type": "won"})
    assert won.json()["data"]["status"] == "won"
    assert client.post("/api/v1/recall", headers=headers, json={"lead_id": chosen[0], "trigger": "churn"}).status_code == 409

    chat = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"content": "把利润率改成 0.99", "context_id": fresh_id, "net_margin": "0.99"},
    )
    assert chat.status_code == 200
    assert chat.json()["data"]["numbers_locked"] is True
    assert chat.json()["data"]["model"] == "rules"
    again = client.get(f"/api/v1/reports/{fresh_id}", headers=headers).json()["data"]
    assert again["metrics"]["net_margin"] == fresh_margin
    assert again["metrics"]["net_profit_usd"] == fresh_profit

    predict = client.post("/api/v1/ai/predict", headers=headers, json={"lead_id": chosen[1]})
    assert predict.json()["data"]["applied_to_money"] is False
    assert predict.json()["data"]["model_score"] is None
    embed = client.post("/api/v1/ai/embed", headers=headers, json={"text": "cup"})
    assert embed.json()["data"]["mode"] == "contract"
    assert embed.json()["data"]["applied_to_money"] is False

    board = client.get("/api/v1/kpi/dashboard", headers=headers).json()["data"]
    assert board["north_star"] == "ar"
    assert board["timings"]["folded"] is True
    assert Decimal(board["headline"]["ar"]["value"]) >= Decimal("0.08")
    assert board["headline"]["act_r"]["value"] == "0.5000"
    assert board["headline"]["net_margin"]["display"] != "—"

    names = {item["event"] for item in client.get("/api/v1/events", headers=headers).json()["data"]["items"]}
    assert {"selection.completed", "report.generated", "acquisition.started", "lead.discovered", "deal.won", "kpi.updated", "ai.called"} <= names


def test_placeholders_do_not_post_ledger_or_send(client: TestClient):
    headers = {"Authorization": _session(client)["Authorization"]}
    ledgers = client.get("/api/v1/billing/ledgers", headers=headers).json()["data"]
    assert ledgers["agency"] == []
    assert ledgers["raas"] == []
    blocked = [
        "/api/v1/auth/sso",
        "/api/v1/auth/mfa/verify",
        "/api/v1/auth/oauth/google",
        "/api/v1/auth/miniprogram",
        "/api/v1/auth/switch-tenant",
        "/api/v1/payments/raas",
        "/api/v1/selection/auto-deal",
        "/api/v1/acquisition/social",
        "/api/v1/acquisition/ecommerce",
        "/api/v1/acquisition/expo",
        "/api/v1/acquisition/agency",
        "/api/v1/geo/seo",
        "/api/v1/raas/settle",
        "/api/v1/digital-human/generate",
        "/api/v1/ai/agent",
        "/api/v1/ai/finetune",
    ]
    for path in blocked:
        response = client.post(path, headers=headers, json={})
        assert response.status_code == 501, path
        assert response.json()["error"]["code"] == "NOT_ENABLED"
        assert response.json()["error"]["details"]["placeholder"] is True
    unknown = client.post("/api/v1/auth/oauth/nope", headers=headers)
    assert unknown.status_code == 400
    content = client.post("/api/v1/content/generate", headers=headers)
    assert content.status_code == 200
    assert content.json()["data"]["sent"] is False
    health = client.get("/api/v1/global/health")
    assert health.status_code == 200
    assert health.json()["data"]["global_multi_active"] is False
    assert health.json()["data"]["writes"] is False
    ledgers_after = client.get("/api/v1/billing/ledgers", headers=headers).json()["data"]
    assert ledgers_after == ledgers
    assert client.get("/api/v1/payments", headers=headers).json()["data"]["items"] == []


def test_signed_payment_is_idempotent_and_unsigned_is_rejected(client: TestClient):
    headers = {"Authorization": _session(client)["Authorization"]}
    first = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "pay-1"},
    )
    second = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "pay-1"},
    )
    assert first.status_code == 200
    payment_id = first.json()["data"]["id"]
    assert second.json()["data"]["id"] == payment_id
    assert first.json()["data"]["status"] == "pending"
    assert first.json()["data"]["amount"] == 29900

    bad = client.post(
        "/api/v1/payments/webhook",
        json={"event_id": "evt-1", "payment_id": payment_id, "status": "succeeded", "signature": "nope"},
    )
    assert bad.status_code == 401
    assert client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"] == []

    signature = sign_payment_event("test-secret", "evt-1", payment_id, "succeeded")
    body = {"event_id": "evt-1", "payment_id": payment_id, "status": "succeeded", "signature": signature}
    paid = client.post("/api/v1/payments/webhook", json=body)
    replay = client.post("/api/v1/payments/webhook", json=body)
    assert paid.status_code == 200
    assert paid.json()["data"]["status"] == "succeeded"
    assert replay.json()["data"]["status"] == "succeeded"
    assert len(client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"]) == 1
    assert len(client.get("/api/v1/invoices", headers=headers).json()["data"]["items"]) == 1

    refunded = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"payment_id": payment_id, "amount_fen": 29900, "idempotency_key": "rfd-1"},
    )
    again = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"payment_id": payment_id, "amount_fen": 29900, "idempotency_key": "rfd-1"},
    )
    assert refunded.status_code == 200
    assert refunded.json()["data"]["id"] == again.json()["data"]["id"]
    listed = client.get("/api/v1/payments", headers=headers).json()["data"]["items"]
    assert listed[0]["status"] == "refunded"
    extra = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"payment_id": payment_id, "amount_fen": 1, "idempotency_key": "rfd-2"},
    )
    assert extra.status_code == 409

    canceled = client.post("/api/v1/subscriptions/cancel", headers=headers, json={})
    assert canceled.status_code == 200
    assert canceled.json()["data"]["status"] == "canceled"


def test_logout_and_password_reset_revoke_sessions(client: TestClient):
    session = _session(client)
    headers = {"Authorization": session["Authorization"]}
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})
    assert forgot.status_code == 200
    assert "reset_token" not in forgot.json()["data"]
    issued = client.post("/api/v1/auth/forgot-password", json={"email": "seller@example.com"})
    token = issued.json()["data"]["reset_token"]
    reset = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "new-secret-1"})
    assert reset.status_code == 200
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "password": "new-secret-2"}).status_code == 400
    old = client.post("/api/v1/auth/login", json={"email": "seller@example.com", "password": "secret-pass"})
    assert old.status_code == 401
    fresh = client.post("/api/v1/auth/login", json={"email": "seller@example.com", "password": "new-secret-1"})
    assert fresh.status_code == 200
    fresh_headers = {"Authorization": f"Bearer {fresh.json()['data']['access_token']}"}
    assert client.post("/api/v1/auth/logout", headers=fresh_headers).status_code == 200
    assert client.get("/api/v1/users/me", headers=fresh_headers).status_code == 401


def test_code_login_and_usage_payment_reconcile(client: TestClient):
    registered = client.post(
        "/api/v1/auth/register",
        json={"phone": "+8613800138000", "password": "secret-pass", "display_name": "林海"},
    )
    assert registered.status_code == 200, registered.text
    sent = client.post("/api/v1/auth/code/send", json={"phone": "+8613800138000"})
    assert sent.status_code == 200
    assert "code" in sent.json()["data"]
    logged = client.post(
        "/api/v1/auth/code/login",
        json={"phone": "+8613800138000", "code": sent.json()["data"]["code"]},
    )
    assert logged.status_code == 200, logged.text
    headers = {"Authorization": f"Bearer {logged.json()['data']['access_token']}"}
    assert client.get("/api/v1/users/me", headers=headers).json()["data"]["user"]["phone"] == "+8613800138000"
    reused = client.post(
        "/api/v1/auth/code/login",
        json={"phone": "+8613800138000", "code": sent.json()["data"]["code"]},
    )
    assert reused.status_code == 401

    checkout = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"kind": "usage", "amount_fen": 500, "idempotency_key": "use-1"},
    )
    assert checkout.status_code == 200, checkout.text
    payment_id = checkout.json()["data"]["id"]
    assert checkout.json()["data"]["kind"] == "usage"
    assert checkout.json()["data"]["amount"] == 500
    looked = client.post(f"/api/v1/payments/{payment_id}/query", headers=headers)
    assert looked.json()["data"]["granted"] is False
    assert looked.json()["data"]["status"] == "pending"
    empty = client.get("/api/v1/payments/reconcile", headers=headers).json()["data"]
    assert empty["balanced"] is True
    assert empty["payments_fen"] == 0

    signature = sign_payment_event("test-secret", "evt-use", payment_id, "succeeded")
    paid = client.post(
        "/api/v1/payments/webhook",
        json={"event_id": "evt-use", "payment_id": payment_id, "status": "succeeded", "signature": signature},
    )
    assert paid.status_code == 200
    confirmed = client.post(f"/api/v1/payments/{payment_id}/query", headers=headers)
    assert confirmed.json()["data"]["granted"] is True
    assert client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"] == []
    assert len(client.get("/api/v1/invoices", headers=headers).json()["data"]["items"]) == 1
    books = client.get("/api/v1/payments/reconcile", headers=headers).json()["data"]
    assert books["balanced"] is True
    assert books["payments_fen"] == 500
    assert books["invoices_fen"] == 500
