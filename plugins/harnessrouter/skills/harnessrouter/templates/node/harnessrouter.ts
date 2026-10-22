// License: Apache-2.0; scope and full text: ../../LICENSING.md
/**
 * HarnessRouter Cloud server adapter for Node 18+ and TypeScript. No dependencies.
 *
 * Copy this file into SERVER-ONLY code (for Next.js, a module that imports 'server-only').
 * It covers: start a streamed task, parse SSE, persist response.id and session_id, keep consuming
 * after the browser leaves, poll to recover, background mode, cancel, list and fetch files, and a
 * signed sandboxed preview route. Contract: references/api-reference.md (verified 2026-10-21,
 * UHP-Version 2026-09-28). Uses only erasable TypeScript, so Node 22.18+ runs it directly.
 */
import { createHmac, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export const API_BASE = 'https://api.harnessrouter.ai';
export const UHP_VERSION = '2026-09-28';
export const TERMINAL_STATUSES: ReadonlySet<string> = new Set(['completed', 'incomplete', 'failed', 'cancelled']);
const TERMINAL_EVENTS: ReadonlySet<string> = new Set(['response.completed', 'response.incomplete', 'response.failed']);

// ── shapes (api-reference.md) ─────────────────────────────────────────────────────────────────
export interface Annotation {
  type: string; container_id: string; file_id: string; filename: string; download_url: string;
  start_index?: number; end_index?: number;
}
export interface ContentPart { type: string; text?: string; annotations?: Annotation[] }
export interface OutputItem {
  id?: string; type: string; status?: string; role?: string; content?: ContentPart[];
  name?: string; arguments?: string; call_id?: string; output?: string;
}
export interface HRResponse {
  id: string; object: string; status: string; created_at?: number; error?: unknown;
  incomplete_details?: { reason?: string } | null; previous_response_id?: string | null;
  model?: string; served_model?: string | null; output: OutputItem[];
  usage?: Record<string, number> | null; metadata?: { session_id?: string; [k: string]: unknown };
}
export interface StreamEvent {
  type: string; sequence_number?: number; response?: HRResponse; delta?: string; text?: string;
  item?: OutputItem; annotation?: Annotation; [k: string]: unknown;
}
export interface SessionFile {
  object: string; id: string; file_id: string; container_id: string; filename: string; path: string;
  bytes: number; media_type: string; download_url: string;
}
export interface Harness {
  id: string; name: string; base: string; defaultModel: string; systemPrompt: string;
  mcpServers: unknown[]; skills: unknown[]; plugins: unknown[]; additionalHeaders: string[];
  env: Record<string, string>; maxStep: number | null; timeoutSeconds: number | null;
  maxCostUsd: number | null; [k: string]: unknown;
}
/** The snake_case request body for POST and PUT /v1/harnesses. PUT replaces every field. */
export interface HarnessBody {
  name: string; base: string; default_model?: string; system_prompt?: string;
  mcp_servers?: unknown[]; skills?: unknown[]; plugins?: unknown[]; additional_headers?: string[];
  env?: Record<string, string>; max_step?: number | null; timeout_seconds?: number | null;
  max_cost_usd?: number | null; reasoning_effort?: string; environment?: string; disabled_tools?: string[];
}

export class HRError extends Error {
  readonly status: number;
  readonly code: string;
  readonly type: string;
  readonly param: string | null;
  readonly retryAfterSeconds: number | null;
  constructor(status: number, body: unknown, retryAfter: string | null) {
    const env = (body && typeof body === 'object' ? body : {}) as Record<string, unknown>;
    const e = (env.error && typeof env.error === 'object' ? env.error : {}) as Record<string, unknown>;
    // The UHP envelope, or the legacy {"detail": "..."} an unknown route answers.
    const message = String(e.message ?? (typeof env.detail === 'string' ? env.detail : '') ?? '') || `HTTP ${status}`;
    super(message);
    this.name = 'HRError';
    this.status = status;
    this.code = String(e.code ?? (status === 404 ? 'not_found' : 'unknown'));
    this.type = String(e.type ?? '');
    this.param = e.param == null ? null : String(e.param);
    const ra = retryAfter == null ? NaN : Number(retryAfter);
    this.retryAfterSeconds = Number.isFinite(ra) ? ra : null;
  }
  /** Only these are worth a retry (and a POST /v1/responses only with the same Idempotency-Key). */
  get retryable(): boolean { return [429, 502, 503, 504].includes(this.status); }
}

// ── the key: HR_API_KEY, else the one-line .env.harnessrouter the key helper writes ─────────────
export function loadApiKey(projectRoot: string = process.cwd()): string {
  const env = process.env.HR_API_KEY?.trim();
  if (env) return env;
  const lines = readFileSync(join(projectRoot, '.env.harnessrouter'), 'utf8').split('\n').filter((l) => l.trim());
  if (lines.length !== 1 || !lines[0].startsWith('HR_API_KEY=')) {
    throw new Error('.env.harnessrouter must hold exactly one HR_API_KEY line');
  }
  return lines[0].slice('HR_API_KEY='.length).trim();
}

// ── SSE: frames split on a blank line, data: lines joined, JSON parsed; [DONE] and junk skipped ─
export async function* parseSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  const take = function* (frame: string): Generator<StreamEvent> {
    const data = frame.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).replace(/^ /, '')).join('\n');
    if (!data.trim() || data.trim() === '[DONE]') return;
    try {
      const ev = JSON.parse(data) as StreamEvent;
      if (ev && typeof ev.type === 'string') yield ev;
    } catch { /* not JSON: skip */ }
  };
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      // normalize on the whole buffer, so a CRLF split across two chunks still becomes one newline
      buf = (buf + decoder.decode(value, { stream: true })).replace(/\r\n/g, '\n');
      let i: number;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const frame = buf.slice(0, i);
        buf = buf.slice(i + 2);
        yield* take(frame);
      }
    }
    buf += decoder.decode();
    if (buf.trim()) yield* take(buf);
  } finally {
    reader.releaseLock();
  }
}

