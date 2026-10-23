import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from '../src/App';

vi.mock('../src/lib/session', () => ({
  SessionBoundary: ({ children }: { children: React.ReactNode }) => children,
  useSession: () => ({ logout: vi.fn() }),
}));
vi.mock('../src/pages/WorkbenchPage', () => ({ WorkbenchPage: () => <div>workbench destination</div> }));
vi.mock('../src/pages/ReferencesPage', () => ({ ReferencesPage: () => <div>documents destination</div> }));
vi.mock('../src/pages/HistoryPage', () => ({ HistoryPage: () => <div>history destination</div> }));
afterEach(() => { cleanup(); window.history.replaceState(null, '', '/'); });

it.each(['/preview', '/design/workbench-v2', '/documents/legacy', '/#diagnosis', '/unknown'])('redirects retired or unknown entry %s to workbench', async path => {
  window.history.replaceState(null, '', path);
  render(<App />);
  expect(await screen.findByText('workbench destination')).toBeTruthy();
  await waitFor(() => expect(window.location.pathname).toBe('/workbench'));
  expect(window.location.hash).toBe('');
  expect(screen.queryByRole('link', { name: '已接受预览' })).toBeNull();
});

it.each([
  ['/documents', 'documents destination'],
  ['/history', 'history destination'],
  ['/workbench/some-case', 'workbench destination'],
])('preserves formal route %s', async (path, text) => {
  window.history.replaceState(null, '', path);
  render(<App />);
  expect(await screen.findByText(text)).toBeTruthy();
  expect(window.location.pathname + window.location.search).toBe(path);
});
