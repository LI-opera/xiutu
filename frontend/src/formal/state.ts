import type { CreateCase, DocumentInput } from './types';

export type VehicleDraft = {
  model: string; year: string; vin: string; engineFamily: string;
  engineCode: string; faultDescription: string; faultCodes: string;
};

export const emptyVehicleDraft = (): VehicleDraft => ({
  model: '', year: '', vin: '', engineFamily: '', engineCode: '',
  faultDescription: '', faultCodes: '',
});

export const supportedConservativeDraft = (faultDescription = '【待体验】R1 保守模式：DKVB 加速无力，P0299'):
VehicleDraft => ({
  model: '虚拟探岳 DKVB 演示台架', year: '2020', vin: '',
  engineFamily: 'EA888 Gen3B DEMO', engineCode: 'DKVB-DEMO',
  faultDescription, faultCodes: 'P0299',
});

const value = (text: string) => text.trim() || undefined;

export function toCreateCase(draft: VehicleDraft): CreateCase {
  const codes = draft.faultCodes.split(/[\s,，]+/).map(x => x.trim()).filter(Boolean);
  return {
    diagnosis_mode: 'conservative',
    policy_version: 'r1',
    vehicle: {
      model: draft.model.trim(),
      ...(draft.year ? { year: Number(draft.year) } : {}),
      ...(value(draft.vin) ? { vin: draft.vin.trim().toUpperCase() } : {}),
      ...(value(draft.engineFamily) ? { engine_family: draft.engineFamily.trim() } : {}),
      ...(value(draft.engineCode) ? { engine_code: draft.engineCode.trim() } : {}),
    },
    fault_description: draft.faultDescription.trim(),
    fault_codes: [...new Set(codes.map(x => x.toUpperCase()))].sort(),
  };
}

export function validateVehicle(draft: VehicleDraft): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!draft.model.trim()) errors.model = '车型为必填项。';
  if (!draft.faultDescription.trim()) errors.faultDescription = '请描述故障现象。';
  if (draft.year && (!Number.isInteger(Number(draft.year)) || Number(draft.year) < 1886 || Number(draft.year) > 2100)) errors.year = '年款须为 1886—2100 的整数。';
  if (draft.vin && !/^[A-HJ-NPR-Z0-9]{17}$/i.test(draft.vin)) errors.vin = 'VIN 须为 17 位且不能含 I/O/Q。';
  const codes = draft.faultCodes.split(/[\s,，]+/).filter(Boolean);
  if (codes.some(x => !/^[A-Za-z0-9-]{1,32}$/.test(x))) errors.faultCodes = '故障码只能包含字母、数字或连字符。';
  return errors;
}

export type MaterialDraft = {
  nature: '' | 'synthetic' | 'nonfiction'; title: string; sourceReference: string;
  model: string; yearFrom: string; yearTo: string; engineFamily: string; engineCode: string;
};

export const emptyMaterialDraft = (): MaterialDraft => ({
  nature: '', title: '', sourceReference: '', model: '', yearFrom: '', yearTo: '',
  engineFamily: '', engineCode: '',
});

export function documentInput(draft: MaterialDraft): DocumentInput {
  const scope = {
    model: value(draft.model) ?? null,
    year_from: draft.yearFrom ? Number(draft.yearFrom) : null,
    year_to: draft.yearTo ? Number(draft.yearTo) : null,
    engine_family: value(draft.engineFamily) ?? null,
    engine_code: value(draft.engineCode) ?? null,
  };
  return {
    document_id: null,
    title: draft.title.trim(),
    source_kind: draft.nature === 'synthetic' ? 'synthetic_upload' : 'local_upload',
    source_reference: draft.sourceReference.trim() || 'unknown',
    source_status: 'unknown',
    license_status: 'unknown',
    scope,
    synthetic: draft.nature === 'synthetic',
  };
}

export function displayBytes(size: number) {
  return size < 1024 * 1024 ? `${Math.ceil(size / 1024)} KiB` : `${(size / 1024 / 1024).toFixed(2)} MiB`;
}
