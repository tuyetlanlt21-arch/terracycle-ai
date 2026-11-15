import {useEffect, useRef, useState} from 'react';
import type {FarmProfile,Provenance} from './types';
import {PILOT_LOCATION} from './pilot';

const palette: Record<FarmProfile['farmer_priority'], [number, number, number, number]> = {
  soil: [106, 240, 201, .15], water: [100, 221, 255, .21],
  income: [255, 192, 120, .18], yield: [118, 224, 247, .16], risk: [193, 169, 255, .12],
};

type GlobeLocation = {lat: number; lon: number; label: string};
const radians = Math.PI / 180;

type LandPoint = { lat: number; lon: number; brightness: number };
type Particle = { angle: number; radius: number; phase: number; size: number; color: number };

export function FarmGlobe({priority, crop, provenance, showLocationControls=true}: {priority: FarmProfile['farmer_priority']; crop: string; provenance?: Provenance; showLocationControls?: boolean}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const target = useRef(palette[priority]);
  const drag = useRef<{x: number; id: number} | null>(null);
  const yaw = useRef(0);
  const focus = useRef<GlobeLocation | null>(null);
  const [location, setLocation] = useState<GlobeLocation | null>(null);
  const [status, setStatus] = useState('');
  const [liveProvenance, setLiveProvenance] = useState<Provenance | undefined>(provenance);
  const [coordinateDraft, setCoordinateDraft] = useState<{latitude?: number; longitude?: number}>({latitude:PILOT_LOCATION.latitude,longitude:PILOT_LOCATION.longitude});
  const locator = useRef<HTMLButtonElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const view = useRef({cx: 0, cy: 0, radius: 1, centerLat: 15 * radians, rotation: 107 * radians});

  useEffect(() => { const handler=(event:Event)=>setLiveProvenance((event as CustomEvent<Provenance>).detail); window.addEventListener('terracycle-provenance',handler); return()=>window.removeEventListener('terracycle-provenance',handler); }, []);
  useEffect(() => {
    if (!location) return;
    close.current?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previous; };
  }, [Boolean(location)]);

  function exitLocation() {
    focus.current = null;
    setLocation(null);
    setStatus('');
    requestAnimationFrame(() => locator.current?.focus());
  }

  function selectPilotLocation() {
    const {latitude,longitude,label}=PILOT_LOCATION;
    setCoordinateDraft({latitude,longitude});
    window.dispatchEvent(new CustomEvent('terracycle-location',{detail:{latitude,longitude}}));
    const point = {lat: latitude * radians, lon: longitude * radians, label};
    focus.current = point;
    setLocation(point);
    setStatus('');
  }

  useEffect(() => {
    const [r,g,b,speed] = palette[priority];
    const variation = [...crop].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 7;
    target.current = [r,g,b,speed + variation*.012];
  }, [priority, crop]);

  useEffect(() => {
    const node = canvas.current;
    const ctx = node?.getContext('2d');
    if (!node || !ctx) return;

    const tags = node.parentElement?.querySelectorAll<HTMLElement>('.telemetry');
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const land: LandPoint[] = [];
    const particles: Particle[] = Array.from({length: 145}, (_, i) => ({
      angle: i * 2.399963, radius: 1.08 + (i * 73 % 100) / 240,
      phase: (i * 17 % 60) / 19, size: i % 13 === 0 ? 2 : i % 4 === 0 ? 1.35 : .8,
      color: i % 3,
    }));
    const image = new Image();
    let disposed = false;
    image.onload = () => {
      if (disposed) return;
      const mask = document.createElement('canvas');
      mask.width = image.naturalWidth; mask.height = image.naturalHeight;
      const maskContext = mask.getContext('2d', {willReadFrequently: true});
      if (!maskContext) return;
      maskContext.drawImage(image, 0, 0);
      const pixels = maskContext.getImageData(0, 0, mask.width, mask.height).data;
      // Evenly distributed sphere points sample an equirectangular land mask.
      for (let i=0; i<17500; i++) {
        const sinLat = 1 - (i + .5) * 2 / 17500;
        const lat = Math.asin(sinLat);
        const lon = ((i * 2.399963229728653) % (Math.PI * 2)) - Math.PI;
        const x = Math.min(mask.width-1, Math.max(0, Math.floor((lon / (2*Math.PI) + .5)*mask.width)));
        const y = Math.min(mask.height-1, Math.max(0, Math.floor((.5-lat/Math.PI)*mask.height)));
        const index = (y*mask.width+x)*4;
        if (pixels[index] > 128) land.push({lat,lon,brightness:.4+(i*83%100)/170});
      }
    };
    image.src = import.meta.env.BASE_URL + 'earth/land-mask.png';

    let frame = 0, previous = 0, angle = 107*Math.PI/180, elapsed = 0, width = 0, height = 0;
    let centerLat = 15 * radians, zoom = 1;
    const color = [...target.current];
    const resize = new ResizeObserver(() => {
      width = node.clientWidth; height = node.clientHeight;
      const ratio = Math.min(devicePixelRatio || 1, 2);
      node.width = Math.round(width * ratio); node.height = Math.round(height * ratio);
      ctx.setTransform(ratio,0,0,ratio,0,0);
    });
    resize.observe(node);
    const draw = (now: number) => {
      const dt = previous ? Math.min((now-previous)/1000,.05) : 0;
      previous = now;
      for (let i=0;i<4;i++) color[i] += (target.current[i]-color[i])*(1-Math.exp(-4*dt));
      if (!motion.matches) {
        elapsed += dt;
        if (!drag.current && !focus.current) angle += color[3]*dt;
      }
      const point = focus.current;
      const ease = motion.matches ? 1 : 1-Math.exp(-2.8*dt);
      if (point) {
        const delta = point.lon-angle-yaw.current;
        angle += Math.atan2(Math.sin(delta), Math.cos(delta))*ease;
      }
      centerLat += ((point?.lat ?? 15*radians)-centerLat)*ease;
      zoom += ((point ? 1.95 : 1)-zoom)*ease;
      const rotation = angle + yaw.current;
      const rgb = color.slice(0,3).map(Math.round).join(',');
      const tint = (alpha:number) => `rgba(${rgb},${alpha})`;
      const cx=width/2, cy=height/2, r=Math.min(width*.34,height*.33)*zoom;
      view.current={cx,cy,radius:r,centerLat,rotation:angle+yaw.current};
      ctx.clearRect(0,0,width,height);
      if (r > 0) {
        const glow=ctx.createRadialGradient(cx,cy,r*.72,cx,cy,r*1.65);
        glow.addColorStop(0,tint(.02));glow.addColorStop(.48,tint(.12));glow.addColorStop(1,tint(0));
        ctx.fillStyle=glow;ctx.fillRect(0,0,width,height);
        const sphere=ctx.createRadialGradient(cx-r*.34,cy-r*.44,r*.05,cx,cy,r*1.2);
        sphere.addColorStop(0,'#172440');sphere.addColorStop(.65,'#0b1533');sphere.addColorStop(1,'#050817');
        ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fillStyle=sphere;ctx.fill();
        // Orthographic projection centered on the tropics.
        const cosCenter=Math.cos(centerLat), sinCenter=Math.sin(centerLat);
        const project=(lat:number,lon:number) => {
          const delta=lon-rotation, cosLat=Math.cos(lat), sinLat=Math.sin(lat);
          const depth=sinCenter*sinLat+cosCenter*cosLat*Math.cos(delta);
          return {x:cx+r*cosLat*Math.sin(delta), y:cy-r*(cosCenter*sinLat-sinCenter*cosLat*Math.cos(delta)), depth};
        };
        ctx.save();ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.clip();
        for (const point of land) {
          const projected=project(point.lat,point.lon);
          if(projected.depth<=0) continue;
          const alpha=point.brightness*(.35+projected.depth*.5);
          ctx.fillStyle=`rgba(211,139,255,${alpha})`;
          const size=projected.depth>.45?1.6:1.1;
          ctx.fillRect(projected.x,projected.y,size,size);
        }
        // Luminous geographic marker, centered on Vietnam.
        const vietnam=project(point?.lat ?? 16.05*radians,point?.lon ?? 108.2*radians);
        if(vietnam.depth>.03){
          const alpha=Math.min(1,vietnam.depth*5);
          const halo=ctx.createRadialGradient(vietnam.x,vietnam.y,0,vietnam.x,vietnam.y,13);
          halo.addColorStop(0,`rgba(172,255,245,${alpha})`);
          halo.addColorStop(.2,`rgba(98,247,239,${alpha*.7})`);
          halo.addColorStop(1,'rgba(98,247,239,0)');
          ctx.fillStyle=halo;ctx.beginPath();ctx.arc(vietnam.x,vietnam.y,13,0,Math.PI*2);ctx.fill();
          ctx.fillStyle=`rgba(226,255,255,${alpha})`;ctx.beginPath();ctx.arc(vietnam.x,vietnam.y,2.3,0,Math.PI*2);ctx.fill();
          ctx.font='600 10px Segoe UI, sans-serif';ctx.fillText(point?.label || (point ? '◆' : 'VIETNAM'),vietnam.x+12,vietnam.y-10);
        }
        ctx.restore();
        const rim=ctx.createLinearGradient(cx-r,cy+r,cx+r,cy-r); rim.addColorStop(0,'#7745e5'); rim.addColorStop(.45,'#46a9fd'); rim.addColorStop(1,'#bbfaff'); ctx.save();ctx.shadowColor='#5cbfff';ctx.shadowBlur=26;ctx.strokeStyle=rim;ctx.lineWidth=2.5;
        ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.stroke();ctx.restore();
        for (let orbit=0;orbit<3;orbit++) {
          const tilt=[-.45,.4,-.9][orbit], distance=r*(1.17+orbit*.12), flatten=.32+orbit*.075;
          ctx.beginPath();ctx.ellipse(cx,cy,distance,distance*flatten,tilt,0,Math.PI*2);
          ctx.strokeStyle=orbit===1?'rgba(211,130,255,.45)':'rgba(118,223,255,.38)';ctx.lineWidth=1;ctx.setLineDash(orbit===2?[1,5]:[]);ctx.stroke();ctx.setLineDash([]);
          const phase=elapsed*(orbit===1?-.22:.2)+orbit*2.1;
          const dx=Math.cos(phase)*distance,dy=Math.sin(phase)*distance*flatten;
          const orbitX=cx+dx*Math.cos(tilt)-dy*Math.sin(tilt),orbitY=cy+dx*Math.sin(tilt)+dy*Math.cos(tilt);
          const tag=tags?.[orbit];
          if(tag){tag.style.left=Math.max(tag.offsetWidth/2,Math.min(width-tag.offsetWidth/2,orbitX))+'px';tag.style.top=Math.max(15,orbitY-18)+'px';}
          ctx.beginPath();ctx.arc(orbitX,orbitY,3,0,Math.PI*2);ctx.fillStyle=tint(.94);ctx.fill();
        }
        for (const p of particles) {
          const a=p.angle+elapsed*.08*(p.color===1?-1:1), orbitR=p.radius*r;
          const px=cx+Math.cos(a)*orbitR,py=cy+Math.sin(a)*orbitR*.76;
          if(Math.hypot(px-cx,py-cy)<r*1.03)continue;
          const flicker=.38+.35*(1+Math.sin(elapsed*1.4+p.phase))/2;
          ctx.fillStyle=p.color===0?`rgba(246,164,255,${flicker})`:p.color===1?tint(flicker):`rgba(213,190,255,${flicker})`;
          ctx.beginPath();
          if (p.size >= 2) {
            for (let side=0;side<6;side++) {
              const corner=a+side*Math.PI/3;
              const x=px+Math.cos(corner)*4, y=py+Math.sin(corner)*4;
              if(side===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
            }
            ctx.closePath();
            ctx.strokeStyle=ctx.fillStyle;
            ctx.stroke();
          } else {
            ctx.arc(px,py,p.size,0,Math.PI*2);
            ctx.fill();
          }
        }
      }
      frame=requestAnimationFrame(draw);
    };
    frame=requestAnimationFrame(draw);
    return () => {disposed=true;image.onload=null;cancelAnimationFrame(frame);resize.disconnect();};
  }, []);

  return <figure className={location ? 'farm-globe farm-globe-expanded' : 'farm-globe'}
    role={location ? 'dialog' : undefined} aria-modal={location ? true : undefined}
    onKeyDown={event => {
      if (location && event.key === 'Escape') exitLocation();
      if (location && event.key === 'Tab') { event.preventDefault(); close.current?.focus(); }
    }} aria-label={location ? "Long Xuyen pilot location on Earth" : "Interactive globe highlighting Vietnam"}>
    <canvas ref={canvas} tabIndex={location ? -1 : 0} aria-label="Rotate the globe with the arrow keys" onDoubleClick={event=>{if(!showLocationControls)return;const box=event.currentTarget.getBoundingClientRect();const camera=view.current;const x=(event.clientX-box.left-camera.cx)/camera.radius;const y=-(event.clientY-box.top-camera.cy)/camera.radius;const rho2=x*x+y*y;if(rho2>1)return;const z=Math.sqrt(Math.max(0,1-rho2));const sinC=Math.sin(camera.centerLat),cosC=Math.cos(camera.centerLat);const sinLat=cosC*y+sinC*z;const q=-sinC*y+cosC*z;const delta=Math.atan2(x,q);const latitude=Math.asin(Math.max(-1,Math.min(1,sinLat)))/radians;const longitude=((camera.rotation+delta)/radians+540)%360-180;window.dispatchEvent(new CustomEvent('terracycle-location',{detail:{latitude:Number(latitude.toFixed(6)),longitude:Number(longitude.toFixed(6))}}));}} onKeyDown={event=>{
      if(!location && (event.key==='ArrowLeft'||event.key==='ArrowRight')){event.preventDefault();yaw.current+=event.key==='ArrowLeft'?-.18:.18;}
    }} onPointerDown={event=>{if(location) return;drag.current={x:event.clientX,id:event.pointerId};event.currentTarget.setPointerCapture(event.pointerId);}}
    onPointerMove={event=>{if(drag.current?.id===event.pointerId){yaw.current+=(event.clientX-drag.current.x)*.012;drag.current.x=event.clientX;}}}
    onPointerCancel={()=>{drag.current=null;}}
    onLostPointerCapture={()=>{drag.current=null;}}/>
    {showLocationControls&&<div className="globe-location-controls">
      {location ? <button ref={close} type="button" onClick={exitLocation}>Close map ×</button> :
        <button ref={locator} type="button" onClick={selectPilotLocation}
          title="For this demo, selects the Long Xuyen pilot coordinates.">◎ Use your location</button>}
      {location && <strong>{location.label || `${(location.lat/radians).toFixed(3)}°, ${(location.lon/radians).toFixed(3)}°`}</strong>}
      <div role="status">{status}</div>
      {liveProvenance && <div className="globe-provenance"><b>Evaluated location</b><span>{liveProvenance.evaluated_location ? `${liveProvenance.evaluated_location.latitude}, ${liveProvenance.evaluated_location.longitude}` : 'not provided'}</span><span>NASA: {liveProvenance.availability?.climate || 'unknown'} · SoilGrids: {liveProvenance.availability?.soil || liveProvenance.soil_status || 'unknown'}</span><span>Period: {liveProvenance.climate_period || 'unknown'} · Rules: {liveProvenance.rule_set || 'unknown'}</span><span>Scope: {liveProvenance.supported_scope || 'unknown'}</span>{liveProvenance.applicability_reason && <span>{liveProvenance.applicability_reason}</span>}{(liveProvenance.warnings || []).map(warning => <span key={warning}>{warning}</span>)}</div>}
      {!location && <div className="globe-coordinates"><label>Latitude <input type="number" min="-90" max="90" step="0.000001" placeholder="Latitude" value={coordinateDraft.latitude??''} onChange={event=>{const latitude=event.target.value===''?undefined:Number(event.target.value);const next={...coordinateDraft,latitude};setCoordinateDraft(next);window.dispatchEvent(new CustomEvent('terracycle-location',{detail:next}))}}/></label><label>Longitude <input type="number" min="-180" max="180" step="0.000001" placeholder="Longitude" value={coordinateDraft.longitude??''} onChange={event=>{const longitude=event.target.value===''?undefined:Number(event.target.value);const next={...coordinateDraft,longitude};setCoordinateDraft(next);window.dispatchEvent(new CustomEvent('terracycle-location',{detail:next}))}}/></label></div>}
    </div>}
    <span className="telemetry telemetry-smap">SMAP Moisture</span>
    <span className="telemetry telemetry-eco">ECOSTRESS LST</span>
    <span className="telemetry telemetry-gpm">GPM Precipitation</span>
    <figcaption>Illustrative globe · Drag to rotate · Land map: <a href="https://www.naturalearthdata.com/" target="_blank" rel="noreferrer">Natural Earth</a></figcaption>
  </figure>;
}
