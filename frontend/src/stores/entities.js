import {logSetsAPI,crashCasesAPI,recoveriesAPI,transferCasesAPI,transferRunsAPI} from '../api/entities.js';
export const store={logs:[],cases:[],runs:[],tcases:[],truns:[],async refresh(){[this.logs,this.cases,this.runs,this.tcases,this.truns]=await Promise.all([logSetsAPI.list(),crashCasesAPI.list(),recoveriesAPI.list(),transferCasesAPI.list(),transferRunsAPI.list()]);}};
