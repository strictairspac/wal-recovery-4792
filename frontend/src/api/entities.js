import {api} from './client.js';
export const logSetsAPI={list:()=>api('/log-sets'),create:data=>api('/log-sets',{method:'POST',body:JSON.stringify(data)})};
export const crashCasesAPI={list:()=>api('/crash-cases'),create:data=>api('/crash-cases',{method:'POST',body:JSON.stringify(data)})};
export const recoveriesAPI={list:()=>api('/recoveries'),get:id=>api('/recoveries/'+id),create:data=>api('/recoveries',{method:'POST',body:JSON.stringify(data)})};
export const transferCasesAPI={list:()=>api('/transfer-cases'),create:data=>api('/transfer-cases',{method:'POST',body:JSON.stringify(data)})};
export const transferRunsAPI={list:()=>api('/transfer-runs'),get:id=>api('/transfer-runs/'+id),create:data=>api('/transfer-runs',{method:'POST',body:JSON.stringify(data)}),decide:(id,data)=>api('/transfer-runs/'+id+'/decision',{method:'POST',body:JSON.stringify(data)})};
