import type { AreaId } from './prototypeKnowledge';

export interface IntakeProfile {
 model:string; engineCode:string; complaint:string; symptomCondition:string;
 dtcCodes:string; safetyGate:string;
}

export const emptyIntakeProfile: IntakeProfile = {
 model:'',engineCode:'',complaint:'',symptomCondition:'',dtcCodes:'',safetyGate:''
};

export function parseDtcInput(value:string){
 const tokens=value.toUpperCase().split(/[\s,，、;；/]+/).filter(Boolean);
 return {
  codes:[...new Set(tokens.filter(token=>/^[PCBU][0-9A-F]{4}$/.test(token)))],
  invalid:tokens.filter(token=>!/^[PCBU][0-9A-F]{4}$/.test(token))
 };
}

export function intakeDtcSignals(p:IntakeProfile){
 const {codes}=parseDtcInput(p.dtcCodes),has=(code:string)=>codes.includes(code);
 const p0236=has('P0236'),p2261=has('P2261');
 const misfire=codes.some(code=>/^P030[0-9]$/.test(code)),fuel=has('P0087');
 const unclassified=codes.filter(code=>!['P0299','P0236','P2261','P0087'].includes(code)&&!/^P030[0-9]$/.test(code));
 return {
  codes,unclassified,
  p0299State:has('P0299')?'current':codes.length?'not_present':'unavailable',
  boostDtcs:p0236&&p2261?'both':p0236?'p0236_family':p2261?'p2261_family':!codes.length||unclassified.length?'unavailable':'none',
  crossDtcs:misfire&&fuel?'multiple':misfire?'misfire':fuel?'fuel':!codes.length||unclassified.length?'unavailable':'none'
 };
}

export function intakeApplicability(p:IntakeProfile):'supported'|'outside_scope'|'safety_stop'|'safety_unknown'{
 if(p.safetyGate==='stop_now')return 'safety_stop';
 if(p.safetyGate==='unavailable')return 'safety_unknown';
 if(!p.model.trim().includes('探岳')||p.engineCode.trim().toUpperCase()!=='DKVB')return 'outside_scope';
 return 'supported';
}

export function initialAreaForIntake(p:IntakeProfile):AreaId{
 const dtcs=intakeDtcSignals(p);
 if(['misfire','fuel','exhaust','multiple'].includes(dtcs.crossDtcs))return 'powertrain';
 if(dtcs.boostDtcs==='p2261_family')return 'actuator';
 if(['p0236_family','both'].includes(dtcs.boostDtcs)||p.symptomCondition==='intermittent')return 'pressure';
 return 'boost-air';
}
