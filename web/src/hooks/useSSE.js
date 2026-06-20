import { useEffect, useRef, useState, useCallback } from "react";
import { createEventSource } from "../api/client";

/**
 * Server-Sent Events 实时事件 Hook。
 *
 * 连接后台 /api/events/stream，接收任务状态变更、
 * Agent 上下线、诊断完成等事件，触发回调。
 *
 * 特性：
 * - 自动重连（指数退避，最多 30s 间隔）
 * - 页面隐藏时保持连接
 * - 组件卸载时自动关闭
 *
 * @param {object} handlers
 * @param {(data: object) => void} [handlers.onTaskChanged]
 * @param {(data: object) => void} [handlers.onAgentStatus]
 * @param {(data: object) => void} [handlers.onDiagnosisComplete]
 * @param {(connected: boolean) => void} [handlers.onConnectionChange]
 * @returns {{ connected: boolean, reconnect: () => void }}
 */
export default function useSSE({
  onTaskChanged,
  onAgentStatus,
  onDiagnosisComplete,
  onConnectionChange,
} = {}) {
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef(null);
  const retryCount = useRef(0);
  const maxRetryDelay = 30000;

  const handlersRef = useRef({ onTaskChanged, onAgentStatus, onDiagnosisComplete, onConnectionChange });
  handlersRef.current = { onTaskChanged, onAgentStatus, onDiagnosisComplete, onConnectionChange };

  const connect = useCallback(() => {
    const es = createEventSource();

    es.onopen = () => {
      setConnected(true);
      retryCount.current = 0;
      handlersRef.current.onConnectionChange?.(true);
    };

    es.addEventListener("task_changed", (e) => {
      try {
        const data = JSON.parse(e.data);
        handlersRef.current.onTaskChanged?.(data);
      } catch {
        // 忽略解析错误
      }
    });

    es.addEventListener("agent_status", (e) => {
      try {
        const data = JSON.parse(e.data);
        handlersRef.current.onAgentStatus?.(data);
      } catch {
        // 忽略
      }
    });

    es.addEventListener("diagnosis_complete", (e) => {
      try {
        const data = JSON.parse(e.data);
        handlersRef.current.onDiagnosisComplete?.(data);
      } catch {
        // 忽略
      }
    });

    // 默认 message 事件作为兼容
    es.onmessage = (e) => {
      try {
        const raw = JSON.parse(e.data);
        const eventType = raw.event || raw.type;
        const data = raw.data || raw;
        if (eventType === "task_changed") handlersRef.current.onTaskChanged?.(data);
        else if (eventType === "agent_status") handlersRef.current.onAgentStatus?.(data);
        else if (eventType === "diagnosis_complete") handlersRef.current.onDiagnosisComplete?.(data);
      } catch {
        // 忽略
      }
    };

    es.onerror = () => {
      setConnected(false);
      handlersRef.current.onConnectionChange?.(false);
      es.close();

      // 指数退避重连
      const delay = Math.min(1000 * Math.pow(2, retryCount.current), maxRetryDelay);
      retryCount.current += 1;
      reconnectTimer.current = setTimeout(connect, delay);
    };

    return es;
  }, []);

  useEffect(() => {
    const es = connect();
    return () => {
      es.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  const reconnect = useCallback(() => {
    retryCount.current = 0;
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    connect();
  }, [connect]);

  return { connected, reconnect };
}