/** The answer: the output_text of the LAST message item. */
export function answerText(r: HRResponse): string {
  const msgs = (r.output || []).filter((i) => i.type === 'message');
  const last = msgs[msgs.length - 1];
  return (last?.content || []).filter((c) => c.type === 'output_text').map((c) => c.text || '').join('');
}

/** Files the task made or changed, as annotations on the last message (filename = relative path). */
export function producedFiles(r: HRResponse): Annotation[] {
  const out: Annotation[] = [];
  for (const item of r.output || []) {
    if (item.type !== 'message') continue;
    for (const c of item.content || []) for (const a of c.annotations || []) if (a.type === 'container_file_citation') out.push(a);
  }
  return out;
}

/** Upstream event -> the small, sanitized progress event a browser may see. null: show nothing. */
export type Progress =
  | { kind: 'text'; delta: string }
  | { kind: 'activity'; label: string }
  | { kind: 'done'; status: string };
export function toProgress(ev: StreamEvent): Progress | null {
  if (ev.type === 'response.output_text.delta' && typeof ev.delta === 'string') return { kind: 'text', delta: ev.delta };
  if (ev.type === 'response.output_item.added' && ev.item?.type === 'function_call') {
    const n = String(ev.item.name || '').toLowerCase();
    const label = /write|edit|patch/.test(n) ? 'Writing files' : /read|grep|glob|ls/.test(n) ? 'Reading files'
      : /bash|shell|exec/.test(n) ? 'Running a step' : /search|fetch|browse/.test(n) ? 'Looking things up' : 'Working';
    return { kind: 'activity', label };
  }
  if (TERMINAL_EVENTS.has(ev.type)) return { kind: 'done', status: ev.response?.status || 'failed' };
  return null;
}

// ── the client ────────────────────────────────────────────────────────────────────────────────
export interface TaskInput {
  harnessId: string;
  /** a string, or a message list with input_text / input_file parts */
  input: unknown;
  /** follow-ups only: both come from the stored task record */
  previousResponseId?: string;
  sessionId?: string;
  idempotencyKey?: string;
  maxStep?: number; timeoutSeconds?: number; maxCostUsd?: number;
}
export interface StreamHooks {
  /** called once, at response.created: persist both ids before anything else */
  onIds?: (ids: { responseId: string; sessionId: string }) => void | Promise<void>;
  onEvent?: (ev: StreamEvent) => void;
}

