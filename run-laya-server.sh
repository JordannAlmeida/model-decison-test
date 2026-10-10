#!/usr/bin/env bash
cd /home/linux/code/laya
git pull origin main

# Server settings read by compose.http.yaml (docs/http-api.md in the Laya repo).
# Torch threads = physical cores; oversubscribing logical cores is a large regression on CPU.
export LAYA_THREADS="${LAYA_THREADS:-$(lscpu -p=Core,Socket | grep -v '^#' | sort -u | wc -l)}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-$LAYA_THREADS}"
# The client pins the multilingual checkpoint (modelDecision/laya/integration.py): build it at
# startup instead of on the first request, and use it as the fallback when routing is left on.
export LAYA_PRELOAD="${LAYA_PRELOAD:-1}"
export LAYA_MODELS="${LAYA_MODELS:-multilingual}"
export LAYA_DEFAULT_MODEL="${LAYA_DEFAULT_MODEL:-multilingual}"
# Ceiling for the max_len / head_max_len the client sends per request.
export LAYA_MAX_TOKEN_BUDGET="${LAYA_MAX_TOKEN_BUDGET:-8192}"

docker compose -f compose.yaml -f compose.http.yaml up --build laya-serve
