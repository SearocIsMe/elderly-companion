#!/usr/bin/env bash
curl -s http://localhost:7010/asr_text -H 'content-type: application/json'   -d '{"text":"救命 我不舒服"}' | jq .
