from fastapi import FastAPI
from pydantic import BaseModel
import requests, json, os
import json as _json

APP = FastAPI()
LLM_BACKEND = os.getenv("LLM_BACKEND", "vllm")     # vllm | llamacpp
LLM_URL = os.getenv("LLM_URL", "http://vllm:8000/v1/chat/completions")
SYSTEM_PROMPT = open("prompts/system_intent_zh.txt","r",encoding="utf-8").read()

class Req(BaseModel):
    text: str
    context: dict | None = None

def call_vllm(prompt):
    payload = {
      "model": os.getenv("LLM_MODEL","Qwen/Qwen2.5-3B-Instruct"),
      "messages":[{"role":"system","content":SYSTEM_PROMPT},
                  {"role":"user","content":prompt}],
      "temperature":0.2,
      "max_tokens":256,
    }
    r = requests.post(LLM_URL, json=payload, timeout=30)
    r.raise_for_status()
    resp = r.json()["choices"][0]["message"]["content"]
    return resp

def call_llamacpp(prompt):
    # Ultra-strict instruction: only JSON, must start with "{" and end with "}"
    strict_sys = (
        SYSTEM_PROMPT
        + "\n规则：只能输出一个 JSON 对象，不能输出任何解释或文字；"
        + "必须以 { 开始，以 } 结束；不要换行/前后缀；不要使用 Markdown；字段不确定就省略。"
    )
    body = {
        "prompt": f"<<SYS>>{strict_sys}<<SYS>>\n{prompt}\n",
        "temperature": 0.0,
        "n_predict": 256,
        # Cut common rambles if they appear
        "stop": ["```", "\n\n", "</s>", "<<SYS>>", "<<USER>>", "<<ASSISTANT>>"],
        "cache_prompt": True
    }
    r = requests.post(LLM_URL, json=body, timeout=60)
    try:
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"llamacpp HTTP {r.status_code}: {r.text[:300]}") from e
    return r.json().get("content","")



def json_only(s: str):
    # Find first '{' and walk to its matching '}' using a stack counter.
    start = s.find("{")
    if start == -1:
        raise ValueError("No JSON start '{' found")
    depth = 0
    end = None
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        raise ValueError("No matching '}' for JSON found")
    chunk = s[start:end+1]
    # Try parse
    return _json.loads(chunk)

@APP.post("/parse_intent")
def parse_intent(req: Req):
    raw = call_vllm(req.text) if LLM_BACKEND=="vllm" else call_llamacpp(req.text)
    try:
        parsed = json_only(raw)
    except Exception:
        parsed = {"intent":"ask.clarification","need":"format","ask":"请再说一遍，或更具体一点","confidence":0}
    return parsed

@APP.get("/health")
def health():
    return {"status": "healthy", "service": "guard_service"}