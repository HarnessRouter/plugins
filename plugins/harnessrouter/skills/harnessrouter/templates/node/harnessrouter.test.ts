// License: Apache-2.0; scope and full text: ../../LICENSING.md
// Unit tests for harnessrouter.ts with mocked HTTP and SSE. Run: node --test templates/node/harnessrouter.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  HRError, HarnessRouter, MemoryTaskStore, PREVIEW_HEADERS, answerText, downloadFile, loadApiKey,
  parseSSE, previewFile, producedFiles, recoverTask, runTask, safeRelPath, signPreview, subscribe,
  toProgress, verifyPreview, type HRResponse, type StreamEvent, type TaskRecord,
} from './harnessrouter.ts';

const SID = 'hsess0001';
const RID = 'resp_0001';
const FILES = [
  { object: 'file', id: 'cfile_a', file_id: 'cfile_a', container_id: SID, filename: 'index.html', path: 'site/index.html', bytes: 40, media_type: 'text/html', download_url: `https://api.harnessrouter.ai/v1/containers/${SID}/files/cfile_a/content` },
  { object: 'file', id: 'cfile_b', file_id: 'cfile_b', container_id: SID, filename: 'style.css', path: 'site/style.css', bytes: 20, media_type: 'text/css', download_url: `https://api.harnessrouter.ai/v1/containers/${SID}/files/cfile_b/content` },
];
const FINAL: HRResponse = {
  id: RID, object: 'response', status: 'completed', output: [
    { type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'Working on it.', annotations: [] }] },
    { type: 'function_call', name: 'write', arguments: '{}', call_id: 'call_1', status: 'completed' },
    { type: 'function_call_output', call_id: 'call_1', output: 'ok' },
    { type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'Made ', annotations: [] }, { type: 'output_text', text: 'two files.', annotations: [
      { type: 'container_file_citation', container_id: SID, file_id: 'cfile_a', filename: 'site/index.html', download_url: FILES[0].download_url, start_index: 0, end_index: 9 },
    ] }] },
  ], metadata: { session_id: SID },
};
const created = { id: RID, object: 'response', status: 'in_progress', output: [], metadata: { session_id: SID } };
const frames = (evs: unknown[]) => evs.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('');
const STREAM = frames([
  { type: 'response.created', sequence_number: 0, response: created },
  { type: 'response.in_progress', sequence_number: 1, response: created },
  { type: 'response.output_item.added', sequence_number: 2, output_index: 0, item: { type: 'function_call', name: 'Write', arguments: '' } },
  { type: 'response.output_text.delta', sequence_number: 3, delta: 'Made two files.' },
  { type: 'response.completed', sequence_number: 4, response: FINAL },
]);

function streamOf(text: string, chunk = 7): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(text);
  let i = 0;
  return new ReadableStream({ pull(c) { if (i >= bytes.length) { c.close(); return; } c.enqueue(bytes.slice(i, i + chunk)); i += chunk; } });
}
async function collect(s: ReadableStream<Uint8Array>): Promise<StreamEvent[]> {
  const out: StreamEvent[] = [];
  for await (const e of parseSSE(s)) out.push(e);
  return out;
}

interface Call { url: string; method: string; headers: Record<string, string>; body: unknown }
function mockFetch(route: (c: Call) => Response): { fetch: typeof fetch; calls: Call[] } {
  const calls: Call[] = [];
  const f = (async (input: string | URL | Request, init?: RequestInit) => {
    const h: Record<string, string> = {};
    for (const [k, v] of Object.entries((init?.headers ?? {}) as Record<string, string>)) h[k.toLowerCase()] = v;
    const c = { url: String(input), method: init?.method ?? 'GET', headers: h, body: init?.body ? JSON.parse(String(init.body)) : undefined };
    calls.push(c);
    return route(c);
  }) as typeof fetch;
  return { fetch: f, calls };
}
const json = (v: unknown, status = 200, headers: Record<string, string> = {}) => new Response(JSON.stringify(v), { status, headers: { 'content-type': 'application/json', ...headers } });
const client = (f: typeof fetch) => new HarnessRouter({ apiKey: 'sk-hr-testtesttest', fetch: f, sleep: async () => {} });

test('parseSSE: chunked frames, CRLF, comments, [DONE], junk and multi-line data', async () => {
  const text = ': keepalive\r\n\r\n' + STREAM.replace(/\n/g, '\r\n') + 'data: [DONE]\n\ndata: not json\n\ndata: {"type":\ndata: "x.multi"}\n\nevent: ignored\ndata: {"type":"x.tail"}';
  const evs = await collect(streamOf(text, 5));
  assert.deepEqual(evs.map((e) => e.type), ['response.created', 'response.in_progress', 'response.output_item.added', 'response.output_text.delta', 'response.completed', 'x.multi', 'x.tail']);
});

