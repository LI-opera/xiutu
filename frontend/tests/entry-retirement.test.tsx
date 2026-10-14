import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { FormalApp } from '../src/formal/FormalApp';

vi.mock('../src/formal/session', () => ({
  SessionBoundary: ({ children }: { children: React.ReactNode }) => children,
  useSession: () => ({ logout: vi.fn() }),
}));
vi.mock('../src/formal/pages/WorkbenchPage', () => ({ WorkbenchPage: () => <div>workbench destination</div> }));
vi.mock('../src/formal/pages/DocumentsPage', () => ({ DocumentsPage: () => <div>documents destination</div> }));
vi.mock('../src/formal/pages/HistoryPage', () => ({ HistoryPage: () => <div>history destination</div> }));
afterEach(() => { cleanup(); window.history.replaceState(null, '', '/'); });

it.each(['/preview', '/design/workbench-v2', '/#diagnosis', '/#dkvb', '/unknown'])('redirects retired or unknown entry %s to workbench', async path => {
  window.history.replaceState(null, '', path);
  render(<FormalApp />);
  expect(await screen.findByText('workbench destination')).toBeTruthy();
  await waitFor(() => expect(window.location.pathname).toBe('/workbench'));
  expect(window.location.hash).toBe('');
  expect(screen.queryByRole('link', { name: '已接受预览' })).toBeNull();
});

it.each([
  ['/documents', 'documents destination'], ['/history', 'history destination'],
  ['/workbench/legacy-case?legacy=1', 'workbench destination'],
])('preserves formal route %s', async (path, text) => {
  window.history.replaceState(null, '', path);
  render(<FormalApp />);
  expect(await screen.findByText(text)).toBeTruthy();
  expect(window.location.pathname + window.location.search).toBe(path);
});
