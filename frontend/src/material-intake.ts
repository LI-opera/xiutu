import type { DocumentInput } from './api-schema';
export type Nature = '' | 'synthetic' | 'nonfiction';
export type IntakeFields = { source: string; model: string; yearFrom: string; yearTo: string; family: string; code: string };
export const emptyFields: IntakeFields = {source:'',model:'',yearFrom:'',yearTo:'',family:'',code:''};
export function byteSize(n: number): string { return `${n.toLocaleString('zh-CN')} 字节（${(n / 1048576).toFixed(2)} MiB）`; }
export function uploadProblem(size: number, max: number | undefined): string {
 if (!max) return '尚未取得服务端上传上限，请稍后重试。';
 return size > max ? `文件超过允许上限：实际 ${byteSize(size)}；允许 ${byteSize(max)}。请改用上限内文件，本入口不支持拆书或分片上传。` : '';
}
export function uploadFailure(status: number, max: number | undefined): string | null {
 return status === 413 ? `服务器拒绝上传：文件或请求超过允许范围。文件上限 ${max ? byteSize(max) : '尚未取得'}；原资料保持不变。` : null;
}
export function intakeMetadata(name: string, nature: Nature, fields: IntakeFields, syntheticScope: DocumentInput['scope']): DocumentInput {
 if (!nature) throw new Error('请明确选择资料性质。');
 const year = (s: string) => {if (!s.trim()) return null; if (!/^\d{4}$/.test(s) || +s < 1886 || +s > 2100) throw new Error('年款请填1886—2100，未知请留空。');return +s;};
 const scope = nature === 'synthetic' ? syntheticScope : { model:fields.model.trim() || null, year_from:year(fields.yearFrom), year_to:year(fields.yearTo), engine_family:fields.family.trim() || null, engine_code:fields.code.trim() || null };
 if (scope?.year_from && scope?.year_to && scope.year_from > scope.year_to) throw new Error('起始年款不能晚于结束年款。');
 return {title:name, source_kind:nature === 'synthetic' ? 'synthetic_preview' : 'unverified_material', source_reference:fields.source.trim() || '来源未知，待核实', source_status:'unknown',license_status:'unknown',scope,synthetic:nature === 'synthetic'};
}

// Every actual selection starts a new declaration, including same-name files.
export type UploadDraft = { file: File | null; nature: Nature; fields: IntakeFields };
export function selectUploadFile(file: File | null): UploadDraft {
 return {file, nature:'', fields:{...emptyFields}};
}
export function selectedUploadMetadata(file: File, draft: UploadDraft, scope: DocumentInput['scope']): DocumentInput {
 if (draft.file !== file) throw new Error('文件选择已变化，请重新声明资料性质。');
 return intakeMetadata(file.name, draft.nature, draft.fields, scope);
}
