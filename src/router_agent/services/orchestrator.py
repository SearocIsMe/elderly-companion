from fastapi import FastAPI
from pydantic import BaseModel
import requests, os

app = FastAPI()
GUARD_URL = os.getenv("GUARD_URL","http://guard:7002/guard/check")
INTENT_URL = os.getenv("INTENT_URL","http://intent:7001/parse_intent")
SMART_URL = os.getenv("SMART_URL","http://adapters:7003/smart-home/cmd")
SIP_URL = os.getenv("SIP_URL","http://adapters:7003/sip/call")

class AsrText(BaseModel):
    text: str

def post(url, json_data):
    r = requests.post(url, json=json_data, timeout=15)
    r.raise_for_status()
    return r.json()

@app.post("/asr_text")
def handle_asr(req: AsrText):
    g = post(GUARD_URL, {"type":"asr","text":req.text})
    if g["decision"]=="dispatch_emergency":
        post(SIP_URL, {"callee":"120","reason":"sos"})
        return {"status":"emergency_dispatched"}
    intent = post(INTENT_URL, {"text":req.text})
    g2 = post(GUARD_URL, {"type":"intent","intent":intent})
    if g2["decision"]=="need_confirm":
        return {"status":"need_confirm","prompt":g2.get("prompt")}
    if g2["decision"]=="deny":
        return {"status":"denied","reason":g2.get("reason")}
    if intent.get("intent")=="smart.home":
        res = post(SMART_URL, {"device":intent.get("device"),"action":intent.get("action"),"room":intent.get("room")})
        return {"status":"ok","adapter":"smart-home","result":res}
    if intent.get("intent")=="call.emergency":
        res = post(SIP_URL, {"callee":intent.get("callee","120"),"reason":intent.get("reason","unknown")})
        return {"status":"ok","adapter":"sip","result":res}
    return {"status":"ok","intent":intent}
