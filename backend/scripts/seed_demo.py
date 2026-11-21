import os
from sqlalchemy import select
from src.config.database import Base,engine,Session
from src.models.entities import User,LogSet,CrashCase,TransferCase
from src.utils.security import hash_password
RECORDS=[{'op':'begin','tx':'T1'},{'op':'write','tx':'T1','key':'sample_A','value':75},{'op':'commit','tx':'T1'},{'op':'checkpoint'},{'op':'begin','tx':'T2'},{'op':'write','tx':'T2','key':'sample_B','value':40},{'op':'begin','tx':'T3'},{'op':'write','tx':'T3','key':'sample_A','value':60},{'op':'commit','tx':'T3'},{'op':'write','tx':'T2','key':'sample_B','value':35},{'op':'commit','tx':'T2'}]
TRANSFER_CASES=[
 {'name':'跨站调拨-准备后失联','decision':'commit','decision_durable':False,'description':'甲站A转出30、乙站B转入30；协调者裁决未落盘，甲站准备后断电失联，乙站已收到提交',
  'participants':[{'name':'site_alpha','initial':{'sample_A':100},'writes':[{'key':'sample_A','value':70}],'crash_stage':1},
                  {'name':'site_beta','initial':{'sample_B':50},'writes':[{'key':'sample_B','value':80}],'crash_stage':2}]},
 {'name':'跨站调拨-裁决落盘接回','decision':'commit','decision_durable':True,'description':'协调者提交裁决已落盘，两站均只到准备，恢复时从协调者日志取回裁决',
  'participants':[{'name':'site_alpha','initial':{'sample_A':100},'writes':[{'key':'sample_A','value':70}],'crash_stage':1},
                  {'name':'site_beta','initial':{'sample_B':50},'writes':[{'key':'sample_B','value':80}],'crash_stage':1}]},
 {'name':'跨站调拨-全员撤销','decision':'abort','decision_durable':False,'description':'协调者撤销裁决未落盘，乙站已收到撤销，甲站准备后待决',
  'participants':[{'name':'site_alpha','initial':{'sample_A':100},'writes':[{'key':'sample_A','value':70}],'crash_stage':1},
                  {'name':'site_beta','initial':{'sample_B':50},'writes':[{'key':'sample_B','value':80}],'crash_stage':2}]},
]
def seed():
    Base.metadata.create_all(engine)
    if os.getenv('SEED_DEMO','true').lower()!='true':return
    with Session() as db:
        for role in ('admin','operator','viewer'):
            email=role+'@haili.local'
            if not db.scalar(select(User).where(User.email==email)):db.add(User(email=email,role=role,password_hash=hash_password('Recovery2026!')))
        logs=db.scalar(select(LogSet).where(LogSet.name=='海砾采样账本-晚班'))
        if logs is None:
            logs=LogSet(name='海砾采样账本-晚班',description='A初始100份、B初始50份，T1提交后检查点，T2未提交，T3已提交',initial={'sample_A':100,'sample_B':50},records=RECORDS);db.add(logs);db.flush()
        for name,point in [('断电点10-撤销T2',10),('完整提交点11',11),('初始点0',0)]:
            if not db.scalar(select(CrashCase).where(CrashCase.name==name)):db.add(CrashCase(name=name,log_set_id=logs.id,crash_after=point))
        for case in TRANSFER_CASES:
            if not db.scalar(select(TransferCase).where(TransferCase.name==case['name'])):db.add(TransferCase(**case))
        db.commit()
if __name__=='__main__':seed()
