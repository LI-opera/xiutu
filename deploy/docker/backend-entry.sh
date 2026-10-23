#!/bin/sh
# init, API and worker share one image. A BGE-M3 model is used only when one is mounted.
set -eu
if [ -f /models/bge-m3/model.onnx ] || [ -f /models/bge-m3/onnx/model.onnx ]; then
  export EMBEDDING_MODEL_PATH=/models/bge-m3
fi
case "${1:-api}" in
  init)
    exec python -B scripts/container_init.py ;;
  api)
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 ;;
  worker)
    exec python -B -m app.worker ;;
  *)
    exec "$@" ;;
esac
