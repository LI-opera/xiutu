import { useRef, useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { apiClient, idempotencyKey } from '../../api-client';
import { ErrorState } from '../../components/States';
import type { CaseSnapshot } from '../../types';

export type MatchedVehicleDraft = { brand: string; model: string; year: string; engine: string; complaint: string; codes: string; condition: string; safety: string };
const empty: Draft = { brand: '', model: '', year: '', engine: '', complaint: '', codes: '', condition: '', safety: '' };

type Draft = MatchedVehicleDraft;

export function MatchedVehicleForm({ initial, embedded = false }: { initial?: Draft; embedded?: boolean }) {
  const [draft, setDraft] = useState<Draft>(initial ?? empty);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const attempt = useRef({ fingerprint: '', key: '' });
  const create = useMutation({
    mutationFn: async (body: object) => {
      const fingerprint = JSON.stringify(body);
      if (attempt.current.fingerprint !== fingerprint) attempt.current = { fingerprint, key: idempotencyKey('template-case') };
      return apiClient.request<CaseSnapshot>('/cases', { method: 'POST', body, idempotencyKey: attempt.current.key });
    },
    onSuccess: item => navigate(`/workbench/${item.id}`),
  });
  const field = (key: keyof Draft) => ({ value: draft[key], onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setDraft(current => ({ ...current, [key]: event.target.value })); setError(''); create.reset();
  } });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (create.isPending) return;
    if (['brand', 'model', 'year', 'complaint', 'codes'].some(key => !draft[key as keyof Draft].trim())) {
      setError('请填写品牌、车型、年份、故障码和主诉摘要。'); return;
    }
    const year = Number(draft.year);
    if (!Number.isInteger(year) || year < 1886 || year > 2100) { setError('请输入有效的四位年份。'); return; }
    const codes = [...new Set(draft.codes.toUpperCase().split(/[\s,，、;；]+/).filter(Boolean))];
    if (codes.some(code => !/^[PBCU][0-9A-F]{4}$/.test(code))) { setError('故障码格式应如 P0299 或 P0236。'); return; }
    create.mutate({ workbench_flow: 'template-match-v1',
      vehicle: { brand: draft.brand.trim(), model: draft.model.trim(), year, engine_code: draft.engine.trim().toUpperCase() || null },
      fault_description: draft.complaint.trim(), fault_codes: codes,
      topic_intake: { symptom_condition: draft.condition, safety_gate: draft.safety },
    });
  };
  return <form className="prototype-vehicle-basics formal-v2-profile-form" onSubmit={submit}>
      <div className="prototype-vehicle-basics-heading"><div><p className="prototype-eyebrow">VEHICLE & INTAKE PROFILE</p><h2>车辆基础信息与接诊事实</h2></div>{!embedded && <span>* 为必填 · 确认后保存</span>}</div>
      <fieldset disabled={create.isPending} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}><div className="formal-v2-reference-grid">
        <label>品牌 *<input {...field('brand')} required maxLength={100} placeholder="例如：大众" /></label>
        <label className="formal-v2-ref-model">车型 *<input {...field('model')} required maxLength={100} placeholder="例如：探岳" /></label>
        <label>年份 *<input {...field('year')} required type="number" min={1886} max={2100} placeholder="例如：2019" /></label>
        <label className="formal-v2-ref-engine">发动机代码<input {...field('engine')} maxLength={64} placeholder="选填，已知时填写" /></label>
        <label className="formal-v2-ref-complaint">主诉摘要 *<input {...field('complaint')} required maxLength={4000} placeholder="描述车辆出现的问题" /></label>
        <label className="formal-v2-ref-condition">症状发生工况<select {...field('condition')}><option value="">未提供</option><option value="mid_load">中负荷</option><option value="high_load">高负荷</option><option value="all_load">所有负荷</option><option value="intermittent">间歇出现</option></select></label>
        <label className="formal-v2-ref-codes">当前读取的故障码 *<input {...field('codes')} required maxLength={200} placeholder="例如：P0299 或 P0236" /></label>
        <label className="formal-v2-ref-safety">安全风险<select {...field('safety')}><option value="">未提供</option><option value="none">未发现/无</option><option value="caution">需要谨慎</option><option value="stop_now">立即停止检查</option><option value="unavailable">无法判断</option></select></label>
      </div></fieldset>
      <div className="prototype-intake-submit">{!embedded && <p>{'当前资料覆盖：大众探岳 2019 / DKVB。P0299 加载五区，P0236 加载三区；匹配后可在工作台请求 AI 排序。匹配不到时保留输入，不套用其他模板。'}</p>}<button className="prototype-button" type="submit" disabled={create.isPending}>{create.isPending ? '正在匹配并保存…' : '确认信息并加载排查区域'}</button></div>
      {error && <p className="formal-v2-profile-error" role="alert">{error}</p>}
      {create.error && <div className="formal-v2-profile-error"><ErrorState error={create.error} /><p>未完成匹配，输入已保留。核对后再次确认。</p></div>}
    </form>;
}

export function MatchedVehicleIntake() {
  return <div className="prototype-v2 formal-workbench-v2 formal-v2-new-case">
    <div className="prototype-warning"><span>◇</span><b>资料模板匹配</b><span>车辆信息与检查记录分开保存 · 不自动填写现场事实</span></div>
    <header className="prototype-case-header"><div><p className="prototype-eyebrow">XIUTU · FORMAL DIAGNOSTIC WORKBENCH V2</p><h1>车辆接诊与诊断工作台</h1><p>确认基础信息后，加载适用的排查区域、分组和问题。</p></div><div className="prototype-header-actions"><Link className="prototype-button subtle" to="/history">返回病例列表</Link></div></header>
    <main><MatchedVehicleForm /></main>
  </div>;
}
