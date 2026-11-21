import logging, time
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models.entities import Recovery, TransferRun
from src.services.wal_engine import recover
from src.services.transfer_run_service import run_transfer
redis = Redis.from_url(REDIS_URL)
logging.basicConfig(level=logging.INFO)
# Redis leadership lock ensures only one worker processes the durable DB queue.
while True:
    Path('/tmp/heartbeat').touch()
    lock = redis.lock('wal-worker', timeout=15, blocking_timeout=1)
    try:
        with lock:
            with Session() as db:
                job = db.scalar(select(Recovery).where(Recovery.status == 'queued').order_by(Recovery.id).with_for_update(skip_locked=True))
                if job:
                    job.status = 'running'
                    try:
                        job.result = recover(job.snapshot['log_set']['initial'],job.snapshot['log_set']['records'],job.snapshot['case']['crash_after'])
                        job.status = 'completed'
                    except ValueError as exc:
                        job.result = {'error': str(exc), 'simulation': True}
                        job.status = 'failed'
                    db.commit()
                    logging.info('recovery %s %s', job.id, job.status)
                transfer = db.scalar(select(TransferRun).where(TransferRun.status == 'queued').order_by(TransferRun.id).with_for_update(skip_locked=True))
                if transfer:
                    transfer.status = 'running'
                    try:
                        result = run_transfer(transfer.snapshot, {})
                        transfer.result = result
                        transfer.state = {'supplied': {}, 'resolved': {p['name']: p['outcome'] for p in result['participants']}}
                        transfer.status = 'completed' if result['global_status'] == 'completed' else 'pending'
                    except ValueError as exc:
                        transfer.result = {'error': str(exc), 'simulation': True}
                        transfer.status = 'failed'
                    db.commit()
                    logging.info('transfer run %s %s', transfer.id, transfer.status)
    except Exception:
        logging.exception('worker retry')
    time.sleep(1)
