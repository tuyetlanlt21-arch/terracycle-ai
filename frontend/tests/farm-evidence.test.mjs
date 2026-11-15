import assert from 'node:assert/strict';
import test from 'node:test';
import { buildFarmEvidence } from '../src/farm-evidence.mjs';

const farm = {
  current_crop: 'rice', farm_area_ha: 1, planting_date: '2025-12-24', planning_month: null,
  farmer_priority: 'yield', soil_ph: null, soil_salinity_ec: 1, irrigation_water_ec: null,
  irrigation_available: false, freshwater_availability: 'unknown', drainage_available: null,
  water_control_available: true, inoculation_confirmed: null, latitude: 10.383333, longitude: 105.45,
};

test('farm evidence lists every API profile field and distinguishes missing from false', () => {
  const rows = buildFarmEvidence(farm, [{crop_id:'rice', crop_name:'Rice'}], false);
  assert.deepEqual(rows.map(row => row.field), [
    'current_crop', 'farm_area_ha', 'planting_date', 'planning_month', 'farmer_priority',
    'soil_ph', 'soil_salinity_ec', 'irrigation_water_ec', 'irrigation_available',
    'freshwater_availability', 'drainage_available', 'water_control_available',
    'inoculation_confirmed', 'latitude', 'longitude',
  ]);
  assert.equal(rows.find(row => row.field === 'soil_ph').state, 'missing');
  assert.equal(rows.find(row => row.field === 'irrigation_available').value, 'No');
  assert.equal(rows.find(row => row.field === 'planning_month').state, 'optional');
  assert.match(rows.find(row => row.field === 'latitude').value, /hidden/i);
});

test('selected location coordinates are shown only after the location control is opened', () => {
  const rows = buildFarmEvidence(farm, [{crop_id:'rice', crop_name:'Rice'}], true);
  assert.equal(rows.find(row => row.field === 'latitude').value, '10.383333°');
  assert.equal(rows.find(row => row.field === 'longitude').value, '105.450000°');
});
