import { useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Status = 'pass' | 'fail' | 'unmeasured';
type Device = {serial:string; run_code:string; design_revision:string; recipe_revision:string; printer:string;
  printed_at:string; substrate_code:string; material_lot:string; measured_at:string|null; value_nm:number|null;
  spec_max_nm:number|null; instrument:string|null; status:Status; position?:string; material?:string};
type Reading = {measured_at:string; value_nm:number; spec_max_nm:number; passed:boolean; instrument:string;
  external_id:string; sha256:string};
type Trace = {device:Device; history:Reading[]};
type Impact = {lot:string; totals:Record<Status,number>; devices:Device[]};
type Page = 'Trace device'|'Review material lot'|'Register fabrication';
const pages:Page[]=['Trace device','Review material lot','Register fabrication'];
const statuses:Status[]=['pass','fail','unmeasured'];

async function request<T>(path:string, body?:object):Promise<T> {
  const response=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);
  const data=await response.json();
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:
    Array.isArray(data.detail)?data.detail.map((x:{loc:string[];msg:string})=>x.loc.slice(1).join('.')+': '+x.msg).join('; '):'Request failed.');
  return data as T;
}
function StatusTag({value}:{value:Status}) {return <span className={'tag '+value}>{value}</span>;}
function Field({label,name, initial='', type='text'}:{label:string; name:string; initial?:string;type?:string}) {
  return <label>{label}<input name={name} type={type} defaultValue={initial} maxLength={64} required /></label>;
}
function Panel({title,children}:{title:string;children:ReactNode}) {return <section className="panel"><h2>{title}</h2>{children}</section>;}
function App(){
  const [page,setPage]=useState<Page>('Trace device');
  const [trace,setTrace]=useState<Trace>();
  const [impact,setImpact]=useState<Impact>();
  const [serial,setSerial]=useState('LENS-102');
  const [lot,setLot]=useState('LOT-R42');
  const [status,setStatus]=useState('');
  const [offset,setOffset]=useState(0);
  const [busy,setBusy]=useState(false);
  const [feedback,setFeedback]=useState<{error:boolean;text:string}>();

  async function action(fn:()=>Promise<void>) {
    setBusy(true);setFeedback(undefined);
    try {await fn();} catch(e) {setFeedback({error:true,text:e instanceof Error? e.message:'Request failed.'});}
    finally{setBusy(false);}
  }
  function change(page:Page) {setPage(page);setFeedback(undefined);}
  function traceDevice(id:string) {
    setSerial(id);setTrace(undefined);change('Trace device');
    return action(async()=>setTrace(await request<Trace>('/api/devices/'+encodeURIComponent(id.trim()))));
  }
  function lotReview(next:number) {
    setImpact(undefined);
    const query=new URLSearchParams({offset:String(next),limit:'25'});
    if(status) query.set('status',status);
    return action(async()=>{
      const result=await request<Impact>('/api/lots/'+encodeURIComponent(lot.trim())+'/impact?'+query);
      setOffset(next);setImpact(result);
    });
  }
  function register(e:FormEvent<HTMLFormElement>, kind:'substrates'|'runs') {
    e.preventDefault();
    const fields=Object.fromEntries(new FormData(e.currentTarget));
    return action(async()=>{
      if(kind==='runs'){
        const devices=String(fields.devices).trim().split(/\r?\n/).map(line=>{
          const parts=line.split(',').map(s=>s.trim());
          if(parts.length!==2||parts.some(s=>!s)) throw new Error('Use one serial,position pair per line.');
          return {serial:parts[0],position:parts[1]};
        });
        await request('/api/runs',{...fields,devices,printed_at:new Date(String(fields.printed_at)).toISOString()});
      }else await request('/api/substrates',fields);
      setFeedback({error:false,text:'Saved '+String(fields.code)+'.'});
    });
  }
  const d=trace?.device;
  return <><header className="mast"><div className="wrap head"><div className="brand">OL</div><div><p>FABRICATION DATA WORKSPACE</p><h1>Optics Run Ledger</h1></div><span className="demo">Synthetic lab data</span></div></header>
  <main className="wrap"><nav aria-label="Workspace">{pages.map(p=><button key={p} className={p===page?'selected':''} aria-current={p===page?'page':undefined} disabled={busy} onClick={()=>change(p)}>{p}</button>)}</nav>
  {feedback&&<p role={feedback.error?'alert':'status'} className={feedback.error?'notice error':'notice'}>{feedback.text}</p>}
  {page==='Trace device'&&<>
    <Panel title="Find a device"><p>Follow a serial number back to its print job, substrate and material lot.</p>
    <form className="row" onSubmit={e=>{e.preventDefault();void traceDevice(serial);}}><label>Device serial<input required value={serial} maxLength={64} onChange={e=>setSerial(e.target.value)}/></label><button disabled={busy}>Trace device</button></form></Panel>
    {d&&<><Panel title={d.serial+' · fabrication record'}><StatusTag value={d.status} />
      <dl className="cards">{Object.entries({'Material lot':d.material_lot,'Substrate':d.substrate_code,'Print run':d.run_code,'Printer':d.printer,'Design revision':d.design_revision,'Recipe revision':d.recipe_revision,'Position':d.position,'Material':d.material}).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      <button className="secondary" disabled={busy} onClick={()=>{setLot(d.material_lot);setImpact(undefined);change('Review material lot');}}>Review this material lot</button>
    </Panel>
    <Panel title="Measurement history">{trace.history.length===0?<p>No measurement has been recorded for this device.</p>:<div className="table"><table><thead><tr>{['Measured at','Result','Limit','Status','Instrument export','Evidence hash'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{trace.history.map((r,i)=><tr key={i}><td>{new Date(r.measured_at).toLocaleString()}</td><td>{r.value_nm} nm</td><td>{r.spec_max_nm} nm</td><td><StatusTag value={r.passed?'pass':'fail'}/></td><td>{r.instrument} / {r.external_id}</td><td><code title={r.sha256}>{r.sha256.slice(0,12)}</code></td></tr>)}</tbody></table></div>}</Panel></>}
  </>}
  {page==='Review material lot'&&<>
    <Panel title="Material lot impact"><p>Find the devices linked to a lot, including devices still waiting for metrology.</p>
      <form className="row" onSubmit={e=>{e.preventDefault();void lotReview(0);}}><label>Material lot<input required value={lot} onChange={e=>setLot(e.target.value)} maxLength={64}/></label><label>Quality status<select value={status} onChange={e=>setStatus(e.target.value)}><option value="">All</option>{statuses.map(s=><option key={s}>{s}</option>)}</select></label><button disabled={busy}>Review lot</button></form></Panel>
    {impact&&<Panel title={impact.lot+' · device impact'}><dl className="cards">{statuses.map(s=><div key={s}><dt>{s}</dt><dd>{impact.totals[s]}</dd></div>)}</dl>
      <div className="table"><table><thead><tr>{['Serial','Print run','Substrate','Status','Latest value'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{impact.devices.map(d=><tr key={d.serial}><td><button className="link" disabled={busy} onClick={()=>void traceDevice(d.serial)}>{d.serial}</button></td><td>{d.run_code}</td><td>{d.substrate_code}</td><td><StatusTag value={d.status}/></td><td>{d.value_nm==null?'—':d.value_nm+' nm'}</td></tr>)}</tbody></table></div>
      {impact.devices.length===0&&<p>No devices matched this filter.</p>}
      <div className="pager"><button className="secondary" disabled={busy||offset===0} onClick={()=>void lotReview(offset-25)}>Previous</button><button className="secondary" disabled={busy||impact.devices.length<25} onClick={()=>void lotReview(offset+25)}>Next</button></div></Panel>}
  </>}
  {page==='Register fabrication'&&<div className="split"><Panel title="Register a substrate"><form onSubmit={e=>void register(e,'substrates')} className="stack">
      <Field label="Substrate code" name="code"/><Field label="Material lot" name="material_lot"/><Field label="Material" name="material"/><button disabled={busy}>Save substrate</button>
    </form></Panel><Panel title="Register a print run"><form onSubmit={e=>void register(e,'runs')} className="stack">
      <div className="split"><Field label="Run ID" name="code"/><Field label="Substrate code" name="substrate_code"/><Field label="Design revision" name="design_revision"/><Field label="Recipe revision" name="recipe_revision"/><Field label="Printer" name="printer"/><Field label="Print time (local)" name="printed_at" type="datetime-local"/></div>
      <label>Devices (serial, position)<textarea name="devices" required rows={3} placeholder="LENS-201, X1" /></label><button disabled={busy}>Save run and devices</button>
    </form></Panel></div>}
  </main></>;
}

createRoot(document.getElementById('root')!).render(<App/>);
