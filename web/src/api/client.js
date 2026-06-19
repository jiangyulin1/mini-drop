/** Mini-Drop HTTP API 客户端。

所有 Web 请求通过此模块调用 Server REST API。
axios 拦截器统一处理错误码和响应格式。
*/

import axios from "axios";

const API_KEY_STORAGE_KEY = "mini-drop-api-key";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = getStoredApiKey();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** 响应拦截：统一提取 data 字段，简化调用方代码 */
api.interceptors.response.use(
  (resp) => {
    const body = resp.data;
    if (body.code === 0) return body.data;
    throw new Error(body.message || "未知错误");
  },
  (err) => {
    const detail = err.response?.data?.detail || err.message;
    throw new Error(detail);
  },
);

// ── 通用 ────────────────────────────────────────────────────────

export function getStoredApiKey() {
  try {
    return window.localStorage.getItem(API_KEY_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function setStoredApiKey(token) {
  try {
    const normalized = (token || "").trim();
    if (normalized) {
      window.localStorage.setItem(API_KEY_STORAGE_KEY, normalized);
    } else {
      window.localStorage.removeItem(API_KEY_STORAGE_KEY);
    }
  } catch {
    // Ignore unavailable localStorage in restricted browser contexts.
  }
}

export function healthz() {
  return api.get("/healthz");
}

function itemsOf(value) {
  if (Array.isArray(value)) return value;
  return value?.items || [];
}

// ── Agent ────────────────────────────────────────────────────────

export function listAgents() {
  return api.get("/agents").then(itemsOf);
}

export function listAuditLogs() {
  return api.get("/audit-logs").then(itemsOf);
}

// ── 任务 ────────────────────────────────────────────────────────

export function createTask(payload) {
  return api.post("/tasks", payload);
}

export function listTasks() {
  return api.get("/tasks");
}

export function getTask(taskId) {
  return api.get(`/tasks/${taskId}`);
}

export function getTaskEvents(taskId) {
  return api.get(`/tasks/${taskId}/events`);
}

export function getTaskArtifacts(taskId) {
  return api.get(`/tasks/${taskId}/artifacts`);
}

export function getTaskArtifactContent(taskId, artifactType) {
  return api.get(`/tasks/${taskId}/artifacts/${artifactType}/content`);
}

export function triggerDiagnose(taskId) {
  return api.post(`/tasks/${taskId}/diagnose`);
}

export function listTaskDiagnoses(taskId) {
  return api.get(`/tasks/${taskId}/diagnoses`);
}

export function getDiagnosis(diagnosisId) {
  return api.get(`/diagnoses/${diagnosisId}`);
}

export function submitDiagnosisFeedback(diagnosisId, payload) {
  return api.post(`/diagnoses/${diagnosisId}/feedback`, payload);
}

// ── NLP 自然语言采集 ────────────────────────────────────────────

export function nlpParse(query) {
  return api.post("/nlp/parse", { query });
}

export function nlpSummarize(taskId) {
  return api.post("/nlp/summarize", { task_id: taskId });
}
