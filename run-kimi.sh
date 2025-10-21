#!/bin/bash

echo " Обновляем easy-llm-cli до последней версии..."
npm install -g easy-llm-cli

export USE_CUSTOM_LLM=true
export CUSTOM_LLM_PROVIDER="openai"
export CUSTOM_LLM_ENDPOINT="http://localhost:11434/v1"
export CUSTOM_LLM_MODEL_NAME="kimi-k2:1t-cloud"
export CUSTOM_LLM_TEMPERATURE=0.0
#export CUSTOM_LLM_MAX_TOKENS=8192

echo " Запуск easy-llm-cli с Kimi K2..."
elc "$@"
