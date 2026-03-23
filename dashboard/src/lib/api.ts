/**
 * Genesis API client — all backend calls go through here.
 */

// In production, use relative URLs (nginx proxies /api/ to backend).
// In dev, point to localhost:8000.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || (typeof window !== "undefined" && window.location.hostname !== "localhost" ? "" : "http://localhost:8000");

let authToken: string | null = null;

export function setToken(token: string) {
  authToken = token;
  if (typeof window !== "undefined") {
    localStorage.setItem("genesis_token", token);
  }
}

export function getToken(): string | null {
  if (authToken) return authToken;
  if (typeof window !== "undefined") {
    authToken = localStorage.getItem("genesis_token");
  }
  return authToken;
}

export function clearToken() {
  authToken = null;
  if (typeof window !== "undefined") {
    localStorage.removeItem("genesis_token");
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> || {}),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }

  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function register(data: {
  tenant_name: string;
  tenant_slug: string;
  email: string;
  password: string;
  name: string;
}) {
  const res = await request<{
    access_token: string;
    tenant_id: string;
    user_id: string;
    email: string;
  }>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
  setToken(res.access_token);
  return res;
}

export async function login(data: {
  email: string;
  password: string;
  tenant_slug: string;
}) {
  const res = await request<{
    access_token: string;
    tenant_id: string;
    user_id: string;
  }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
  setToken(res.access_token);
  return res;
}

export async function getMe() {
  return request<{
    user_id: string;
    tenant_id: string;
    tenant_name: string;
    email: string;
    name: string;
    is_admin: boolean;
  }>("/api/v1/auth/me");
}

// ── Factories ────────────────────────────────────────────────────────────────

export interface Factory {
  id: string;
  name: string;
  domain: string;
  description: string | null;
  tech_stack: string | null;
  status: string;
  fast_track: boolean;
  github_repo: string | null;
  build_count: number;
  avg_vibe_score: number | null;
  created_at: string;
}

export async function listFactories() {
  return request<{ factories: Factory[]; total: number }>(
    "/api/v1/factories"
  );
}