test('answerText takes the last message; producedFiles reads container_file_citation', () => {
  assert.equal(answerText(FINAL), 'Made two files.');
  assert.deepEqual(producedFiles(FINAL).map((a) => a.filename), ['site/index.html']);
});

test('toProgress maps only safe, plain progress', () => {
  assert.deepEqual(toProgress({ type: 'response.output_text.delta', delta: 'hi' }), { kind: 'text', delta: 'hi' });
  assert.deepEqual(toProgress({ type: 'response.output_item.added', item: { type: 'function_call', name: 'Write' } }), { kind: 'activity', label: 'Writing files' });
  assert.deepEqual(toProgress({ type: 'response.failed', response: { ...FINAL, status: 'cancelled' } }), { kind: 'done', status: 'cancelled' });
  assert.equal(toProgress({ type: 'response.content_part.added' }), null);
});

test('runStreamed sends the documented request and persists ids at response.created', async () => {
  const { fetch, calls } = mockFetch(() => new Response(streamOf(STREAM), { status: 200, headers: { 'content-type': 'text/event-stream' } }));
  const order: string[] = [];
  const r = await client(fetch).runStreamed(
    { harnessId: 'chrn_1', input: 'hello', previousResponseId: 'resp_0', sessionId: SID, idempotencyKey: 'k-1' },
    { onIds: (ids) => { order.push(`ids:${ids.responseId}:${ids.sessionId}`); }, onEvent: (e) => { order.push(e.type); } },
  );
  assert.equal(r.status, 'completed');
  assert.equal(order[0], `ids:${RID}:${SID}`);
  const c = calls[0];
  assert.equal(c.url, 'https://api.harnessrouter.ai/v1/responses');
  assert.equal(c.method, 'POST');
  assert.equal(c.headers.authorization, 'Bearer sk-hr-testtesttest');
  assert.equal(c.headers['uhp-version'], '2026-09-28');
  assert.equal(c.headers['idempotency-key'], 'k-1');
  assert.equal(c.headers.accept, 'text/event-stream');
  assert.deepEqual(c.body, { input: 'hello', metadata: { harness_id: 'chrn_1', session_id: SID }, previous_response_id: 'resp_0', stream: true });
});

test('a stream that ends without a terminal event is recovered by polling, not resent', async () => {
  const partial = frames([{ type: 'response.created', response: created }, { type: 'response.output_text.delta', delta: 'x' }]);
  let polls = 0;
  const { fetch, calls } = mockFetch((c) => {
    if (c.method === 'POST') return new Response(streamOf(partial), { status: 200 });
    polls += 1;
    return json(polls < 3 ? { ...created } : FINAL);
  });
  const r = await client(fetch).runStreamed({ harnessId: 'chrn_1', input: 'x' });
  assert.equal(r.status, 'completed');
  assert.equal(calls.filter((c) => c.method === 'POST').length, 1);
  assert.ok(calls.slice(1).every((c) => c.url.endsWith(`/v1/responses/${RID}`)));
});

test('a replayed stream (created without metadata) still yields the ids', async () => {
  const replay = frames([{ type: 'response.created', response: { id: RID, object: 'response', status: 'completed', output: [] } }, { type: 'response.completed', response: FINAL }]);
  const { fetch } = mockFetch(() => new Response(streamOf(replay), { status: 200 }));
  const seen: string[] = [];
  await client(fetch).runStreamed({ harnessId: 'chrn_1', input: 'x' }, { onIds: (i) => { seen.push(i.sessionId); } });
  assert.deepEqual(seen, [SID]);
});

test('HRError reads the UHP envelope and the legacy detail', async () => {
  const { fetch } = mockFetch((c) => c.url.endsWith('/v1/nope')
    ? json({ detail: 'Not Found' }, 404)
    : json({ error: { type: 'invalid_request_error', code: 'session_busy', message: 'busy', param: 'session_id' }, detail: 'busy' }, 409, { 'retry-after': '3' }));
  const hr = client(fetch);
  await assert.rejects(hr.request('GET', '/v1/nope'), (e: unknown) => e instanceof HRError && e.status === 404 && e.message === 'Not Found');
  await assert.rejects(hr.request('POST', '/v1/responses', {}), (e: unknown) => e instanceof HRError && e.code === 'session_busy' && e.param === 'session_id' && !e.retryable && e.retryAfterSeconds === 3);
});

test('runTask persists, publishes progress, settles with changed files; recoverTask polls', async () => {
  const { fetch } = mockFetch((c) => {
    if (c.method === 'POST') return new Response(streamOf(STREAM), { status: 200 });
    if (c.url.includes('/files')) return json({ session_id: SID, count: 2, files: FILES });
    return json(FINAL);
  });
  const hr = client(fetch);
  const store = new MemoryTaskStore();
  const rec: TaskRecord = { taskId: 't1', userId: 'u1', harnessId: 'chrn_1', idempotencyKey: 'k', status: 'starting', updatedAt: 0 };
  const got: string[] = [];
  const off = subscribe('t1', (p) => { got.push(p.kind); });
  const done = await runTask(hr, store, rec, 'go');
  off();
  assert.equal(done.status, 'completed');
  assert.equal(done.answer, 'Made two files.');
  assert.deepEqual(done.files?.map((f) => f.path), ['site/index.html', 'site/style.css']);
  assert.deepEqual(got, ['activity', 'text', 'done']);
  await store.put({ ...done, taskId: 't2', status: 'in_progress' });
  assert.equal((await recoverTask(hr, store, 't2'))?.status, 'completed');
});

