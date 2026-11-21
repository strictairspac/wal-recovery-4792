/** @typedef {{id:number,name:string,initial:object,records:object[],description:string}} LogSet */
/** @typedef {{id:number,name:string,log_set_id:number,crash_after:number}} CrashCase */
/** @typedef {{id:number,crash_case_id:number,label:string,status:string,snapshot:object,result:object|null}} Recovery */
/** @typedef {{name:string,initial:object,writes:object[],crash_stage:0|1|2}} TransferParticipant */
/** @typedef {{id:number,name:string,decision:'commit'|'abort',decision_durable:boolean,participants:TransferParticipant[],description:string}} TransferCase */
/** @typedef {{id:number,transfer_case_id:number,label:string,status:string,snapshot:object,state:object|null,result:object|null}} TransferRun */
export {};
