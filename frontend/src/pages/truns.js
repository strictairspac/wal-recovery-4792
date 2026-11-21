import {store} from '../stores/entities.js';
import {session} from '../stores/session.js';
import {transferRunsAPI} from '../api/entities.js';
import {table} from '../components/common/table.js';
import {badge} from '../components/common/status.js';
import {esc,formObject} from '../utils/html.js';
import {action} from '../hooks/action.js';
export function trunsPage(){return `<section class="split compact"><div><h2>发起一次跨站调拨演练</h2><p>提交时冻结全局事务、协调者裁决与各方断电位置，后台按两阶段提交恢复：已准备但裁决未落盘的账本保持待决与写锁，可随后补入裁决接回。</p></div>${session.role!=='viewer'?`<form id="trun-form"><label>调拨场景<select name="transfer_case_id">${store.tcases.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select></label><label>记录标签<input name="label" value="晚班跨站调拨核对" required></label><button type="submit">冻结场景并执行 →</button></form>`:'<p class="readonly">观察员可查看下方调拨演练。</p>'}</section><div class="section-title"><h2>调拨演练队列</h2><button class="secondary" id="refresh">刷新状态</button></div>${table(['编号','演练记录','状态','全局结果','证据'],store.truns.map(r=>[r.id,esc(r.label),badge(r.status),r.result?(r.result.global_status==='completed'?'各账本一起可见':`待决 ${r.result.participants.filter(p=>p.outcome==='in_doubt').length} 方`):'待计算',`<a href="#tdetail/${r.id}">查看待决与账本 →</a>`]))}`;}
export function bindTruns(render){document.querySelector('#refresh').onclick=render;action(document.querySelector('#trun-form'),async f=>{const d=formObject(f);d.transfer_case_id=Number(d.transfer_case_id);const job=await transferRunsAPI.create(d);location.hash='#tdetail/'+job.id;});}
