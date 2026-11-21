# 海砾 · 采样账本 WAL 恢复演练
海砾计量数据保障组（8人）用可重放日志替代恢复演练时手工拼接的SQL片段和账本截图。

## 场景与模块
上游为事务日志样例，下游为值班复核人。原流程人工标记提交、表格算恢复余额、截图写结论；痛点是崩溃点不清、撤销顺序容易错、恢复证据缺失。模块为事务日志集 / 故障注入点 / 恢复队列 / 恢复证据，实体LogSet/CrashCase/Recovery贯穿全栈。

扩展模块为跨站调拨场景 / 调拨恢复演练 / 调拨证据，实体TransferCase/TransferRun贯穿全栈：跨站采样调拨需两个账本同成同败，单账本恢复无法复核，故以同一全局事务关联各账本本地事务，按两阶段提交演练准备、裁决与断电恢复。

**Python WAL教学模型，不注入真实PostgreSQL故障，不执行数据库物理恢复。** PostgreSQL真实保存业务输入、冻结快照、任务和结果，Redis实际用于worker互斥，后台Python实际演算恢复历史。

## 启动
```bash
cp .env.example .env
docker compose up -d --build
# http://localhost:18246
# http://localhost:19246/docs
docker compose exec -T backend python -m scripts.seed_demo
docker compose down --remove-orphans
```
SEED_DEMO=true时启动自动执行种子；自然键查重，不覆盖用户修改。初始化失败显式阻止启动，不隐藏结构错误。删除数据需显式down -v。

|账号|密码|权限|典型动作|
|---|---|---|---|
|admin@haili.local|Recovery2026!|读写/导出/审计|查询审计记录|
|operator@haili.local|Recovery2026!|新增日志/场景/运行/导出|设置断电点10|
|viewer@haili.local|Recovery2026!|只读/导出|核对恢复账本|

## 一天的复核剧本
09:00操作员登录；09:05查看海砾采样账本-晚班（A100、B50）；09:10复制日志集保存shift-20261117；09:15在第10条日志后注入断电点；09:20提交恢复；09:25核对检查点LSN4、已提交T3、未提交T2两条写入逆序撤销，最终A60/B50；09:30下载JSON；09:40观察员核对且写操作403；10:00管理员查看/api/audits。

## 算法、格式和失败态
日志为JSON数组，操作为begin/write/commit/abort/checkpoint；write包含tx/key/value，其他事务操作包含tx，checkpoint不带tx。键必须在初始整数账本存在。事务ID不可复用；严格写锁直到commit/abort释放，同键重叠活动事务拒绝；检查点仅在无活动事务时允许。最多200条日志/30键/整数绝对值不超过10亿。

crash_after=N表示前N条日志已持久化。最近静止检查点保存全部数据页，检查点后数据页假定均未写回（no-force）。恢复重放日志写入和已abort的撤销，再按LSN倒序撤销未结束事务。独立oracle从检查点账本仅应用已提交事务写入，结果须相同。输出重做/撤销轨迹、事务集合、各阶段账本、SHA256和模型版本。空输入、未知键、事务顺序非法、检查点有活动事务、写锁冲突、崩溃点超限均拒绝。模型不涉及页LSN、CLR、模糊检查点或真实磁盘故障；不是完整ARIES实现。

## 跨站调拨两阶段提交演练
TransferCase冻结协调者裁决（commit/abort）、裁决是否落盘，以及1—5个参与账本各自的初始账本、本地写入和断电位置（0准备未落盘 / 1已准备裁决未落盘 / 2裁决已落盘）。TransferRun入队冻结快照，worker按断电前缀恢复：准备未落盘的账本本地回滚并释放写锁；裁决已落盘或协调者裁决落盘的账本按裁决执行；已准备但裁决未落盘的账本保持待决（pending）与写锁，绝不猜成撤销或完成，最终账本暂不公开。有效提交裁决要求全员已准备，存在准备未落盘账本时commit场景拒绝保存。

待决演练可POST /transfer-runs/{id}/decision补入缺失裁决接回任务：与协调者裁决相反的冲突裁决返回409拒绝；重复补入同一裁决幂等，不重复生效。全员裁决后所有参与账本的最终账本一起可见，防止跨站调拨半成半败造成数据丢失。页面05配置场景与各方断电位置，06提交演练，07查看待决原因、持有写锁、最终账本并下载JSON证据。引擎单测backend/tests/test_twopc_engine.py覆盖准备后失联、部分收到提交、相反裁决拒绝、提交要求全员准备、一起可见与幂等重试，运行cd backend && python -m unittest tests.test_twopc_engine。

## 工程与开发
前端原生HTML/CSS/JS+Nginx1.27；后端Python3.11+FastAPI+SQLAlchemy+PyJWT；PostgreSQL16和Redis7；5服务均healthcheck。持久任务队列在PG，单worker通过Redis锁互斥。20条待执行配额，审计记录写入操作，JWT8小时、PBKDF2随机盐密码。后端路由不含/api，Nginx/api/去前缀代理。

目录frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}与backend/src/{routes,controllers,services,models,schemas,middlewares,utils,constants,config}。本地开发安装backend/requirements.txt并设DATABASE_URL/REDIS_URL/JWT_SECRET，再运行uvicorn src.main:app；前端需代理/api。migrations记录初始化结构，暂无在线升级器。

环境COMPOSE_PROJECT_NAME控制命名，FRONTEND_PORT/BACKEND_PORT/DB_PORT为18246/19246/17746，DB_PASSWORD控制演示数据库密码，JWT_SECRET签名密钥，SEED_DEMO控制种子。命名卷db-data/redis-data/artifacts；共享artifacts预留，导出由冻结快照即时生成。Google Fonts需外网，业务离线可运行。默认凭据仅本地演示。

共享枚举roles与任务states（含调拨待决pending）定义于backend/src/constants/enums.py、frontend/src/constants/enums.js，状态使用models/entities.py/services/recovery_service.py/services/transfer_run_service.py/worker.py/components/common/status.js；日志操作类型在schemas/log_set.py和pages/logs.js中声明/说明，调拨断电位置与裁决标签在constants/enums.js与services/twopc_engine.py中声明。MIT许可。真实验证见批次test-artifacts/gb-4107/TESTING.md。
