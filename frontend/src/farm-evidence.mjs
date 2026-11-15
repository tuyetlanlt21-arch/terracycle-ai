const labels = {
  current_crop: 'Current crop',
  farm_area_ha: 'Farm area',
  planting_date: 'Planting date',
  planning_month: 'Planning month',
  farmer_priority: 'Farmer priority',
  soil_ph: 'Soil pH',
  soil_salinity_ec: 'Soil salinity EC',
  irrigation_water_ec: 'Irrigation-water EC',
  irrigation_available: 'Irrigation available',
  freshwater_availability: 'Freshwater availability',
  drainage_available: 'Drainage available',
  water_control_available: 'Water control available',
  inoculation_confirmed: 'Legume inoculation confirmed',
  latitude: 'Latitude',
  longitude: 'Longitude',
};

const cropSource = new Set(['current_crop']);
const fieldMeasurements = new Set(['soil_ph', 'soil_salinity_ec', 'irrigation_water_ec']);
const optional = new Set(['planning_month', 'inoculation_confirmed']);

function display(value) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

export function buildFarmEvidence(farm, crops, locationDetailsVisible) {
  const cropNames = new Map(crops.map(crop => [crop.crop_id, crop.crop_name]));
  return Object.keys(labels).map(field => {
    let value = display(farm[field]);
    let state = value === null ? (optional.has(field) ? 'optional' : 'missing') : 'provided';
    let origin = 'Farmer-provided input';
    let note = '';

    if (cropSource.has(field)) {
      value = cropNames.get(farm.current_crop) || value || 'Not selected';
      state = farm.current_crop ? 'sourced' : 'missing';
      origin = 'Crop catalog';
      note = 'Crop reference values and their citations appear below.';
    } else if (fieldMeasurements.has(field)) {
      origin = 'Local field measurement';
      if (value !== null && field !== 'soil_ph') value = `${value} dS/m`;
      if (value === null) note = 'Enter a measured value; gridded soil data is not substituted.';
    } else if (field === 'farm_area_ha') {
      if (value !== null) value = `${value} ha`;
    } else if (field === 'latitude' || field === 'longitude') {
      origin = 'Selected farm location';
      state = value === null ? 'missing' : 'provided';
      if (!locationDetailsVisible) value = 'Coordinates hidden; open the location control to view or change.';
      else if (value !== null) value = `${Number(value).toFixed(6)}°`;
      note = 'NASA POWER point data are gridded climate context, not field measurements.';
    } else if (field === 'planning_month') {
      note = 'Optional planning context; the current comparison uses the exact planting date.';
    } else if (field === 'inoculation_confirmed' && value === null) {
      note = 'Needed only when assessing soybean; otherwise optional.';
    } else if (field === 'freshwater_availability' && farm.freshwater_availability === 'unknown') {
      value = 'Unknown';
      state = 'missing';
      origin = 'Farmer confirmation';
      note = 'Climate data cannot establish water access at this farm.';
    } else if (field.endsWith('_available') || field === 'water_control_available') {
      origin = 'Farmer confirmation';
    }

    return {field, label: labels[field], value: value || (state === 'optional' ? 'Not supplied (optional)' : 'Not provided'), state, origin, note};
  });
}
