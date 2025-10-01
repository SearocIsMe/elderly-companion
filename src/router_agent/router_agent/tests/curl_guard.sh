#!/usr/bin/env bash
# 前置：唤醒
curl -s http://localhost:7002/guard/check -H 'content-type: application/json' \
  -d '{"type":"asr","text":"小安 在吗"}' | jq .

# 后置：意图复核
curl -s http://localhost:7002/guard/check -H 'content-type: application/json' \
  -d '{"type":"intent","intent":{"intent":"lock.unlock"}}' | jq .
