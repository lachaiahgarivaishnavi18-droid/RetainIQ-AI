import { ReactNode } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { Inbox, ArrowUpRight } from 'lucide-react'
import { pct } from '../services/api'
export type Row = Record<string, any>
export function Panel({title, caption, children, action}: {title:string;caption?:string;children:ReactNode;action?:ReactNode}) {return <section className="panel"><div className="panel-heading"><div><h2>{title}</h2>{caption&&<p>{caption}</p>}</div>{action}</div>{children}</section>}
export function Empty({text='No records yet. Import a dataset to get started.'}:{text?:string}) {return <div className="empty"><Inbox size={28}/><p>{text}</p></div>}
export function Badge({value}:{value:string}) {return <span className={`badge ${value.toLowerCase().replaceAll(' ','-')}`}>{value}</span>}
export function Json({value}:{value:unknown}) {return <pre className="json">{JSON.stringify(value,null,2)}</pre>}
export function Table({rows, columns, onSelect}:{rows:Row[];columns:{key:string;label:string;render?:(r:Row)=>ReactNode}[];onSelect?:(r:Row)=>void}) {
 if(!rows.length)return <Empty/>
 return <div className="table-scroll"><table><thead><tr>{columns.map(c=><th key={c.key}>{c.label}</th>)}{onSelect&&<th><span className="sr-only">Open</span></th>}</tr></thead><tbody>{rows.map((r,i)=><tr key={String(r.id??r.customer_id??i)}>{columns.map(c=><td key={c.key}>{c.render?c.render(r):String(r[c.key]??'—')}</td>)}{onSelect&&<td><button className="icon-button" aria-label={`Open ${r.customer_id??r.id}`} onClick={()=>onSelect(r)}><ArrowUpRight size={16}/></button></td>}</tr>)}</tbody></table></div>
}
export function Bars({data,x='feature',y='importance',signed=false}:{data:Row[];x?:string;y?:string;signed?:boolean}) {return data.length?<div className="chart"><ResponsiveContainer width="100%" height={300}><BarChart data={data.slice(0,10)} layout="vertical" margin={{left:10,right:30}}><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tick={{fontSize:11}}/><YAxis dataKey={x} type="category" width={160} tick={{fontSize:11}}/><Tooltip contentStyle={{color:'#18352f',background:'#fff',borderRadius:10}}/><Bar dataKey={y} radius={[0,4,4,0]}>{data.slice(0,10).map((r,i)=><Cell key={i} fill={signed&&r[y]<0?'#66a993':'#265e50'}/>)}</Bar></BarChart></ResponsiveContainer></div>:<Empty text="Run the relevant analysis to populate this chart."/>}
export const customerColumns = [
 {key:'customer_id',label:'Customer'}, {key:'region',label:'Region'}, {key:'total_orders',label:'Orders'},
 {key:'probability',label:'Churn probability',render:(r:Row)=><div className="probability"><span>{pct(r.probability)}</span><i style={{width:`${(r.probability??0)*70}px`}}/></div>},
 {key:'risk',label:'Risk',render:(r:Row)=><Badge value={r.risk??'Unscored'}/>}, {key:'source',label:'Data source'}
]
