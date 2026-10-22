import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { DocumentsPage } from './pages/DocumentsPage';
import { ReferencesPage } from './pages/ReferencesPage';
import { HistoryPage } from './pages/HistoryPage';
import { WorkbenchPage } from './pages/WorkbenchPage';
import { SessionBoundary } from './session';
import '../tokens.css';
import '../formal.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 15_000, retry: false, refetchOnWindowFocus: false },
    mutations: { retry: false },
  },
});

export function FormalApp() {
  useEffect(() => {
    const previous = document.title;
    document.title = '修途 · 正式工作台';
    return () => { document.title = previous; };
  }, []);
  return <QueryClientProvider client={queryClient}><SessionBoundary><BrowserRouter>
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/workbench/:caseId?" element={<WorkbenchPage />} />
        <Route path="/documents" element={<ReferencesPage />} />
        <Route path="/documents/legacy" element={<DocumentsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="*" element={<Navigate to="/workbench" replace />} />
      </Route>
    </Routes>
  </BrowserRouter></SessionBoundary></QueryClientProvider>;
}
