"""HealthCheck gRPC 服务：1 Hz 心跳 + 任务下发。"""

from server.app.generated import healthcheck_pb2, healthcheck_pb2_grpc, hotmethod_pb2
from server.app.repository import InMemoryRepository


class HealthCheckService(healthcheck_pb2_grpc.HealthCheckServicer):
    """Agent 心跳服务，一次 RPC 同时完成保活和任务拉取。"""

    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo

    def Do(self, request: healthcheck_pb2.HealthCheckRequest, context) -> healthcheck_pb2.HealthCheckResponse:
        # 记录心跳，检查有无待执行任务
        task = self._repo.heartbeat(request.agent_id, request.ip_addr)

        response = healthcheck_pb2.HealthCheckResponse()
        response.status = healthcheck_pb2.HealthCheckResponse.SERVING

        if task is None:
            response.pending = False
            return response

        # 构造 TaskDesc 并嵌入响应
        response.pending = True
        task_desc = response.task_desc
        task_desc.task_id = task.id
        task_desc.task_type = 0  # 通用任务
        task_desc.profiler_type = self._profiler_type(task.collector_type)
        task_desc.timeout_sec = task.duration_sec + 30  # 留 30 秒余量
        task_desc.sample_argv.hz = task.sample_rate
        task_desc.sample_argv.duration = task.duration_sec
        task_desc.sample_argv.pid = task.target_pid
        task_desc.sample_argv.callgraph = task.request_params.get("options", {}).get("callgraph", "fp")
        task_desc.sample_argv.event = task.request_params.get("options", {}).get("event", "cpu-cycles")
        task_desc.sample_argv.subprocess = task.request_params.get("options", {}).get("subprocess", False)
        return response

    @staticmethod
    def _profiler_type(collector_type: str) -> int:
        """将 collector_type 字符串映射为 protobuf profiler_type 枚举值。"""
        mapping: dict[str, int] = {
            "perf_cpu": 0,
            "ebpf_io": 4,       # 4 = bpftrace
            "pyspy": 3,         # 3 = py-spy
            "continuous_perf": 0,  # 同样是 perf
        }
        return mapping.get(collector_type, 0)
