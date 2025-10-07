#!/usr/bin/env bash
curl -s http://localhost:7010/asr_text -H 'content-type: application/json'   -d '{"text":"把客厅的灯调亮一点"}' | jq .