export interface ClientOptions {
  apiKey?: string; baseUrl?: string; fetch?: typeof fetch; sleep?: (ms: number) => Promise<void>;
}

export class HarnessRouter {
  readonly baseUrl: string;
  private readonly key: string;
  private readonly http: typeof fetch;
  private readonly sleep: (ms: number) => Promise<void>;

  constructor(opts: ClientOptions = {}) {
    this.key = opts.apiKey ?? loadApiKey();
    this.baseUrl = (opts.baseUrl ?? API_BASE).replace(/\/+$/, '');
    this.http = opts.fetch ?? fetch;
    this.sleep = opts.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
  }

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    return { Authorization: `Bearer ${this.key}`, 'UHP-Version': UHP_VERSION, Accept: 'application/json', ...extra };
  }

  private async raw(method: string, path: string, body?: unknown, extra: Record<string, string> = {}): Promise<Response> {
    const res = await this.http(this.baseUrl + path, {
      method,
      headers: this.headers(body === undefined ? extra : { 'Content-Type': 'application/json', ...extra }),
      body: body === undefined ? undefined : JSON.stringify(body),
      redirect: 'manual',
    });
    if (!res.ok) {
      let parsed: unknown = null;
      try { parsed = await res.json(); } catch { /* not JSON */ }
      throw new HRError(res.status, parsed, res.headers.get('retry-after'));
    }
    return res;
  }

  async request<T>(method: string, path: string, body?: unknown, extra?: Record<string, string>): Promise<T> {
    return (await (await this.raw(method, path, body, extra)).json()) as T;
  }

  // catalog and harnesses
  bases() { return this.request<{ bases: Array<{ id: string; defaultModel: string; models: Array<{ id: string; available: boolean }> }>; runtimeDefaults: Record<string, number> }>('GET', '/v1/bases'); }
  me() { return this.request<{ workspace: string; workspace_name: string }>('GET', '/v1/me'); }
  async listHarnesses(): Promise<Harness[]> { return (await this.request<{ harnesses: Harness[] }>('GET', '/v1/harnesses')).harnesses; }
  /** "Reuse by name": the Harness whose name equals `name` exactly, if any. */
  async findHarnessByName(name: string): Promise<Harness | undefined> { return (await this.listHarnesses()).find((h) => h.name === name); }
  createHarness(body: HarnessBody) { return this.request<Harness>('POST', '/v1/harnesses', body); }
  async getHarness(id: string): Promise<{ harness: Harness; etag: string | null }> {
    const res = await this.raw('GET', `/v1/harnesses/${encodeURIComponent(id)}`);
    return { harness: (await res.json()) as Harness, etag: res.headers.get('etag') };
  }
  /** A FULL replace: build `body` from a fresh getHarness() plus your change. */
  replaceHarness(id: string, body: HarnessBody, etag?: string | null) {
    return this.request<Harness>('PUT', `/v1/harnesses/${encodeURIComponent(id)}`, body, etag ? { 'If-Match': etag } : {});
  }
  deleteHarness(id: string) { return this.request<{ deleted: boolean }>('DELETE', `/v1/harnesses/${encodeURIComponent(id)}`); }

  private taskBody(t: TaskInput, mode: 'stream' | 'background' | 'block'): Record<string, unknown> {
    const metadata: Record<string, string> = { harness_id: t.harnessId };
    if (t.sessionId) metadata.session_id = t.sessionId;
    const body: Record<string, unknown> = { input: t.input, metadata };
    if (t.previousResponseId) body.previous_response_id = t.previousResponseId;
    if (t.maxStep) body.max_step = t.maxStep;
    if (t.timeoutSeconds) body.timeout_seconds = t.timeoutSeconds;
    if (t.maxCostUsd) body.max_cost_usd = t.maxCostUsd;
    if (mode === 'stream') body.stream = true;
    if (mode === 'background') body.background = true;
    return body;
  }

  /**
   * Start (or continue) a task and read its stream to the end. Resolves with the terminal response.
   * If the stream ends without a terminal event, it polls GET /v1/responses/{id} instead of
   * sending the task again. Do not tie this to the browser request: see runTask().
   */
  async runStreamed(t: TaskInput, hooks: StreamHooks = {}): Promise<HRResponse> {
    const res = await this.raw('POST', '/v1/responses', this.taskBody(t, 'stream'), {
      Accept: 'text/event-stream', 'Idempotency-Key': t.idempotencyKey || randomUUID(),
    });
    if (!res.body) throw new HRError(502, null, null);
    let responseId = '';
    let sessionId = '';
    let terminal: HRResponse | null = null;
    try {
      for await (const ev of parseSSE(res.body)) {
        const r = ev.response;
        if (r?.id && !responseId) responseId = r.id;
        const sid = r?.metadata?.session_id;
        if (sid && !sessionId) {
          sessionId = sid;
          // A replayed stream's created frame has no metadata: ids are then saved at the terminal event.
          await hooks.onIds?.({ responseId, sessionId });
        }
        hooks.onEvent?.(ev);
        if (TERMINAL_EVENTS.has(ev.type) && r) terminal = r;
      }
    } catch (err) {
      if (!responseId) throw err;   // nothing started that we know of
    }
    if (terminal) return terminal;
    if (!responseId) throw new HRError(502, { error: { code: 'stream_ended', message: 'The stream ended before the task started.' } }, null);
    return this.waitForResponse(responseId);
  }

  /** Background mode: answers at once with status "in_progress"; poll with waitForResponse(). */
  startBackground(t: TaskInput) {
    return this.request<HRResponse>('POST', '/v1/responses', this.taskBody(t, 'background'), { 'Idempotency-Key': t.idempotencyKey || randomUUID() });
  }
  getResponse(id: string) { return this.request<HRResponse>('GET', `/v1/responses/${encodeURIComponent(id)}`); }
  /** Poll until completed, incomplete, failed or cancelled: every 3 s, every 10 s after a minute. */
  async waitForResponse(id: string, opts: { timeoutMs?: number } = {}): Promise<HRResponse> {
    const start = Date.now();
    const limit = opts.timeoutMs ?? 2 * 60 * 60 * 1000 + 60_000;
    for (;;) {
      try {
        const r = await this.getResponse(id);
        if (TERMINAL_STATUSES.has(r.status)) return r;
      } catch (err) {
        if (!(err instanceof HRError) || !err.retryable) throw err;
      }
      if (Date.now() - start > limit) throw new HRError(504, { error: { code: 'poll_timeout', message: 'The task did not finish in time.' } }, null);
      await this.sleep(Date.now() - start > 60_000 ? 10_000 : 3_000);
    }
  }
  cancelResponse(id: string) { return this.request<HRResponse>('POST', `/v1/responses/${encodeURIComponent(id)}/cancel`, {}); }
  cancelSession(sessionId: string) { return this.request<{ status: string }>('POST', `/v1/sessions/${encodeURIComponent(sessionId)}/cancel`, {}); }

  async listFiles(sessionId: string, opts: { changed?: boolean } = {}): Promise<SessionFile[]> {
    const q = opts.changed ? '?changed=true' : '';
    return (await this.request<{ files: SessionFile[] }>('GET', `/v1/sessions/${encodeURIComponent(sessionId)}/files${q}`)).files || [];
  }
  /** Bytes of one file. The URL is built here, so the key only ever goes to the API origin. */
  async fetchFile(sessionId: string, fileId: string, view: 'content' | 'pdf' = 'content'): Promise<{ bytes: Uint8Array; contentType: string }> {
    const res = await this.raw('GET', `/v1/containers/${encodeURIComponent(sessionId)}/files/${encodeURIComponent(fileId)}/${view}`, undefined, { Accept: '*/*' });
    return { bytes: new Uint8Array(await res.arrayBuffer()), contentType: res.headers.get('content-type') || 'application/octet-stream' };
  }
}