test('signPreview / verifyPreview: genuine, tampered, expired, malformed', () => {
  const secret = Buffer.alloc(32, 7);
  const now = 1_800_000_000_000;
  const tok = signPreview('task_1', secret, 60, now);
  assert.equal(verifyPreview(tok, secret, now), 'task_1');
  assert.equal(verifyPreview(tok, Buffer.alloc(32, 8), now), null);
  assert.equal(verifyPreview(tok.replace('task_1', 'task_2'), secret, now), null);
  assert.equal(verifyPreview(tok, secret, now + 61_000), null);
  assert.equal(verifyPreview('x.y.z', secret, now), null);
  assert.throws(() => signPreview('a.b', secret));
});

test('safeRelPath refuses escapes', () => {
  assert.equal(safeRelPath('index.html'), 'index.html');
  assert.equal(safeRelPath('css/app.css'), 'css/app.css');
  for (const bad of ['../x', 'a/../b', '/etc/passwd', 'a\\b', '', 'a//b', '%2e%2e/x', 'a/./b']) assert.equal(safeRelPath(bad), null, bad);
});

test('previewFile maps to <root>/<path>, sets the sandbox headers, allows known types only', async () => {
  const { fetch, calls } = mockFetch((c) => {
    if (c.url.endsWith('/files')) return json({ session_id: SID, count: 2, files: FILES });
    return new Response('<h1>Hi</h1>', { status: 200, headers: { 'content-type': 'text/html', 'content-disposition': 'attachment; filename="index.html"' } });
  });
  const hr = client(fetch);
  const ok = await previewFile(hr, SID, 'site', 'index.html');
  assert.equal(ok.status, 200);
  assert.equal(ok.headers['Content-Type'], 'text/html; charset=utf-8');
  assert.equal(ok.headers['Content-Security-Policy'], PREVIEW_HEADERS['Content-Security-Policy']);
  assert.equal(ok.headers['X-Content-Type-Options'], 'nosniff');
  assert.equal(ok.headers['Referrer-Policy'], 'no-referrer');
  assert.equal(ok.headers['Cache-Control'], 'private, no-store');
  assert.ok(calls.some((c) => c.url === `https://api.harnessrouter.ai/v1/containers/${SID}/files/cfile_a/content`));
  assert.equal((await previewFile(hr, SID, 'site', 'missing.html')).status, 404);
  assert.equal((await previewFile(hr, SID, 'site', '../site/index.html')).status, 404);
  assert.equal((await previewFile(hr, SID, 'site', 'run.exe')).status, 404);
  const dl = await downloadFile(hr, SID, 'site/style.css');
  assert.equal(dl.headers['Content-Disposition'], 'attachment; filename="style.css"');
});

test('loadApiKey: env wins; the file must be one HR_API_KEY line', () => {
  const dir = mkdtempSync(join(tmpdir(), 'hr-key-'));
  const saved = process.env.HR_API_KEY;
  try {
    delete process.env.HR_API_KEY;
    writeFileSync(join(dir, '.env.harnessrouter'), 'HR_API_KEY=sk-hr-fromfile123\n');
    assert.equal(loadApiKey(dir), 'sk-hr-fromfile123');
    writeFileSync(join(dir, '.env.harnessrouter'), 'HR_API_KEY=a\nOTHER=b\n');
    assert.throws(() => loadApiKey(dir));
    process.env.HR_API_KEY = 'sk-hr-fromenv1234';
    assert.equal(loadApiKey(dir), 'sk-hr-fromenv1234');
  } finally {
    if (saved === undefined) delete process.env.HR_API_KEY; else process.env.HR_API_KEY = saved;
  }
});

test('findHarnessByName matches the exact name; replaceHarness sends If-Match', async () => {
  const { fetch, calls } = mockFetch((c) => c.method === 'GET'
    ? json({ harnesses: [{ id: 'chrn_1', name: 'Support replies' }, { id: 'chrn_2', name: 'Support replies v2' }] })
    : json({ id: 'chrn_1', name: 'Support replies' }));
  const hr = client(fetch);
  assert.equal((await hr.findHarnessByName('Support replies'))?.id, 'chrn_1');
  assert.equal(await hr.findHarnessByName('support replies'), undefined);
  await hr.replaceHarness('chrn_1', { name: 'Support replies', base: 'hermes' }, '"e1"');
  assert.equal(calls[calls.length - 1].headers['if-match'], '"e1"');
});
