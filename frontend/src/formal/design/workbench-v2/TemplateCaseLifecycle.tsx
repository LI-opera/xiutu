import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { apiClient, errorText } from '../../api-client';

export function TemplateCaseLifecycle({ caseId, revision, closed, onChanged }: {caseId:string; revision:number; closed:boolean; onChanged:()=>void}) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const client = useQueryClient();
  async function save() {
    setBusy(true); setError('');
    try {
      await apiClient.request(`/cases/${caseId}/template-lifecycle`, {method:'POST', body:{expected_revision:revision, closed:!closed}});
      await client.invalidateQueries({queryKey:['case-history']});
      await client.invalidateQueries({queryKey:['case',caseId]});
      setConfirm(false); onChanged();
    } catch (cause) {setError(errorText(cause)); onChanged();}
    finally {setBusy(false);}
  }
  return <section className="prototype-intake">
    <b>{closed ? '本次工作已结束，记录保留' : '本病例正在进行'}</b>
    {closed ? <button className="prototype-button subtle" disabled={busy} onClick={()=>void save()}>继续此病例</button>
      : <button className="prototype-button subtle" disabled={busy} onClick={()=>setConfirm(true)}>结束本次工作</button>}
    {confirm && !closed && <div><p>结束后保留全部检查、分析和处理复检记录；未完成的复检仍会标注。结束不表示故障已修复，之后可继续此病例。</p>
      <button className="prototype-button" disabled={busy} onClick={()=>void save()}>确认结束</button>
      <button className="prototype-button subtle" disabled={busy} onClick={()=>setConfirm(false)}>暂不结束</button></div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