// ── tasks: persisted with the product's user, consumed independently of the browser ──────────
export interface TaskRecord {
  taskId: string; userId: string; harnessId: string; idempotencyKey: string;
  status: 'starting' | 'in_progress' | 'completed' | 'incomplete' | 'failed' | 'cancelled';
  responseId?: string; sessionId?: string; answer?: string; files?: SessionFile[];
  incompleteReason?: string; updatedAt: number;
}
/** Back this with the product's database. MemoryTaskStore is for development and tests only. */
export interface TaskStore {
  get(taskId: string): Promise<TaskRecord | undefined>;
  put(rec: TaskRecord): Promise<void>;
}
export class MemoryTaskStore implements TaskStore {
  private readonly m = new Map<string, TaskRecord>();
  async get(id: string) { const r = this.m.get(id); return r ? { ...r } : undefined; }
  async put(rec: TaskRecord) { this.m.set(rec.taskId, { ...rec }); }
}

/** Browser listeners per task. A listener that leaves does not stop the task. */
const listeners = new Map<string, Set<(p: Progress) => void>>();
export function subscribe(taskId: string, fn: (p: Progress) => void): () => void {
  const set = listeners.get(taskId) ?? new Set();
  set.add(fn);
  listeners.set(taskId, set);
  return () => { set.delete(fn); if (!set.size) listeners.delete(taskId); };
}
function publish(taskId: string, p: Progress) {
  for (const fn of listeners.get(taskId) ?? []) { try { fn(p); } catch { /* a broken listener never stops the task */ } }
}

