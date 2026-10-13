from app.services.common import base_doc, new_id

CURRENT_VERSION = "1.0.0"
PREVIOUS_VERSION = "0.9.0"
SUPPORTED_VERSIONS = {CURRENT_VERSION, PREVIOUS_VERSION}

NAMES = {
    "user.registered",
    "user.login",
    "payment.succeeded",
    "product.imported",
    "selection.completed",
    "report.generated",
    "acquisition.started",
    "lead.discovered",
    "lead.qualified",
    "campaign.delivered",
    "campaign.opened",
    "campaign.replied",
    "deal.won",
    "recall.triggered",
    "kpi.updated",
    "ai.called",
    "digital_human.generated",
    "raas.settled",
}


def classify(event: dict) -> str:
    if event.get("version") not in SUPPORTED_VERSIONS or event.get("event") not in NAMES:
        return "dead_letter"
    return "accept"


def emit(store, tenant_id: str, name: str, payload: dict, created_by: str = "system") -> dict:
    if name not in NAMES:
        raise ValueError(f"unknown event {name}")
    doc = base_doc(
        tenant_id,
        created_by,
        id=new_id("evt"),
        event=name,
        version=CURRENT_VERSION,
        payload=payload,
    )
    return store.insert("events", doc)
