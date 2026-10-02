from fastapi import APIRouter, BackgroundTasks, Header, Request
from pydantic import BaseModel

from app.api.deps import bind, respond
from app.modules.acquisition import enqueue_recall, open_acquisition_task, score_lead
from app.modules.jobs import enqueue_tenant_job
from app.modules.kpi_view import build_dashboard
from app.modules.selection import mark_acquired, present_report
from app.services.common import require_doc, search_catalog
from app.workers.execute import execute_job
from config.flags import load_flags, require_flag

router = APIRouter(prefix="/api/v1")


class CatalogIn(BaseModel):
    q: str = ""


class CsvIn(BaseModel):
    csv: str


class AnalyzeIn(BaseModel):
    product_id: str


class TaskIn(BaseModel):
    channel: str
    platform: str | None = None
    query: str = ""
    seed_analysis_id: str | None = None


class ScoreIn(BaseModel):
    lead_id: str


class RecallIn(BaseModel):
    lead_id: str
    trigger: str = "opened_without_reply"


def _schedule(background: BackgroundTasks, store, settings, job: dict) -> None:
    if job["status"] == "queued":
        background.add_task(execute_job, store, settings, job["id"])


@router.get("/flags")
def feature_flags(request: Request):
    """Public on/off map so the client can hide entries that return 501."""
    return respond(request, load_flags())


@router.post("/catalog/search")
def catalog_search(request: Request, body: CatalogIn, authorization: str | None = Header(default=None)):
    bind(request, authorization)
    return respond(request, {"items": search_catalog(body.q)})


@router.post("/products/import", status_code=202)
def import_products(
    request: Request,
    body: CsvIn,
    background: BackgroundTasks,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    settings, store, prof = bind(request, authorization, write=True)
    job = enqueue_tenant_job(store, prof, "product_import", {"csv": body.csv}, None, idempotency_key)
    _schedule(background, store, settings, job)
    return respond(request, {"job_id": job["id"], "status": job["status"]})


@router.post("/selection/analyze", status_code=202)
def selection_analyze(
    request: Request,
    body: AnalyzeIn,
    background: BackgroundTasks,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    settings, store, prof = bind(request, authorization, write=True, permission="analysis.write")
    require_doc(store, "products", body.product_id, prof["tenant"]["id"], "PRODUCT_NOT_FOUND", "商品不存在")
    job = enqueue_tenant_job(
        store,
        prof,
        "product_analysis",
        {"product_id": body.product_id},
        "analysis",
        idempotency_key,
    )
    _schedule(background, store, settings, job)
    return respond(request, {"job_id": job["id"], "status": job["status"]})


@router.get("/reports/{report_id}")
def get_report(report_id: str, request: Request, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization)
    report = require_doc(store, "analysis_reports", report_id, prof["tenant"]["id"], "REPORT_NOT_FOUND", "报告不存在")
    return respond(request, present_report(store, prof["tenant"]["id"], report))


@router.post("/reports/{report_id}/acquire")
def acquire_report(report_id: str, request: Request, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization, write=True)
    return respond(request, mark_acquired(store, prof["tenant"]["id"], prof["user"]["id"], report_id))


@router.post("/acquisition/tasks", status_code=202)
def acquisition_tasks(
    request: Request,
    body: TaskIn,
    background: BackgroundTasks,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    settings, store, prof = bind(request, authorization, write=True)
    task = open_acquisition_task(
        store,
        prof,
        channel=body.channel,
        platform=body.platform,
        query=body.query,
        seed_analysis_id=body.seed_analysis_id,
    )
    job = enqueue_tenant_job(
        store,
        prof,
        "lead_discovery",
        {
            "channel": body.channel,
            "platform": body.platform,
            "query": body.query,
            "seed_analysis_id": body.seed_analysis_id,
            "task_id": task["id"],
        },
        "discovery",
        idempotency_key,
    )
    _schedule(background, store, settings, job)
    return respond(request, {"job_id": job["id"], "status": job["status"], "task_id": task["id"]})


@router.post("/leads/score")
def leads_score(request: Request, body: ScoreIn, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization, write=True, permission="leads.write")
    return respond(request, score_lead(store, settings, prof, body.lead_id))


@router.post("/recall")
def recall(request: Request, body: RecallIn, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization, write=True)
    return respond(request, enqueue_recall(store, prof, lead_id=body.lead_id, trigger=body.trigger))


@router.get("/kpi/dashboard")
def kpi_dashboard(request: Request, window_days: int = 30, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization)
    return respond(request, build_dashboard(store, settings, prof, window_days))


@router.get("/events")
def list_events(request: Request, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization)
    return respond(request, store.query("events", tenant_id=prof["tenant"]["id"], limit=200))


@router.post("/selection/auto-deal")
def auto_deal(request: Request, authorization: str | None = Header(default=None)):
    require_flag("selection.auto_deal")
    bind(request, authorization, write=True)
    return respond(request, {"posted": False})


@router.post("/acquisition/social")
def acquisition_social(request: Request, authorization: str | None = Header(default=None)):
    require_flag("acquisition.social")
    bind(request, authorization, write=True)
    return respond(request, {"sent": False})


@router.post("/acquisition/ecommerce")
def acquisition_ecommerce(request: Request, authorization: str | None = Header(default=None)):
    require_flag("acquisition.ecommerce")
    bind(request, authorization, write=True)
    return respond(request, {"sent": False})


@router.post("/acquisition/expo")
def acquisition_expo(request: Request, authorization: str | None = Header(default=None)):
    require_flag("acquisition.expo")
    bind(request, authorization, write=True)
    return respond(request, {"sent": False})


@router.post("/acquisition/agency")
def acquisition_agency(request: Request, authorization: str | None = Header(default=None)):
    require_flag("acquisition.agency")
    bind(request, authorization, write=True)
    return respond(request, {"sent": False})


@router.post("/geo/seo")
def geo_seo(request: Request, authorization: str | None = Header(default=None)):
    require_flag("geo_seo")
    bind(request, authorization, write=True)
    return respond(request, {"published": False})


@router.post("/content/generate")
def content_generate(request: Request, authorization: str | None = Header(default=None)):
    bind(request, authorization, write=True)
    return respond(request, {"mode": "contract", "sent": False, "applied_to_money": False, "items": []})


@router.post("/raas/settle")
def raas_settle(request: Request, authorization: str | None = Header(default=None)):
    require_flag("raas")
    bind(request, authorization, write=True)
    return respond(request, {"posted": False})


@router.get("/global/health")
def global_health():
    from config.flags import load_flags

    flags = load_flags()
    return {
        "data": {
            "status": "placeholder",
            "global_multi_active": flags["global_multi_active"],
            "writes": False,
        }
    }
