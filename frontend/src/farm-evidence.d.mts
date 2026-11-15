import type {Crop, FarmProfile} from './types';

export type FarmEvidenceState = 'provided' | 'sourced' | 'missing' | 'optional';
export interface FarmEvidenceRow {
  field: string;
  label: string;
  value: string;
  state: FarmEvidenceState;
  origin: string;
  note: string;
}

export function buildFarmEvidence(
  farm: FarmProfile,
  crops: Crop[],
  locationDetailsVisible: boolean,
): FarmEvidenceRow[];
