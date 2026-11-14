import {ArrowUpRight} from 'lucide-react';
import {FarmGlobe} from './FarmGlobe';

const variables = [
  ['T2M / T2M_MAX', 'Mean and maximum air temperature', 'Mean temperature over the crop’s growing window is checked against documented crop thresholds. Maximum temperature is available as context.'],
  ['PRECTOTCORR', 'Corrected precipitation', 'Daily precipitation is summed across the growing window. It describes rainfall exposure.'],
  ['RH2M / ALLSKY_SFC_SW_DWN / WS2M', 'Humidity, solar radiation and wind', 'Included in the historical dataset as climate context. The rotation engine currently scores none of these three variables.'],
];

export function Landing() {
  return <section className="project-landing" aria-labelledby="landing-title">
    <div className="landing-split">
      <header className="hero">
        <div className="eyebrow">NASA SPACE APPS · FIELD SHIFT</div>
        <h1 id="landing-title">Shift with the <em>climate.</em></h1>
        <p>Explore crop rotations for a pilot farm in Long Xuyên, An Giang, using historical climate and local growing conditions.</p>
        <a className="mission-cta" href="#farm-profile-title">Open Farm Profile <ArrowUpRight size={17}/></a>
      </header>
      <FarmGlobe priority="yield" crop=""/>
    </div>
    <div className="landing-overview">
      <section><h2>Context</h2><p>Farmers weighing a crop change need to know whether the next crop fits the planting window, available water and soil conditions. Missing measurements make that choice harder.</p></section>
      <section><h2>Objective</h2><p>Compare current practice, water saving and soil recovery using the same farm profile. See which options the evidence supports and what still needs checking before planting.</p></section>
    </div>
    <section className="landing-band">
      <h2>How the assessment works</h2>
      <p>The backend checks rotation compatibility and planting windows using documented crop rules. It matches the planting date and crop duration to the NASA POWER daily record and checks the reported soil pH against crop thresholds. Water suitability and scores remain unknown when the required evidence is missing.</p>
    </section>
    <section className="landing-band">
      <h2>NASA data used</h2>
      <p>NASA POWER Daily Point provides historical records for Long Xuyên (10.383333° N, 105.450000° E), 2020–2025. Soil pH and salinity measurements come from local inputs. Future weather and field-level water availability require separate evidence.</p>
      <dl className="landing-datasets">{variables.map(([code,name,description])=><div key={code}><dt><strong>{name}</strong><code>{code}</code></dt><dd>{description}</dd></div>)}</dl>
      <a href="https://power.larc.nasa.gov/docs/services/api/temporal/daily/" target="_blank" rel="noreferrer">NASA POWER Daily API <ArrowUpRight size={14}/></a>
    </section>
    <section className="landing-band">
      <h2>Quick guide</h2>
      <ol><li>Open Farm Profile and enter your crop, area, planting date and priority.</li><li>Add measured soil and irrigation values if available. Leave unknown values blank.</li><li>Choose <strong>Compare three strategies</strong>. Read each result’s rationale, rejected options and evidence gaps. <strong>UNKNOWN</strong> means the assessment needs more evidence.</li></ol>
      <a className="mission-cta" href="#farm-profile-title">Start the comparison <ArrowUpRight size={17}/></a>
    </section>
  </section>;
}
