#!/bin/bash
# compile.sh — 将 .proto 文件编译为 Python gRPC stub
#
# 使用前确认已安装:
#   pip install grpcio grpcio-tools protobuf
#
# 编译产物输出到 server/app/generated/ 目录，
# Server 和 Agent 均从此处 import 生成的 *_pb2.py 和 *_pb2_grpc.py。

set -euo pipefail

PROTO_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${PROTO_DIR}/../server/app/generated"

# 定位 grpc_tools 自带的 google/protobuf/*.proto（empty.proto 等）。
GRPC_INCLUDE=$(python -c "import grpc_tools,os;print(os.path.join(os.path.dirname(grpc_tools.__file__),'_proto'))")

mkdir -p "${OUT_DIR}"

python -m grpc_tools.protoc \
    -I"${PROTO_DIR}" \
    -I"${GRPC_INCLUDE}" \
    --python_out="${OUT_DIR}" \
    --grpc_python_out="${OUT_DIR}" \
    common.proto \
    init.proto \
    healthcheck.proto \
    hotmethod.proto \
    control.proto

# grpc_tools 会生成 `import common_pb2` 这类同级导入。
# 生成文件位于 server.app.generated 包内，后续业务代码会按包路径导入，
# 因此这里统一改成相对导入，避免 `ModuleNotFoundError: common_pb2`。
python - "${OUT_DIR}" <<'PY'
import re
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
pattern = re.compile(r"^import ([a-zA-Z0-9_]+_pb2) as ([a-zA-Z0-9_]+)$", re.MULTILINE)

for path in out_dir.glob("*_pb2*.py"):
    text = path.read_text(encoding="utf-8")
    text = pattern.sub(r"from . import \1 as \2", text)
    path.write_text(text, encoding="utf-8")
PY

# 为 generated 包生成 __init__.py
cat > "${OUT_DIR}/__init__.py" <<'EOF'
"""gRPC 自动生成的 Python stub。由 proto/compile.sh 生成，不要手动编辑。"""
EOF

echo "proto 编译完成: ${OUT_DIR}"
