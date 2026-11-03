type Choice = { answer_kind: string; exclusive_options?: string[] };

// Options that stand alone in a multi-choice answer ("normal", "cannot inspect"): the template
// names them; templates without the list keep the old ids.
const LEGACY_EXCLUSIVE = ['none', 'none_known'];

export function nextSelection(question: Choice, selected: string[], id: string): string[] {
  if (question.answer_kind !== 'multi_choice') return [id];
  if (selected.includes(id)) return selected.filter(item => item !== id);
  const exclusive = new Set(question.exclusive_options?.length ? question.exclusive_options : LEGACY_EXCLUSIVE);
  return exclusive.has(id) ? [id] : [...selected.filter(item => !exclusive.has(item)), id];
}
