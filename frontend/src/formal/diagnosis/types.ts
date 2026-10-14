import type { components } from '../../generated/api-schema';

export type DiagnosisView = components['schemas']['DiagnosisView'];
export type DiagnosisAreaList = components['schemas']['DiagnosisAreaList'];
export type DiagnosisArea = components['schemas']['DiagnosisAreaView'];
export type AreaActivationResult = components['schemas']['AreaActivationResult'];
export type ObservationList = components['schemas']['ObservationList'];
export type ObservationView = components['schemas']['ObservationView'];
export type SubmitObservation = components['schemas']['SubmitObservation'];
export type CorrectObservation = components['schemas']['CorrectObservation'];
export type EnqueuedAction = components['schemas']['EnqueuedAction'];
export type RunSnapshot = components['schemas']['RunSnapshot'];
export type ReportList = components['schemas']['ReportList'];
export type ReportView = components['schemas']['ReportView'];
export type FinalReportGate = components['schemas']['FinalReportGate'];
export type EvidenceView = components['schemas']['EvidenceView'];

export type WorkbenchAction = { check_id: string; title: string; status: 'locked' | 'not_started' | 'current' | 'completed' | 'needs_review' | 'not_applicable'; available: boolean };
export type WorkbenchComponent = { component_id: string; title: string; status: WorkbenchAction['status']; actions: WorkbenchAction[] };
export type WorkbenchArea = { area_id: string; title: string; priority: number; priority_reason: string; status: 'locked' | 'available' | 'current' | 'waiting' | 'abnormal' | 'completed' | 'handed_off'; completed_checks: number; required_checks: number; has_abnormality: boolean; available: boolean; locked_reason?: string | null; components: WorkbenchComponent[] };
export type WorkbenchView = {
  case_summary: { id: string; title: string; mode: string; status_label: string; vehicle: Record<string, unknown>; fault_description: string; fault_codes: string[]; symptom_context: Record<string, unknown>; synthetic: boolean; formal_usable: boolean };
  areas: WorkbenchArea[]; selected_area_id: string; current_component?: WorkbenchComponent | null;
  current_action?: { step_id: string; check_id: string; candidate: Record<string, unknown>; protocol: Record<string, unknown> } | null;
  saved_facts: Array<{ id: string; kind: string; check_id?: string | null; summary: string; created_revision: number }>;
  synthesis: { status: 'in_progress' | 'handoff' | 'demo_complete'; confirmed_facts: string[]; handled_issues: string[]; remaining_abnormalities: string[]; unchecked_items: string[]; next_recommendations: string[]; can_generate_demo_summary: boolean };
};

export type Reference = { evidence_id: string; document_version_id: string };
export type Claim = { text?: string; references?: Reference[] };
export type StepMeasurement = {
  spec_id: string;
  quantity?: string;
  unit: components['schemas']['MeasuredValue']['unit'];
  conditions: Record<string, string>;
};
export type StepInput = {
  kind: 'choice' | 'measurement' | 'composite';
  choices?: Claim[];
  measurements?: StepMeasurement[];
};

export type ProtocolField = { name: string; label: string; kind: 'text' | 'select' | 'decimal'; required: boolean; options: string[] };
export type ProtocolOption = { option_id: string; label: string; fields: ProtocolField[] };
export type DemoMeasurementPreset = { id: string; label: string; explanation: string; synthetic: true; option_id?: string | null; fields: Record<string, string> };
export type ProtocolPresentation = {
  task_summary: string; why_summary: string; operation_steps: string[]; completion_explanation: string;
  evidence_summary: string; evidence_scope: string; evidence_limitations: string;
  progress_completed: string[]; progress_current: string; progress_remaining: string[];
  demo_measurement_presets: DemoMeasurementPreset[];
  task_title?: string | null; question?: string | null; record_summary?: string | null;
  outcome_preview?: string | null; evidence_kind?: string | null; progress_phase?: string | null;
};
export type ProtocolDecision = { decision: 'next_check' | 'need_input'; protocol_id: string; protocol_version: string; transition_id: string; current_check_id?: string | null; observation_id?: string | null; next_check_id: string; reason_code: string; handoff_reason?: string | null; options: ProtocolOption[]; presentation?: ProtocolPresentation };

export type StepCandidate = {
  type: 'propose_step';
  component_key: string;
  title: string;
  purpose: Claim;
  location?: Claim | null;
  prerequisites?: Claim[];
  actions?: Array<Claim & { operation?: string }>;
  input: StepInput;
  interpretation?: Claim[];
};

export function asStepCandidate(value: Record<string, unknown>): StepCandidate | null {
  if (value.type !== 'propose_step' || typeof value.title !== 'string' ||
      typeof value.component_key !== 'string' || typeof value.input !== 'object' ||
      value.input === null) return null;
  return value as unknown as StepCandidate;
}

export function referencesOf(step: StepCandidate): Reference[] {
  const claims: Array<Claim | null | undefined> = [
    step.purpose, step.location, ...(step.prerequisites ?? []),
    ...(step.actions ?? []), ...(step.input.choices ?? []),
    ...(step.interpretation ?? []),
  ];
  const seen = new Set<string>();
  return claims.flatMap(claim => claim?.references ?? []).filter(ref => {
    const key = `${ref.evidence_id}:${ref.document_version_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
