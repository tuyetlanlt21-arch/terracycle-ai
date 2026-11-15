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
