from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.api.deps import bind, respond
from app.modules.ai_gateway import chat, contract_stub, predict_lead
from config.flags import require_flag

router = APIRouter(prefix="/api/v1")


class ChatIn(BaseModel):
    content: str
    context_id: str | None = None


class TextIn(BaseModel):
    text: str = ""


class LeadIn(BaseModel):
    lead_id: str


@router.post("/ai/chat")
def ai_chat(request: Request, body: ChatIn, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization, write=True)
    return respond(request, chat(store, settings, prof, body.content, body.context_id))


@router.post("/ai/embed")
def ai_embed(request: Request, body: TextIn, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization, write=True)
    return respond(request, contract_stub(store, settings, prof, "embed", body.text))


@router.post("/ai/rerank")
def ai_rerank(request: Request, body: TextIn, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization, write=True)
    return respond(request, contract_stub(store, settings, prof, "rerank", body.text))


@router.post("/ai/classify")
def ai_classify(request: Request, body: LeadIn, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization, write=True)
    return respond(request, predict_lead(store, settings, prof, body.lead_id))


@router.post("/ai/predict")
def ai_predict(request: Request, body: LeadIn, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization, write=True)
    return respond(request, predict_lead(store, settings, prof, body.lead_id))


@router.post("/ai/translate")
def ai_translate(request: Request, body: TextIn, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization, write=True)
    return respond(request, contract_stub(store, settings, prof, "translate", body.text))


@router.post("/ai/ocr")
def ai_ocr(request: Request, body: TextIn, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization, write=True)
    return respond(request, contract_stub(store, settings, prof, "ocr", body.text))


@router.post("/digital-human/generate")
def digital_human(request: Request, authorization: str | None = Header(default=None)):
    require_flag("digital_human")
    bind(request, authorization, write=True)
    return respond(request, {"generated": False})


@router.post("/ai/agent")
def ai_agent(request: Request, authorization: str | None = Header(default=None)):
    require_flag("ai.agent")
    bind(request, authorization, write=True)
    return respond(request, {"ran": False})


@router.post("/ai/finetune")
def ai_finetune(request: Request, authorization: str | None = Header(default=None)):
    require_flag("ai.finetune")
    bind(request, authorization, write=True)
    return respond(request, {"started": False})
