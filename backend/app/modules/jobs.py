from app.services.common import new_id, quota_reserve
from app.workers.execute import enqueue


def enqueue_tenant_job(store, prof: dict, job_type: str, payload: dict, module: str | None, idempotency_key: str | None):
    tenant_id = prof["tenant"]["id"]
    if idempotency_key:
        existing = store.find_global("jobs", tenant_id=tenant_id, idempotency_key=idempotency_key)
        if existing:
            return existing
    job_id = new_id("job")
    if module:
        quota_reserve(store, tenant_id, module, job_id)
    return enqueue(
        store,
        tenant_id,
        prof["user"]["id"],
        job_type,
        payload,
        job_id=job_id,
        idempotency_key=idempotency_key,
    )
