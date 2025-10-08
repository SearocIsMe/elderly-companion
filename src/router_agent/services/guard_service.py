
from fastapi import FastAPI
from pydantic import BaseModel
import yaml

app = FastAPI()
cfg = yaml.safe_load(open("config/guard.yml","r",encoding="utf-8"))

class AsrIn(BaseModel):
    text: str | None = None
    type: str = "asr"      # "asr" or "intent"
    intent: dict | None = None

def has_kw(text, kws):
    return any(k in text for k in kws)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "guard_service"}

@app.post("/guard/check")
def check(payload: AsrIn):
    if payload.type=="asr":
        t = (payload.text or "").strip()
        if has_kw(t, cfg.get("sos_keywords", [])):
            return {"decision":"dispatch_emergency","route":["sip","family","doctor"],"reason":"sos_keyword"}
        if has_kw(t, cfg.get("wakewords", [])):
            return {"decision":"wake","reason":"wakeword"}
        return {"decision":"pass_text"}    # hand over to intent
    else:
        it = payload.intent or {}
        if it.get("intent")=="assist.move":
            if it.get("speed")=="fast":
                return {"decision":"deny","reason":"speed_policy"}
        if it.get("intent")=="lock.unlock":
            return {"decision":"need_confirm","reason":"unlock requires consent",
                    "prompt":"需要打开门锁吗？请说“确认开锁”或“取消”。"}
        if it.get("intent")=="call.emergency":
            return {"decision":"dispatch_emergency","route":["sip","family","doctor"],"reason":"policy"}
        return {"decision":"allow"}
