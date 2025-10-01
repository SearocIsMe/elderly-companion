from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class SmartCmd(BaseModel):
    device:str; action:str; room:str|None=None

@app.post("/smart-home/cmd")
def smart_home(cmd: SmartCmd):
    return {"status":"ok","echo":cmd.dict()}

class CallReq(BaseModel):
    callee:str; reason:str|None=None

@app.post("/sip/call")
def sip_call(req: CallReq):
    return {"status":"dialing","callee":req.callee}