async function settle(hr: HarnessRouter, store: TaskStore, rec: TaskRecord, r: HRResponse): Promise<TaskRecord> {
  const sessionId = rec.sessionId || r.metadata?.session_id || '';
  let files: SessionFile[] = [];
  if (sessionId && r.status !== 'cancelled') {
    try { files = await hr.listFiles(sessionId, { changed: true }); } catch { files = []; }
  }
  const done: TaskRecord = {
    ...rec, responseId: rec.responseId || r.id, sessionId, status: r.status as TaskRecord['status'],
    answer: answerText(r), files, incompleteReason: r.incomplete_details?.reason, updatedAt: Date.now(),
  };
  await store.put(done);
  return done;
}

/**
 * Run one task for a product user. Call WITHOUT awaiting it from the request handler: it reads the
 * upstream stream to the end even after the browser goes away, persists the ids at
 * response.created and the result at the end. `rec` is the record the route created (status
 * "starting", a fresh idempotencyKey). For a follow-up pass previousResponseId and sessionId from
 * the stored record of the task being continued.
 */
export async function runTask(hr: HarnessRouter, store: TaskStore, rec: TaskRecord, input: unknown,
  followUp: { previousResponseId?: string; sessionId?: string } = {}): Promise<TaskRecord> {
  await store.put({ ...rec, updatedAt: Date.now() });
  try {
    const r = await hr.runStreamed(
      { harnessId: rec.harnessId, input, idempotencyKey: rec.idempotencyKey, ...followUp },
      {
        onIds: async ({ responseId, sessionId }) => {
          rec = { ...rec, responseId, sessionId, status: 'in_progress', updatedAt: Date.now() };
          await store.put(rec);
        },
        onEvent: (ev) => { const p = toProgress(ev); if (p) publish(rec.taskId, p); },
      },
    );
    return await settle(hr, store, rec, r);
  } catch (err) {
    const failed: TaskRecord = { ...rec, status: 'failed', updatedAt: Date.now() };
    await store.put(failed);
    publish(rec.taskId, { kind: 'done', status: 'failed' });
    if (!(err instanceof HRError)) throw err;
    return failed;
  }
}

/** After a server restart: finish every record that has a responseId but no terminal status. */
export async function recoverTask(hr: HarnessRouter, store: TaskStore, taskId: string): Promise<TaskRecord | undefined> {
  const rec = await store.get(taskId);
  if (!rec || !rec.responseId || TERMINAL_STATUSES.has(rec.status)) return rec;
  return settle(hr, store, rec, await hr.waitForResponse(rec.responseId));
}

// ── signed, sandboxed previews (files-artifacts-and-rendering.md) ─────────────────────────────
let processSecret: Buffer | null = null;
/** PREVIEW_SIGNING_SECRET (hex or base64, 32 bytes) from the server env; else a per-process random
 *  secret, which is fine in development (links stop working after a restart). */
export function previewSecret(): Buffer {
  const v = process.env.PREVIEW_SIGNING_SECRET?.trim();
  if (v) return /^[0-9a-f]{64}$/i.test(v) ? Buffer.from(v, 'hex') : Buffer.from(v, 'base64');
  return (processSecret ??= randomBytes(32));
}
const mac = (secret: Buffer, msg: string) => createHmac('sha256', secret).update(msg).digest('base64url');

