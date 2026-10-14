// Types for retained historical topic responses; no prototype data or execution.
export type StageId='S0'|'S1'|'S2'|'S3'|'S4'|'S5'|'S6';
export type AreaId='boost-air'|'pressure'|'actuator'|'turbo'|'powertrain';
export type EntryState='ready'|'available_secondary'|'in_progress'|'completed'|'historical_completed'|'waiting_prerequisite'|'unavailable';
export type Outcome='normal'|'abnormal'|'unavailable'|'recovered';
export type SourceType='FACT_LOCAL_MANUAL'|'GENERAL_VAG_REFERENCE'|'EDITORIAL_DEMO'|'SAFETY_BOUNDARY';
export interface FieldDef{id:string;label:string;unit?:string;defaultValue:string;type:'number'|'text'}
export interface OptionDef{id:string;label:string;outcome:Outcome}
export interface QuestionBlock{id:string;stage:StageId;cardId:string;title:string;prompt:string;purpose:string;instructions:string;factKey:string;options:OptionDef[];fields:FieldDef[];assetIds:string[];sources:SourceType[]}
export interface TopicCard{id:string;stage:StageId;areaId?:AreaId;title:string;icon:string;location:string;why:string;safety:string;questionIds:string[];assetIds:string[]}
export interface AreaDef{id:AreaId;stage:StageId;title:string;icon:string;description:string;initialPriority:number;componentIds:string[]}
export interface AssetDef{id:string;title:string;file:string;source:SourceType;description:string}
export interface DemoSeed{questionId:string;optionId:string;fields?:Record<string,string>;historical?:boolean}
export interface ResultStateDef{id:string;label:string;minimumFacts:string;nextStep:string}
export interface TransitionDef{id:string;condition:string;target:string}

