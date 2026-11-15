import type {ClimateSummary,Crop,DataSourceCatalog,FarmProfile,SoilProfile} from './types';
import {buildFarmEvidence} from './farm-evidence.mjs';

export function DataProvenance({
  farm,crops,climate,climateLoading,soil,dataSources,sourceError,locationDetailsVisible,
}: {
  farm:FarmProfile;
  crops:Crop[];
  climate:ClimateSummary|null;
  climateLoading:boolean;
  soil:SoilProfile|null;
  dataSources:DataSourceCatalog|null;
  sourceError:string;
  locationDetailsVisible:boolean;
}) {
  const evidence=buildFarmEvidence(farm,crops,locationDetailsVisible);
  const cropReferences=crops.filter(crop=>['rice','soybean','mung_bean'].includes(crop.crop_id));
  const range=(value:{optimal?:Record<string,number|null>;absolute?:Record<string,number|null>}|undefined,keys:string[],unit='')=>{
    if(!value)return 'Not available';
    const fmt=(bounds:Record<string,number|null>|undefined)=>bounds?keys.map(key=>bounds[key]===null||bounds[key]===undefined?'–':bounds[key]).join('–'):'Not available';
    return `Preferred ${fmt(value.optimal)}${unit}; absolute ${fmt(value.absolute)}${unit}`;
  };

  return <section className="evidence" id="data-provenance">
    <div className="eyebrow dark">04 / DATA PROVENANCE</div>
    <h2>Transparent data boundaries.</h2>
    <p>Historical and gridded datasets provide context. They do not replace measurements from the farm, and NASA POWER does not provide a future weather forecast.</p>

    <div className="evidence-line" aria-label="Dataset availability">
      <span>{climateLoading?'NASA POWER loading…':typeof climate?.source==='string'?climate.source:'NASA POWER unavailable'}</span>
      <span>Period: {climateLoading?'loading…':climate?.period?`${climate.period.start}–${climate.period.end}`:'unknown'}</span>
      <span>Soil profile: {String(soil?.status||'unavailable')}</span>
      <span>Forecast: no</span>
    </div>
    {typeof climate?.source_url==='string'&&<p className="live-source">Retrieved dataset: <a href={climate.source_url} target="_blank" rel="noreferrer">NASA POWER request and coverage</a></p>}

    <h3>Farm Profile fields</h3>
    <p>Values marked as local measurements or farmer confirmation must come from this farm. Missing values remain unknown.</p>
    <div className="field-evidence-grid">
      {evidence.map(row=><article className="field-evidence" key={row.field}>
        <div className="field-evidence-heading"><strong>{row.label}</strong><span className={`evidence-state evidence-${row.state}`}>{row.state==='provided'?'Provided':row.state==='sourced'?'Catalog':row.state==='optional'?'Optional':'Needed'}</span></div>
        <p className="field-evidence-value">{row.value}</p>
        <small>{row.origin}</small>
        {row.note&&<small>{row.note}</small>}
      </article>)}
    </div>

    <h3>Crop reference data</h3>
    <p>Values below come from the cited crop records. Annual rainfall is shown as background context; it is not compared with the user-entered season total.</p>
    <div className="crop-reference-grid">
      {cropReferences.map(crop=>{
        const coefficient=crop.fa056_crop_coefficient;
        return <article className="crop-reference-card" key={crop.crop_id}>
          <h4>{crop.crop_name}</h4>
          <p><b>Temperature:</b> {range(crop.temperature,['min_c','max_c'],' °C')}</p>
          <p><b>Annual rainfall reference:</b> {range(crop.rainfall,['min_mm_year','max_mm_year'],' mm/year')} · context only</p>
          {crop.rainfall_response&&<p><b>Rainfall response:</b> {crop.rainfall_response.summary} <a href={crop.rainfall_response.source_url} target="_blank" rel="noreferrer">Source</a> · qualitative only</p>}
          <p><b>Soil pH:</b> {range(crop.soil_ph,['min','max'])}</p>
          <p><b>Growth duration:</b> {crop.growth_duration?.min_days??'Not available'}–{crop.growth_duration?.max_days??'Not available'} days</p>
          <p><b>Seasonal water reference:</b> {crop.water_requirement?.min_mm_season===null||crop.water_requirement?.min_mm_season===undefined?'Not verified':`${crop.water_requirement.min_mm_season}–${crop.water_requirement.max_mm_season} mm/season`} · {crop.water_requirement?.drought_sensitivity||'sensitivity unknown'}</p>
          {crop.water_requirement?.special_note&&<p>{crop.water_requirement.special_note}</p>}
          {coefficient&&<><p><b>Crop coefficients (Kc):</b> {coefficient.stages?.map(stage=>`${stage.name} ${stage.kc} (${stage.days} days)`).join('; ')||'Not available'}</p><p><b>Evidence:</b> {coefficient.evidence_grade||'not specified'}{coefficient.decision_eligible===false?' · indicative only; excluded from PASS/FAIL':''}</p>{coefficient.seasonal_consumptive_water_mm!==undefined&&<p><b>External trial water use:</b> {coefficient.seasonal_consumptive_water_mm} mm over {coefficient.total_days} days · {coefficient.cultivar}, {coefficient.region}, {coefficient.study_period}</p>}{coefficient.limitation&&<p>{coefficient.limitation}</p>}{coefficient.source_url&&<p><a href={coefficient.source_url} target="_blank" rel="noreferrer">Coefficient and trial source</a></p>}</>}
          <p><b>Crop record sources:</b> {[crop.temperature?.source_url,crop.rainfall?.source_url,crop.soil_ph?.source_url,crop.growth_duration?.source_url,crop.water_requirement?.source_url,crop.legume?.source_url].filter((value,index,array):value is string=>Boolean(value)&&array.indexOf(value)===index).map((url,index)=><span key={url}>{index>0?' · ':''}<a href={url} target="_blank" rel="noreferrer">{new URL(url).hostname}</a></span>)}</p>
        </article>;
      })}
    </div>

    <h3>Data sources and citations</h3>
    {sourceError&&<p className="warning" role="status">Source catalog unavailable: {sourceError}</p>}
    {!dataSources&&!sourceError&&<p>Loading source catalog…</p>}
    {dataSources&&<div className="source-catalog">
      {dataSources.sources.map(source=><article className="source-card" key={source.id}>
        <h4><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a></h4>
        <p>{source.publisher}{source.review_status?` · Review status: ${source.review_status.replace(/_/g,' ')}`:''}</p>
        <p><b>Used for:</b> {source.fields.join('; ')}</p>
        <p><b>Time coverage:</b> {source.temporal_coverage}</p>
        <p><b>Geographic scope:</b> {source.spatial_scope}</p>
        <ul>{source.limitations.map(limit=><li key={limit}>{limit}</li>)}</ul>
      </article>)}
    </div>}
    <p className="evidence-boundary">SoilGrids and regional salinity maps are context only. They do not establish soil EC or irrigation-water EC for this field.</p>
  </section>;
}
