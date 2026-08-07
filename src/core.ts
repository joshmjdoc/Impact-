import { parse } from 'parse5';
import { z } from 'zod';
import { createHash } from 'node:crypto';

export type ActionType='get_started'|'category'|'package';
export type ActionBinding={provider:'telehealthus';actionType:ActionType;clinicId:string;categoryId:string|null;packageId:string|null;destinationPath:string;canonicalDestinationUrl:string;sourceHash:string};
const MAX=100_000;
const allowedHosts=new Set(['telehealthus.com','www.telehealthus.com']);
function iframeSources(node: unknown,out:string[]=[]):string[]{
  if(node && typeof node==='object'){
    const n=node as {nodeName?:string;attrs?:{name:string;value:string}[];childNodes?:unknown[]};
    if(n.nodeName==='iframe'){const src=n.attrs?.find(a=>a.name.toLowerCase()==='src')?.value;if(src)out.push(src);}
    n.childNodes?.forEach(c=>iframeSources(c,out));
  } return out;
}
export function analyzeSnippet(input:string,canonicalOrigin=process.env.TELEHEALTHUS_CANONICAL_ORIGIN||'https://www.telehealthus.com'):ActionBinding{
  if(!input.trim()||input.length>MAX) throw new Error(input.length>MAX?'Input is too large':'Unsupported snippet format');
  const trimmed=input.trim(); let candidates:string[];
  if(/^https?:\/\//i.test(trimmed)) candidates=[trimmed]; else candidates=iframeSources(parse(trimmed));
  if(candidates.length!==1) throw new Error(candidates.length>1?'Ambiguous snippet: multiple iframes':'Unsupported snippet format');
  let url:URL; try{url=new URL(candidates[0]);}catch{throw new Error('Unsupported snippet format');}
  if(!['http:','https:'].includes(url.protocol)||!allowedHosts.has(url.hostname.toLowerCase())||url.username||url.password||url.port||url.search||url.hash||/%2f|%5c/i.test(url.pathname)) throw new Error('Unsupported or unsafe TelehealthUS URL');
  const routes:[RegExp,ActionType][]=[[/^\/get-started\/(\d+)$/,'get_started'],[/^\/packageByCategory\/(\d+)\/(\d+)$/,'category'],[/^\/get-started-by-package\/(\d+)\/(\d+)\/(\d+)$/,'package']];
  const match=routes.map(([re,type])=>({m:url.pathname.match(re),type})).find(x=>x.m);
  if(!match?.m||match.m.slice(1).some(v=>Number(v)<=0)) throw new Error('Unsupported snippet format');
  const [,clinicId,categoryId=null,packageId=null]=match.m;
  const origin=new URL(canonicalOrigin); if(origin.protocol!=='https:'||!allowedHosts.has(origin.hostname)||origin.username||origin.password) throw new Error('Canonical TelehealthUS origin must be secure HTTPS');
  const destinationPath=url.pathname;
  return {provider:'telehealthus',actionType:match.type,clinicId,categoryId,packageId,destinationPath,canonicalDestinationUrl:new URL(destinationPath,origin).href,sourceHash:createHash('sha256').update(input).digest('hex')};
}
export const presentationSchema=z.object({headline:z.string().max(100),description:z.string().max(400),ctaLabel:z.string().min(1).max(50),accent:z.string().regex(/^#[0-9a-f]{6}$/i),radius:z.enum(['sm','md','lg']),showPrice:z.boolean()}).strict();
export const eventSchema=z.object({widgetKey:z.string().min(8).max(80),type:z.enum(['view','cta_click','modal_open','iframe_ready','launch','conversion','runtime_error']),installationId:z.string().max(80).optional(),referrerHostname:z.string().max(253).optional(),device:z.enum(['mobile','tablet','desktop']).optional()}).strict();
