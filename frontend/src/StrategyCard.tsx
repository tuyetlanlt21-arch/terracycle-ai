import type {CompareResponse,DataSource,Strategy} from './types';

const labels:Record<Strategy,string>={current_practice:'Current Practice',water_saving:'Water Saving',soil_recovery:'Soil Recovery'};
const format=(value:unknown,unit='mm')=>typeof value==='number'&&Number.isFinite(value)?`${value.toFixed(2)} ${unit}`:'Unavailable';

export function StrategyCard({strategy,response,dataSources=[]}:{strategy:Strategy;response:CompareResponse|undefined;dataSources?:DataSource[]}){
 if(!response)return <article className="decision"><h3>{labels[strategy]}</h3><p>Not assessed.</p></article>;
 return <article className="decision"><div className="field-num">{labels[strategy].toUpperCase()}</div>
  {response.recommendations.length===0&&response.rejected_alternatives.length===0?<p>No alternatives were returned.</p>:response.recommendations.map(item=>{
   const water=item.water_balance as Record<string,unknown>|null|undefined;
   const climate=item.climate_suitability; const farm=item.farm_suitability;
   return <div className="recommendation" key={item.crop_id}>
    <div className="status-row"><span className={`status status-${(item.final_decision||item.eligibility).toLowerCase()}`}>{item.final_decision||item.eligibility}</span>{item.score!==null&&<strong>{item.score.toFixed(0)}/100</strong>}</div>
    <h3>{item.sequence.join(' → ')}</h3>
    <p>{item.rationale.slice(0,2).join(' ')}</p>
    <p><b>Climate suitability:</b> {climate?.status||'Unavailable'}</p>
    <p><b>Farm suitability:</b> {farm?.status||'Unavailable'}</p>
    {item.final_decision===null&&<p className="warning"><b>Additional information required.</b></p>}
    {climate?.missing_evidence?.map(value=><p className="warning" key={`climate-${value}`}>Climate evidence: {value}</p>)}
    {farm?.missing_evidence?.map(value=><p className="warning" key={`farm-${value}`}>Farm evidence: {value}</p>)}
    {water&&<div className="water-evidence"><p><b>Rainfall:</b> growing period {format(water.growing_period_rainfall_mm)}; effective {format(water.effective_rainfall_mm)}</p><p><b>Water balance:</b> ET0 {format(water.et0_total_mm)}; ETc {format(water.etc_total_mm)}; irrigation deficit {format(water.irrigation_deficit_mm)}</p><p><b>Coverage:</b> {String((water.data_coverage as Record<string,unknown>|undefined)?.start||'Unavailable')}–{String((water.data_coverage as Record<string,unknown>|undefined)?.end||'Unavailable')}</p></div>}
    {item.warnings.map(warning=><p className="warning" key={warning}>{warning}</p>)}
    {item.sources.length>0&&<div className="recommendation-sources"><b>Evidence sources</b><ul>{item.sources.map(id=>{const source=dataSources.find(candidate=>candidate.id===id||candidate.url===id);return <li key={id}>{source?<a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>:/^https?:\/\//.test(id)?<a href={id} target="_blank" rel="noreferrer">{id}</a>:id}</li>})}</ul></div>}
   </div>;
  })}
  {response.missing_data_warnings.length>0&&<div className="warning"><b>Missing data</b><p>{response.missing_data_warnings.slice(0,3).join(' · ')}</p></div>}
  <p className="warning">{response.warnings.join(' ')}</p></article>;
}
