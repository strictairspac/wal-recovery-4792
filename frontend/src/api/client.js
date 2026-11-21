import {session} from '../stores/session.js';
export async function api(path, options={}) {
 const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json','Authorization':'Bearer '+session.token,...options.headers}});
 if(!response.ok){const data=await response.json().catch(()=>({}));if(response.status===401 && path!='/auth/login'){session.clear();location.hash='#login';}throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||'请求失败'));}
 return response.json();
}
export async function download(id){const r=await fetch('/api/recoveries/'+id+'/export',{headers:{Authorization:'Bearer '+session.token}});if(!r.ok)throw new Error('导出失败');saveBlob(await r.blob(),'recovery-'+id+'.json');}
export async function downloadTransfer(id){const r=await fetch('/api/transfer-runs/'+id+'/export',{headers:{Authorization:'Bearer '+session.token}});if(!r.ok)throw new Error('导出失败');saveBlob(await r.blob(),'transfer-run-'+id+'.json');}
function saveBlob(blob,name){const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
