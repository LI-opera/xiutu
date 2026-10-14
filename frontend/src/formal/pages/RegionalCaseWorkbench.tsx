import { useCallback, useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api-client';
import { ErrorState, LoadingState, StatusBadge } from '../components/States';
import { CurrentStep, EvidenceDrawer, stepFrom } from '../diagnosis/ArchivedReadParts';
import { observationSummary } from '../diagnosis/presentation';
import { CaseHeader, CaseSynthesisPanel, ComponentActionPreview, ComponentNavigator, DiagnosticAreaGrid, VehicleFaultSummary } from '../diagnosis/RegionalWorkbench';
import type { DiagnosisView, FinalReportGate, ObservationList, ProtocolDecision, WorkbenchView } from '../diagnosis/types';
import type { CaseSnapshot } from '../types';

export function RegionalCaseWorkbench({ caseId }: { caseId: string }) {
  const client = useQueryClient();
  const [evidenceIds, setEvidenceIds] = useState<string[]>([]);
  const [selectedAreaId, setSelectedAreaId] = useState('');
  const [selectedComponentId, setSelectedComponentId] = useState('');
  const [newlyCompleted, setNewlyCompleted] = useState<Set<string>>(new Set());
  const snapshot = useQuery({ queryKey: ['case', caseId], queryFn: ({ signal }) => apiClient.request<CaseSnapshot>(`/cases/${caseId}`, { signal }) });
  const diagnosis = useQuery({ queryKey: ['diagnosis', caseId], queryFn: ({ signal }) => apiClient.request<DiagnosisView>(`/cases/${caseId}/diagnosis`, { signal }) });
  const workbench = useQuery({ queryKey: ['workbench-view', caseId], queryFn: ({ signal }) => apiClient.request<WorkbenchView>(`/cases/${caseId}/workbench-view`, { signal }) });
  const observations = useQuery({ queryKey: ['observations', caseId], queryFn: ({ signal }) => apiClient.request<ObservationList>(`/cases/${caseId}/observations`, { signal }) });
  const gate = useQuery({ queryKey: ['report-gate', caseId], queryFn: ({ signal }) => apiClient.request<FinalReportGate>(`/cases/${caseId}/reports/gate`, { signal }) });
  const refresh = useCallback(async () => { await Promise.all([
    client.invalidateQueries({ queryKey: ['case', caseId] }), client.invalidateQueries({ queryKey: ['diagnosis', caseId] }),
    client.invalidateQueries({ queryKey: ['workbench-view', caseId] }), client.invalidateQueries({ queryKey: ['observations', caseId] }),
    client.invalidateQueries({ queryKey: ['reports', caseId] }), client.invalidateQueries({ queryKey: ['report-gate', caseId] }),
  ]); }, [caseId, client]);

  const view = workbench.data;
  const currentCheckId = view?.current_action?.check_id ?? '';
  useEffect(() => {
    if (!view) return;
    setSelectedAreaId(view.selected_area_id);
    const area = view.areas.find(item => item.area_id === view.selected_area_id);
    setSelectedComponentId(view.current_component?.component_id ?? area?.components[0]?.component_id ?? '');
  }, [caseId, view?.selected_area_id, currentCheckId]);
  useEffect(() => {
    if (!view) return;
    const key = `xiutu:completed-areas:${caseId}`;
    const now = view.areas.filter(area => area.status === 'completed').map(area => area.area_id);
    const raw = sessionStorage.getItem(key);
    const before = raw ? JSON.parse(raw) as string[] : now;
    setNewlyCompleted(new Set(now.filter(id => !before.includes(id))));
    sessionStorage.setItem(key, JSON.stringify(now));
  }, [caseId, view]);

  if (snapshot.isPending || diagnosis.isPending || workbench.isPending || observations.isPending || gate.isPending) return <LoadingState label="正在恢复区域化诊断工作台" />;
  const firstError = snapshot.error ?? diagnosis.error ?? workbench.error ?? observations.error ?? gate.error;
  if (firstError || !snapshot.data || !diagnosis.data || !workbench.data || !observations.data) return <ErrorState error={firstError ?? new Error('工作台数据不完整')} onRetry={() => refresh()} />;

  const readyItem = snapshot.data;
  const readyDiagnosis = diagnosis.data;
  const readyView = workbench.data;
  const current = readyDiagnosis.current_step;
  const candidate = stepFrom(readyDiagnosis);
  const protocol = (current?.validation as { protocol?: ProtocolDecision } | undefined)?.protocol ?? null;
  const selectedArea = readyView.areas.find(area => area.area_id === selectedAreaId) ?? readyView.areas[0];
  const currentArea = readyView.areas.find(area => area.area_id === readyView.selected_area_id);
  const selectedComponent = selectedArea?.components.find(component => component.component_id === selectedComponentId) ?? selectedArea?.components[0];
  const isCurrentComponent = Boolean(selectedArea && selectedComponent && selectedArea.area_id === readyView.selected_area_id && selectedComponent.actions.some(action => action.check_id === currentCheckId));
  const selectArea = (areaId: string) => {
    const area = readyView.areas.find(item => item.area_id === areaId);
    setSelectedAreaId(areaId);
    setSelectedComponentId(area?.components.find(component => component.status === 'current')?.component_id ?? area?.components[0]?.component_id ?? '');
  };
  const returnCurrent = () => {
    setSelectedAreaId(readyView.selected_area_id);
    setSelectedComponentId(readyView.current_component?.component_id ?? currentArea?.components[0]?.component_id ?? '');
  };
  return <div className="workbench regional-workbench">
    <p className="prototype-warning" role="status">历史病例已归档，仅供查看；原有待输入步骤不会继续执行。</p>
    <CaseHeader view={readyView} />
    <VehicleFaultSummary view={readyView} />
    <DiagnosticAreaGrid areas={readyView.areas} selectedId={selectedArea.area_id} newlyCompleted={newlyCompleted} onSelect={selectArea} />
    <section className="regional-detail-shell">
      <ComponentNavigator area={selectedArea} selectedId={selectedComponent?.component_id ?? ''} onSelect={setSelectedComponentId} />
      <div className="regional-action-column">
        {selectedComponent && <ComponentActionPreview component={selectedComponent} isCurrent={isCurrentComponent} onReturn={returnCurrent} />}
        {isCurrentComponent && candidate && current ? <section className="live-check-action"><CurrentStep candidate={candidate} protocol={protocol} onEvidence={setEvidenceIds} /><p>此待输入步骤已归档，仅供查看。</p></section> : !current && <article className="regional-terminal-note"><StatusBadge value={readyView.synthesis.status === 'demo_complete' ? '演示路径已完成' : '当前专题已交接'} tone={readyView.synthesis.status === 'demo_complete' ? 'good' : 'warn'} /><p>{readyView.synthesis.next_recommendations[0]}</p></article>}
      </div>
    </section>
    <CaseSynthesisPanel view={readyView} gate={gate.data ?? null} />
    <details className="saved-facts-panel" id="saved-observations"><summary>查看已保存事实与更正（{observations.data.items.length}）</summary><div className="saved-facts-grid">{observations.data.items.map(obs => <article key={obs.id}><div className="badge-row"><StatusBadge value={obs.kind === 'intake_snapshot' ? '系统接诊事实' : obs.kind === 'unavailable' ? '无法完成' : '用户观察'} /><StatusBadge value={obs.effective ? '有效' : '已被更正'} tone={obs.effective ? 'good' : 'warn'} /></div><p>{observationSummary(obs)}</p><details><summary>查看历史详情</summary><small>revision {obs.created_revision}</small><details><summary>技术负载</summary><pre>{JSON.stringify(obs.payload, null, 2)}</pre></details></details></article>)}</div></details>
    <EvidenceDrawer evidenceIds={evidenceIds} onClose={() => setEvidenceIds([])} />
  </div>;
}
