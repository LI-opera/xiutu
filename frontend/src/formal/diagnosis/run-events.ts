export type RunEvent = { id: string; type: string; data: unknown };

type Recovery = { terminal: boolean; resetCursor?: boolean };
type Options = {
  runId: string;
  signal: AbortSignal;
  contextValid: () => boolean;
  onEvent: (event: RunEvent) => void | Promise<void>;
  onDisconnect: () => Promise<Recovery>;
  fetcher?: typeof fetch;
  reconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
  onRecoveryError?: (error: unknown | null) => void;
};

const terminalEvents = new Set(['run.succeeded', 'run.failed', 'run.cancelled', 'run.superseded', 'run.waiting_input']);

function parseBlock(block: string): RunEvent | null {
  let id = '';
  let type = 'message';
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(':')) continue;
    const split = line.indexOf(':');
    const field = split < 0 ? line : line.slice(0, split);
    const value = split < 0 ? '' : line.slice(split + 1).replace(/^ /, '');
    if (field === 'id') id = value;
    else if (field === 'event') type = value;
    else if (field === 'data') data.push(value);
  }
  if (!id && !data.length) return null;
  let parsed: unknown = null;
  if (data.length) {
    const raw = data.join('\n');
    try { parsed = JSON.parse(raw); } catch { parsed = raw; }
  }
  return { id, type, data: parsed };
}

export async function consumeRunEvents(options: Options): Promise<void> {
  const fetcher = options.fetcher ?? fetch;
  const seen = new Set<string>();
  let cursor: string | null = null;
  let recoveryFailures = 0;
  while (!options.signal.aborted && options.contextValid()) {
    try {
      const headers = new Headers({ Accept: 'text/event-stream' });
      if (cursor !== null) headers.set('Last-Event-ID', cursor);
      const response = await fetcher(`/api/v2/runs/${encodeURIComponent(options.runId)}/events`, {
        credentials: 'same-origin', headers, signal: options.signal,
      });
      if (!response.ok || !response.body) throw new Error(`SSE_HTTP_${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let pending = '';
      let terminal = false;
      while (!terminal && options.contextValid() && !options.signal.aborted) {
        const chunk = await reader.read();
        pending += decoder.decode(chunk.value ?? new Uint8Array(), { stream: !chunk.done });
        const blocks = pending.split(/\r?\n\r?\n/);
        pending = blocks.pop() ?? '';
        for (const block of blocks) {
          if (!options.contextValid() || options.signal.aborted) break;
          const event = parseBlock(block);
          if (!event) continue;
          if (event.type === 'reset_required') {
            cursor = null;
            seen.clear();
            await options.onEvent(event);
            continue;
          }
          if (event.id && seen.has(event.id)) continue;
          if (event.id) { seen.add(event.id); cursor = event.id; }
          await options.onEvent(event);
          terminal ||= terminalEvents.has(event.type);
        }
        if (chunk.done) break;
      }
      reader.releaseLock();
      if (terminal || options.signal.aborted || !options.contextValid()) return;
    } catch (error) {
      if (options.signal.aborted || !options.contextValid()) return;
      if (error instanceof DOMException && error.name === 'AbortError') return;
    }
    let recovery: Recovery;
    try {
      recovery = await options.onDisconnect();
      recoveryFailures = 0;
      options.onRecoveryError?.(null);
    } catch (error) {
      if (options.signal.aborted || !options.contextValid()) return;
      recoveryFailures += 1;
      options.onRecoveryError?.(error);
      recovery = { terminal: false };
    }
    if (!options.contextValid() || options.signal.aborted || recovery.terminal) return;
    if (recovery.resetCursor) { cursor = null; seen.clear(); }
    await new Promise<void>((resolve) => {
      const base = options.reconnectDelayMs ?? 500;
      const delay = Math.min(base * 2 ** Math.max(0, recoveryFailures - 1), options.maxReconnectDelayMs ?? 5_000);
      const timer = window.setTimeout(resolve, delay);
      options.signal.addEventListener('abort', () => {
        window.clearTimeout(timer); resolve();
      }, { once: true });
    });
  }
}
