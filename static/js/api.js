// Thin client for the Upsolve REST API (/api/v1). Plugins receive this same client.

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
  }
}

async function request(method, path, body) {
  const res = await fetch(`/api/v1${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new ApiError(res.status, Array.isArray(d) ? d.map((x) => x.msg).join("; ") : d || res.statusText);
  }
  return data;
}

const u = (handle) => `/users/${encodeURIComponent(handle)}`;

export const api = {
  get: (path) => request("GET", path),
  put: (path, body) => request("PUT", path, body),
  post: (path, body) => request("POST", path, body),
  del: (path) => request("DELETE", path),

  startSync: (h) => request("POST", `${u(h)}/sync`),
  syncStatus: (h) => request("GET", `${u(h)}/sync`),
  users: () => request("GET", "/users"),
  profile: (h) => request("GET", `${u(h)}/profile`),
  topics: (h) => request("GET", `${u(h)}/topics`),
  topicHistory: (h, tag) => request("GET", `${u(h)}/topics/${encodeURIComponent(tag)}/history`),
  ratingHistory: (h) => request("GET", `${u(h)}/rating-history`),
  activity: (h, days = 365) => request("GET", `${u(h)}/activity?days=${days}`),
  attempts: (h, { limit = 20, tag } = {}) =>
    request("GET", `${u(h)}/attempts?limit=${limit}${tag ? `&tag=${encodeURIComponent(tag)}` : ""}`),
  recommendations: (h, { count = 5, topic, refresh = 0 } = {}) =>
    request("GET", `${u(h)}/recommendations?count=${count}&refresh=${refresh}${topic ? `&topic=${encodeURIComponent(topic)}` : ""}`),
  predict: (h, pid) => request("GET", `${u(h)}/predict/${encodeURIComponent(pid)}`),
  feedback: (h) => request("GET", `${u(h)}/feedback`),
  training: (h) => request("GET", `${u(h)}/training`),
  setTraining: (h, body) => request("PUT", `${u(h)}/training`, body),
  plan: (h) => request("GET", `${u(h)}/plan`),
  allTopics: () => request("GET", "/topics"),
  model: () => request("GET", "/model"),
  plugins: () => request("GET", "/plugins"),
  togglePlugin: (id, enabled) => request("PUT", `/plugins/${id}`, { enabled }),
};
