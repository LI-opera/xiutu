import { describe, expect, it } from 'vitest';
import { documentInput, emptyMaterialDraft, emptyVehicleDraft, toCreateCase, validateVehicle } from '../src/formal/state';

describe('formal input state', () => {
  it('keeps engine family and code separate and omits unknown case fields', () => {
    const body = toCreateCase({ ...emptyVehicleDraft(), model: '探岳', engineFamily: 'EA888', engineCode: 'DKVB', faultDescription: '增压不足', faultCodes: 'p0299 P0299' });
    expect(body.vehicle.engine_family).toBe('EA888');
    expect(body.vehicle.engine_code).toBe('DKVB');
    expect(body.vehicle.year).toBeUndefined();
    expect(body.fault_codes).toEqual(['P0299']);
  });

  it('enforces year, VIN and fault code boundaries before sending', () => {
    const errors = validateVehicle({ ...emptyVehicleDraft(), model: 'X', faultDescription: 'Y', year: '2101', vin: 'IOQ', faultCodes: 'P0299 ?' });
    expect(errors).toMatchObject({ year: expect.any(String), vin: expect.any(String), faultCodes: expect.any(String) });
  });

  it('does not invent unknown source, license or applicability metadata', () => {
    const body = documentInput({ ...emptyMaterialDraft(), nature: 'nonfiction', title: '待核实资料', sourceReference: '' });
    expect(body).toMatchObject({ synthetic: false, source_status: 'unknown', license_status: 'unknown', source_reference: 'unknown' });
    expect(body.scope).toEqual({ model: null, year_from: null, year_to: null, engine_family: null, engine_code: null });
  });
});
