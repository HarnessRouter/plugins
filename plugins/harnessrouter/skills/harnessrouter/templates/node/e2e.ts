// License: Apache-2.0; scope and full text: ../../LICENSING.md
/**
 * Live end-to-end check of harnessrouter.ts: one real streamed task, ids persisted at
 * response.created, recovery by polling, file list, a signed sandboxed preview and a download.
 *
 *   node templates/node/e2e.ts --project <dir with .env.harnessrouter> --harness chrn_…
 *
 * The key comes from HR_API_KEY or <project>/.env.harnessrouter; it is never printed. The task
 * asks for two small files under site/, so it costs a fraction of a cent on a small model.
 */
import { randomUUID } from 'node:crypto';
import {
  HarnessRouter, MemoryTaskStore, PREVIEW_HEADERS, downloadFile, loadApiKey, previewFile,
  recoverTask, runTask, signPreview, subscribe, verifyPreview, type TaskRecord,
} from './harnessrouter.ts';

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : undefined;
}

const project = arg('--project') ?? process.cwd();
const harnessId = arg('--harness') ?? process.env.HR_HARNESS_ID ?? '';
if (!harnessId) { console.error(JSON.stringify({ ok: false, error: 'pass --harness or HR_HARNESS_ID' })); process.exit(2); }

const checks: Record<string, boolean> = {};
const hr = new HarnessRouter({ apiKey: loadApiKey(project) });
const me = await hr.me();

class WatchedStore extends MemoryTaskStore {
  idsBeforeEnd = false;
  async put(rec: TaskRecord) {
    if (rec.responseId && rec.sessionId && rec.status === 'in_progress') this.idsBeforeEnd = true;
    await super.put(rec);
  }
}
const store = new WatchedStore();
const taskId = randomUUID().replace(/-/g, '');
const rec: TaskRecord = { taskId, userId: 'e2e', harnessId, idempotencyKey: randomUUID(), status: 'starting', updatedAt: Date.now() };
let progress = 0;
const leave = subscribe(taskId, () => { progress += 1; });
const t0 = Date.now();
const done = await runTask(hr, store, rec,
  'Write site/index.html with an h1 that says Hello and a stylesheet link to style.css, and site/style.css that makes the h1 blue. Then reply with one short line.');
leave();
checks.completed = done.status === 'completed';
checks.ids_saved_at_created = store.idsBeforeEnd;
checks.answer = !!done.answer && done.answer.length > 0;
checks.progress_events = progress > 0;
const paths = (done.files ?? []).map((f) => f.path);
checks.files_listed = paths.includes('site/index.html') && paths.includes('site/style.css');

// recovery: a record left "in_progress" (as after a restart) is finished by polling
await store.put({ ...done, taskId: taskId + 'r', status: 'in_progress' });
const rec2 = await recoverTask(hr, store, taskId + 'r');
checks.recover_by_polling = rec2?.status === 'completed';

// signed sandboxed preview
const token = signPreview(taskId);
checks.preview_token = verifyPreview(token) === taskId && verifyPreview(token.slice(0, -2) + 'xx') === null;
const page = await previewFile(hr, done.sessionId!, 'site', 'index.html');
const css = await previewFile(hr, done.sessionId!, 'site', 'style.css');
const escape = await previewFile(hr, done.sessionId!, 'site', '../site/index.html');
checks.preview_html = page.status === 200 && page.headers['Content-Security-Policy'] === PREVIEW_HEADERS['Content-Security-Policy']
  && /<h1/i.test(Buffer.from(page.body as Uint8Array).toString('utf8'));
checks.preview_css = css.status === 200 && css.headers['Content-Type'].startsWith('text/css');
checks.preview_rejects_escape = escape.status === 404;
const dl = await downloadFile(hr, done.sessionId!, 'site/index.html');
checks.download_attachment = dl.status === 200 && /^attachment;/.test(dl.headers['Content-Disposition'] ?? '');

const ok = Object.values(checks).every(Boolean);
console.log(JSON.stringify({
  ok, workspace: me.workspace_name, status: done.status, seconds: Math.round((Date.now() - t0) / 1000),
  files: paths, progress_events: progress, answer_chars: done.answer?.length ?? 0, checks,
}));
process.exit(ok ? 0 : 1);
