// The answer is a job on the server. This module only starts it and polls.
// Leaving the assistant does not abort the job, and the poll keeps running
// after the page unmounts. A reload picks the same job back up.
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { ApiError, api } from "./api";

export interface ChatMeta {
  mode?: string;
  provider?: string;
  model?: string;
  fallback_reason?: string;
  usage?: { prompt_tokens?: number; completion_tokens?: number } | null;
  context_summary?: { alerts?: number; research_passages?: number; as_of?: string };
  citations?: { ref: string; title: string; source: string }[];
}

export interface ChatMsg { role: "user" | "assistant"; content: string; meta?: ChatMeta }

export interface ChatSnapshot {
  msgs: ChatMsg[];
  busy: boolean;
  local: boolean;
  startedAt: number | null;
}

export interface ChatActivity {
  busy: boolean;
  local: boolean;
  href: string;
  startedAt: number | null;
}

interface PendingJob {
  id: string;
  username: string;
  astronautId: string;
  local: boolean;
  startedAt: number;
  fails: number;
}

const EMPTY: ChatSnapshot = { msgs: [], busy: false, local: false, startedAt: null };
const IDLE: ChatActivity = { busy: false, local: false, href: "/assistant", startedAt: null };
const MAX_TURNS = 40;
const JOB_KEY = "hmt.chat.job";
const POLL_MS = 1500;

const cache = new Map<string, ChatSnapshot>();
const listeners = new Map<string, Set<() => void>>();
const activityListeners = new Set<() => void>();
let activity: ChatActivity = IDLE;
let pending: PendingJob | null = null;
let timer: number | null = null;
let polling = false;

function threadKey(username: string, astronautId: string) {
  return `${username}|${astronautId}`;
}

function storageKey(username: string, astronautId: string) {
  return `hmt.chat.${username}.${astronautId}`;
}

