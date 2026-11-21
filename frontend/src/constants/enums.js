export const ROLES = {admin:'管理员',operator:'操作员',viewer:'观察员'};
export const DRILL_STATUSES = {queued:'等待执行',running:'执行中',pending:'待决·写锁保持',completed:'已完成',failed:'失败'};
export const CRASH_STAGES = {0:'断电点0·准备未落盘',1:'断电点1·已准备·裁决未落盘',2:'断电点2·裁决已落盘'};
export const DECISIONS = {commit:'提交',abort:'撤销'};
export const OUTCOMES = {committed:'已提交',aborted:'已撤销',in_doubt:'待决'};
