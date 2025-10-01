#!/usr/bin/env bash
curl -s http://localhost:7010/asr_text -H 'content-type: application/json'   -d '{"text":"小安 跟着我"}' | jq .
