"""Hotmethod gRPC 服务：接收 Agent 采集结果。"""

import json
from typing import Any

from google.protobuf.empty_pb2 import Empty

from server.app.generated import hotmethod_pb2_grpc
from server.app.state_machine import Actor, TaskStatus


class HotmethodService(hotmethod_pb2_grpc.HotmethodServicer):
    """采集结果上报服务。"""

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    def NotifyResult(self, request, context) -> Empty:
        task_id = request.task_id

        if request.error_message:
            # Agent 报告采集失败
            self._repo.transition_task(
                task_id, TaskStatus.FAILED,
                request.error_message, Actor.AGENT,
            )
            return Empty()

        # 采集成功：先迁移到 UPLOADING，写入产物元数据
        self._repo.transition_task(
            task_id, TaskStatus.UPLOADING,
            "采集完成，准备上传产物", Actor.AGENT,
        )

        # 解析 artifact 元数据
        artifacts: list[dict] = []
        if request.artifact_metadata_json:
            try:
                artifacts = json.loads(request.artifact_metadata_json)
            except json.JSONDecodeError:
                artifacts = [{"artifact_type": request.artifact_type, "cos_key": request.cos_key}]
        elif request.cos_key:
            artifacts = [{"artifact_type": request.artifact_type or "raw", "cos_key": request.cos_key}]

        if artifacts:
            self._repo.add_artifacts(task_id, artifacts)

        # 产物写入后迁移到 ANALYZING
        self._repo.transition_task(
            task_id, TaskStatus.ANALYZING,
            "产物已记录，等待分析", Actor.SERVER,
        )

        return Empty()
