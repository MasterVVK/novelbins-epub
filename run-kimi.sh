#!/bin/bash
export USE_CUSTOM_LLM=true
export CUSTOM_LLM_PROVIDER="openai"
export CUSTOM_LLM_ENDPOINT="http://localhost:11434/v1"
export CUSTOM_LLM_MODEL_NAME="kimi-k2:1t-cloud"
export CUSTOM_LLM_TEMPERATURE=0.0

elc "$@"
