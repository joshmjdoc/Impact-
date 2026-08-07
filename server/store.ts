import type { ActionBinding } from '../src/core.js';
export type Widget={id:string;publicKey:string;name:string;status:'draft'|'published'|'unpublished';binding:ActionBinding;presentation:{headline:string;description:string;ctaLabel:string;accent:string;radius:'sm'|'md'|'lg';showPrice:boolean};launchMode:'redirect'|'new_tab'|'modal'|'inline';version:number};
export const widgets=new Map<string,Widget>();