function load(username: string, astronautId: string): ChatMsg[] {
  try {
    const raw = localStorage.getItem(storageKey(username, astronautId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string");
  } catch {
    return [];
  }
}

function persist(username: string, astronautId: string, msgs: ChatMsg[]) {
  const kept = msgs.slice(-MAX_TURNS);
  try {
    localStorage.setItem(storageKey(username, astronautId), JSON.stringify(kept));
  } catch {
    try { localStorage.setItem(storageKey(username, astronautId), JSON.stringify(kept.slice(-8))); } catch { /* storage full or blocked */ }
  }
}

function recomputeActivity() {
  let next = IDLE;
  if (pending) {
    next = {
      busy: true,
      local: pending.local,
      href: `/assistant?a=${encodeURIComponent(pending.astronautId)}`,
      startedAt: pending.startedAt,
    };
  } else {
    for (const [key, snap] of cache) {
      if (!snap.busy) continue;
      const astronautId = key.slice(key.indexOf("|") + 1);
      next = { busy: true, local: snap.local, href: `/assistant?a=${encodeURIComponent(astronautId)}`, startedAt: snap.startedAt };
      break;
    }
  }
  if (activity.busy === next.busy && activity.local === next.local && activity.href === next.href && activity.startedAt === next.startedAt) return;
  activity = next;
  activityListeners.forEach((fn) => fn());
}

function publish(username: string, astronautId: string, snap: ChatSnapshot) {
  const key = threadKey(username, astronautId);
  cache.set(key, snap);
  persist(username, astronautId, snap.msgs);
  listeners.get(key)?.forEach((fn) => fn());
  recomputeActivity();
}

export function getChatSnapshot(username: string, astronautId: string): ChatSnapshot {
  const key = threadKey(username, astronautId);
  let snap = cache.get(key);
  if (!snap) {
    snap = { msgs: load(username, astronautId), busy: false, local: false, startedAt: null };
    cache.set(key, snap);
  }
  return snap;
}

function subscribe(username: string, astronautId: string, fn: () => void) {
  const key = threadKey(username, astronautId);
  let set = listeners.get(key);
  if (!set) { set = new Set(); listeners.set(key, set); }
  set.add(fn);
  return () => { set!.delete(fn); };
}

function slim(r: any): ChatMeta {
  return {
    mode: r.mode,
    provider: r.provider,
    model: r.model,
    fallback_reason: r.fallback_reason,
    usage: r.usage ?? undefined,
    context_summary: r.context_summary,
    citations: Array.isArray(r.citations)
      ? r.citations.map((c: any) => ({ ref: String(c.ref ?? ""), title: String(c.title ?? ""), source: String(c.source ?? "") }))
      : undefined,
  };
}

function savePending() {
  try {
    if (pending) sessionStorage.setItem(JOB_KEY, JSON.stringify(pending));
    else sessionStorage.removeItem(JOB_KEY);
  } catch { /* storage blocked */ }
}

function stopPolling() {
  if (timer != null) {
    window.clearInterval(timer);
    timer = null;
  }
}

function settle(job: PendingJob, message: ChatMsg | null) {
  if (pending?.id !== job.id) return;
  pending = null;
  savePending();
  stopPolling();
  const latest = getChatSnapshot(job.username, job.astronautId);
  publish(job.username, job.astronautId, {
    msgs: message ? [...latest.msgs, message] : latest.msgs,
    busy: false,
    local: false,
    startedAt: null,
  });
}

async function tick() {
  if (polling) return;
  const job = pending;
  if (!job) return;
  polling = true;
  try {
    const r = await api<any>(`/assistant/chat/jobs/${job.id}`);
    if (pending?.id !== job.id) return;
    job.fails = 0;
    if (r.status === "pending") return;
    if (r.status === "done") {
      settle(job, { role: "assistant", content: r.answer, meta: slim(r) });
      return;
    }
    settle(job, { role: "assistant", content: `**Request failed:** ${r.detail ?? "the model did not answer"}` });
  } catch (e: any) {
    if (pending?.id !== job.id) return;
    if (e instanceof ApiError && e.status === 401) {
      settle(job, null);
      return;
    }
    // The job id is saved before the server has registered it. A 404 in that window is not a failure.
    if (e instanceof ApiError && e.status === 404 && Date.now() - job.startedAt < 15000) return;
    job.fails += 1;
    if ((e instanceof ApiError && e.status === 404) || job.fails >= 8) {
      settle(job, { role: "assistant", content: `**Request failed:** ${e?.message ?? "the answer could not be collected. Ask again."}` });
    }
  } finally {
    polling = false;
  }
}

function arm() {
  if (timer != null || !pending) return;
  timer = window.setInterval(() => { void tick(); }, POLL_MS);
  void tick();
}

function restore() {
  if (typeof sessionStorage === "undefined") return;
  try {
    const raw = sessionStorage.getItem(JOB_KEY);
    if (!raw) return;
    const job = JSON.parse(raw) as PendingJob;
    if (!job?.id || !job.username || !job.astronautId) return;
    pending = { ...job, fails: 0 };
    const snap = getChatSnapshot(job.username, job.astronautId);
    publish(job.username, job.astronautId, { ...snap, busy: true, local: !!job.local, startedAt: job.startedAt });
    arm();
  } catch { /* ignore a bad saved job */ }
}

restore();

export function sendChat(
  username: string,
  astronautId: string,
  text: string,
  choice: { provider: string; model?: string },
  local: boolean,
) {
  const trimmed = text.trim();
  const cur = getChatSnapshot(username, astronautId);
  if (!trimmed || cur.busy || pending) return Promise.resolve();
  const history = cur.msgs.map(({ role, content }) => ({ role, content }));
  const id = (crypto.randomUUID?.() ?? `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`).replace(/-/g, "").slice(0, 32).padEnd(32, "0");
  const startedAt = Date.now();
  pending = { id, username, astronautId, local, startedAt, fails: 0 };
  savePending();
  publish(username, astronautId, {
    msgs: [...cur.msgs, { role: "user", content: trimmed }],
    busy: true,
    local,
    startedAt,
  });
  arm();
  return api<any>("/assistant/chat/jobs", {
    body: { astronaut_id: astronautId, message: trimmed, history, job_id: id, ...choice },
  }).then(
    (r) => {
      if (pending && r?.id && r.id !== pending.id) {
        pending = { ...pending, id: r.id };
        savePending();
      }
    },
    (e: any) => {
      const job = pending;
      if (!job || job.id !== id) return;
      settle(job, { role: "assistant", content: `**Request failed:** ${e?.message ?? "unknown error"}` });
    },
  );
}

export function useAssistantChat(username: string, astronautId: string | null) {
  const get = useCallback(
    () => (astronautId ? getChatSnapshot(username, astronautId) : EMPTY),
    [username, astronautId],
  );
  const sub = useCallback(
    (fn: () => void) => (astronautId ? subscribe(username, astronautId, fn) : () => {}),
    [username, astronautId],
  );
  return useSyncExternalStore(sub, get, get);
}

export function useChatActivity() {
  return useSyncExternalStore(
    (fn: () => void) => {
      activityListeners.add(fn);
      return () => { activityListeners.delete(fn); };
    },
    () => activity,
    () => activity,
  );
}

export function useElapsed(startedAt: number | null, active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active || !startedAt) return;
    setNow(Date.now());
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [active, startedAt]);
  if (!active || !startedAt) return 0;
  return Math.max(0, Math.round((now - startedAt) / 1000));
}
