"""Control gRPC 服务：Web → Server 任务创建与 Agent 查询。"""

from server.app.generated import control_pb2, control_pb2_grpc
from server.app.repository import InMemoryRepository
from server.app.schemas import CreateTaskRequest


class ControlService(control_pb2_grpc.ControlServicer):
    """控制面服务，供 FastAPI 层调用。"""

    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo

    def CreateTask(self, request: control_pb2.CreateTaskRequest, context) -> control_pb2.CreateTaskResponse:
        task_desc = request.task_desc
        agent = self._repo.find_agent_by_ip(request.target_ip)
        agent_id = agent.id if agent is not None else request.target_ip
        payload = CreateTaskRequest(
            name=f"task_{request.task_id}" if request.task_id else "gRPC task",
            agent_id=agent_id,
            target_pid=task_desc.sample_argv.pid,
            collector_type=self._collector_type(task_desc.profiler_type),
            sample_rate=task_desc.sample_argv.hz or 99,
            duration_sec=int(task_desc.sample_argv.duration) if task_desc.sample_argv.duration else 15,
            options={
                "callgraph": task_desc.sample_argv.callgraph or "fp",
                "event": task_desc.sample_argv.event or "cpu-cycles",
                "subprocess": task_desc.sample_argv.subprocess,
            },
        )
        task = self._repo.create_task(payload)
        return control_pb2.CreateTaskResponse(task_id=task.id, status=task.status.value)

    def StatAgent(self, request: control_pb2.StatAgentRequest, context) -> control_pb2.StatAgentResponse:
        agent = self._repo.agents.get(request.agent_id)
        response = control_pb2.StatAgentResponse()
        if agent is not None:
            response.agent_status = agent.status
            response.current_stats.cpu_percent = 0.0
            response.current_stats.rss_mb = 0.0
        else:
            response.agent_status = "UNKNOWN"
        return response

    @staticmethod
    def _collector_type(profiler_type: int) -> str:
        mapping = {0: "perf_cpu", 1: "pyspy", 3: "pyspy", 4: "ebpf_io"}
        return mapping.get(profiler_type, "perf_cpu")