/** "<taskId>.<expiresAt>.<signature>", for /preview/<token>/index.html. taskId must not contain dots. */
export function signPreview(taskId: string, secret: Buffer = previewSecret(), ttlSeconds = 3600, now = Date.now()): string {
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(taskId)) throw new Error('taskId must be [A-Za-z0-9_-]');
  const exp = Math.floor(now / 1000) + ttlSeconds;
  return `${taskId}.${exp}.${mac(secret, `${taskId}.${exp}`)}`;
}
/** The taskId when the token is genuine and unexpired, else null. Constant-time comparison. */
export function verifyPreview(token: string, secret: Buffer = previewSecret(), now = Date.now()): string | null {
  const m = /^([A-Za-z0-9_-]{1,128})\.(\d{1,12})\.([A-Za-z0-9_-]{43})$/.exec(token);
  if (!m) return null;
  const [, taskId, exp, sig] = m;
  if (Number(exp) * 1000 < now) return null;
  const want = Buffer.from(mac(secret, `${taskId}.${exp}`));
  const got = Buffer.from(sig);
  return want.length === got.length && timingSafeEqual(want, got) ? taskId : null;
}

export const PREVIEW_TYPES: Readonly<Record<string, string>> = {
  html: 'text/html; charset=utf-8', htm: 'text/html; charset=utf-8', css: 'text/css; charset=utf-8',
  js: 'text/javascript; charset=utf-8', mjs: 'text/javascript; charset=utf-8', json: 'application/json',
  txt: 'text/plain; charset=utf-8', md: 'text/plain; charset=utf-8', svg: 'image/svg+xml', png: 'image/png',
  jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp', ico: 'image/x-icon',
  woff: 'font/woff', woff2: 'font/woff2', ttf: 'font/ttf', otf: 'font/otf',
};
export const PREVIEW_HEADERS: Readonly<Record<string, string>> = {
  'Content-Security-Policy': "sandbox allow-scripts allow-forms; default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'none'; form-action 'none'; frame-ancestors 'self'",
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Cache-Control': 'private, no-store',
};

/** A relative path inside the output folder, or null for anything that could escape it. */
export function safeRelPath(p: string): string | null {
  let s: string;
  try { s = decodeURIComponent(p); } catch { return null; }
  if (!s || s.includes('\\') || s.includes('\0') || s.startsWith('/')) return null;
  const parts = s.split('/');
  if (parts.some((x) => x === '..' || x === '.' || x === '')) return null;
  return parts.join('/');
}

export interface Served { status: number; headers: Record<string, string>; body: Uint8Array | string }
const notFound: Served = { status: 404, headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' }, body: 'Not found' };

/**
 * The preview route's body, after verifyPreview() gave a taskId and the product loaded its record:
 * maps `relPath` to `<root>/<relPath>` in the session's files and serves it with the sandbox CSP.
 */
export async function previewFile(hr: HarnessRouter, sessionId: string, root: string, relPath: string): Promise<Served> {
  const rel = safeRelPath(relPath || 'index.html');
  if (!rel) return notFound;
  const ext = (rel.split('.').pop() || '').toLowerCase();
  const type = PREVIEW_TYPES[ext];
  if (!type) return notFound;
  const want = root ? `${root.replace(/\/+$/, '')}/${rel}` : rel;
  const file = (await hr.listFiles(sessionId)).find((f) => f.path === want);
  if (!file) return notFound;
  const { bytes } = await hr.fetchFile(sessionId, file.id);
  return { status: 200, headers: { ...PREVIEW_HEADERS, 'Content-Type': type }, body: bytes };
}

/** The download route's body (owner already checked): the original bytes as an attachment. */
export async function downloadFile(hr: HarnessRouter, sessionId: string, path: string): Promise<Served> {
  const file = (await hr.listFiles(sessionId)).find((f) => f.path === path);
  if (!file) return notFound;
  const { bytes, contentType } = await hr.fetchFile(sessionId, file.id);
  const name = file.filename.replace(/["\r\n\\]/g, '_');
  return {
    status: 200, body: bytes,
    headers: { 'Content-Type': contentType, 'Content-Disposition': `attachment; filename="${name}"`, 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store' },
  };
}