export async function createFactory(data: {
  name: string;
  domain: string;
  description?: string;
  tech_stack?: string;
  fast_track?: boolean;
}) {
  return request<Factory>("/api/v1/factories", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getFactory(id: string) {
  return request<Factory>(`/api/v1/factories/${id}`);
}

// ── Builds ───────────────────────────────────────────────────────────────────

export interface Build {
  id: string;
  factory_id: string;
  feature_request: string;
  status: string;
  vibe_score: number | null;
  vibe_grade: string | null;
  iterations: number;
  build_mode: string;
  file_map: Record<string, string> | null;
  findings: any | null;
  requirements_data: any | null;
  design_data: any | null;
  plan: any | null;
  created_at: string;
  updated_at: string;
}

export async function listBuilds(factoryId?: string) {
  const params = factoryId ? `?factory_id=${factoryId}` : "";
  return request<{ builds: Build[]; total: number }>(
    `/api/v1/builds${params}`
  );
}

export async function createBuild(data: {
  factory_id: string;
  feature_request: string;
  build_mode?: string;
  fast_track?: boolean;
}) {
  return request<Build>("/api/v1/builds", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getBuild(id: string) {
  return request<Build>(`/api/v1/builds/${id}`);
}

export async function deleteBuild(id: string) {
  return request<void>(`/api/v1/builds/${id}`, { method: "DELETE" });
}

export async function advanceBuild(id: string, fastTrack = false) {
  return request<Build>(`/api/v1/builds/${id}/advance`, {
    method: "POST",
    body: JSON.stringify({ fast_track: fastTrack }),
  });
}

export async function runBuild(id: string, fastTrack = false) {
  return request<Build>(`/api/v1/builds/${id}/run`, {
    method: "POST",
    body: JSON.stringify({ fast_track: fastTrack }),
  });
}

export async function approveBuild(
  id: string,
  data: { type: string; decision: string; comment?: string }
) {
  return request<Build>(`/api/v1/builds/${id}/approve`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Supervisor ───────────────────────────────────────────────────────────────

export interface SupervisorStatus {
  tenant_id: string;
  active_builds: number;
  max_concurrent: number;
  queued_builds: number;
  total_factories: number;
  total_builds: number;
  credits_used: number;
  credits_limit: number;
  builds_by_status: Record<string, number>;
}

export async function getSupervisorStatus() {
  return request<SupervisorStatus>("/api/v1/supervisor/status");
}

export async function getActiveBuilds() {
  return request<
    {
      build_id: string;
      factory_id: string;
      factory_name: string;
      feature_request: string;
      status: string;
      vibe_score: number | null;
      created_at: string;
    }[]
  >("/api/v1/supervisor/active");
}

// ── Conversation (Guided Build) ──────────────────────────────────────────────

export interface ConversationMessage {
  role: "user" | "assistant" | "system";
  content: string;
  attachments?: { type: string; name: string; content: string }[];
  timestamp: string;
}

export interface ConversationState {
  build_id: string;
  factory_id: string;
  phase: string;
  messages: ConversationMessage[];
  context: Record<string, any>;
  artifacts: Record<string, any> | null;
  ready_to_build: boolean;
}

export async function startConversation(data: {
  factory_id: string;
  initial_idea: string;
  assistant_ids?: string[];
}) {
  return request<ConversationState>("/api/v1/conversation/start", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function sendMessage(buildId: string, message: string, attachments?: any[]) {
  return request<ConversationState>(`/api/v1/conversation/${buildId}/message`, {
    method: "POST",
    body: JSON.stringify({ message, attachments }),
  });
}

export async function scanWebsite(buildId: string, url: string) {
  return request<ConversationState>(`/api/v1/conversation/${buildId}/scan-website`, {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function getConversation(buildId: string) {
  return request<ConversationState>(`/api/v1/conversation/${buildId}`);
}

export async function generateRequirements(buildId: string) {
  return request<any>(`/api/v1/conversation/${buildId}/generate-requirements`, {
    method: "POST",
  });
}

// ── Assistants ───────────────────────────────────────────────────────────────

export interface AssistantSummary {
  id: string;
  name: string;
  domain: string;
  domain_label: string;
  description: string;
  weight: number;
  is_active: boolean;
  source: "catalog" | "custom";
}

export interface AssistantDetail extends AssistantSummary {
  system_prompt: string;
}

export async function listAssistants(domain?: string, source?: string) {
  const params = new URLSearchParams();
  if (domain) params.set("domain", domain);
  if (source) params.set("source", source);
  const qs = params.toString();
  return request<{
    assistants: AssistantSummary[];
    total: number;
    domains: Record<string, string>;
  }>(`/api/v1/assistants${qs ? `?${qs}` : ""}`);
}

export async function getAssistant(id: string) {
  return request<AssistantDetail>(`/api/v1/assistants/${id}`);
}

export async function createAssistant(data: {
  name: string;
  domain: string;
  description: string;
  system_prompt: string;
  weight?: number;
  is_active?: boolean;
}) {
  return request<AssistantDetail>("/api/v1/assistants", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAssistant(id: string, data: Partial<{
  name: string;
  domain: string;
  description: string;
  system_prompt: string;
  weight: number;
  is_active: boolean;
}>) {
  return request<AssistantDetail>(`/api/v1/assistants/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function forkAssistant(id: string) {
  return request<AssistantDetail>(`/api/v1/assistants/${id}/fork`, {
    method: "POST",
  });
}

export async function deleteAssistant(id: string) {
  return request<void>(`/api/v1/assistants/${id}`, { method: "DELETE" });
}

export async function listReviewAssistants() {
  return request<{ assistants: AssistantSummary[]; total: number; domains: Record<string, string> }>(
    "/api/v1/assistants/review"
  );
}

export async function listDiscoveryAssistants() {
  return request<{ assistants: AssistantSummary[]; total: number; domains: Record<string, string> }>(
    "/api/v1/assistants/discovery"
  );
}

// ── Review ───────────────────────────────────────────────────────────────────

export async function reviewCode(data: {
  code: string;
  language?: string;
  context?: string;
}) {
  return request<{
    vibe_score: number;
    grade: string;
    summary: string;
    findings_count: number;
    findings: any[];
    recommendations: string[];
    assistants_used: string[];
  }>("/api/v1/review", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
