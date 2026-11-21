"""Blocking two-phase commit teaching model for cross-site sampling transfers.

One global transaction links local transactions on participant ledgers.
Each party gets its own power-loss point: the coordinator may lose its
decision record, each participant may lose its prepare or decision record.
A prepared participant without a durable decision stays in-doubt and keeps
its write locks; the model never guesses abort or commit on its behalf.
"""
import copy, hashlib, json, re

STAGES = (0, 1, 2)  # 0=准备未落盘 1=已准备·裁决未落盘 2=裁决已落盘
STAGE_LABELS = {0: '断电点0·准备记录未落盘', 1: '断电点1·已准备但裁决未落盘', 2: '断电点2·裁决记录已落盘'}
DECISIONS = ('commit', 'abort')
KEY = r'[A-Za-z0-9_-]{1,50}'
NAME = r'[A-Za-z0-9_-]{1,30}'


def _check_ledger(initial):
    if not initial or len(initial) > 30:
        raise ValueError('各参与账本需1—30个键')
    for key, value in initial.items():
        if not re.fullmatch(KEY, key) or isinstance(value, bool) or not isinstance(value, int) or abs(value) > 1000000000:
            raise ValueError('账本键为字母数字下划线短横线，值为绝对值不超过10亿的整数')


def validate_case(decision, decision_durable, participants):
    if decision not in DECISIONS:
        raise ValueError('协调者裁决仅支持commit或abort')
    if not isinstance(decision_durable, bool):
        raise ValueError('协调者裁决落盘标记需为布尔值')
    if not participants or len(participants) > 5:
        raise ValueError('需1—5个参与账本')
    seen = set()
    for p in participants:
        name = p.get('name')
        if not name or not re.fullmatch(NAME, name):
            raise ValueError('参与账本名为1—30位字母数字下划线短横线')
        if name in seen:
            raise ValueError(f'参与账本{name}重复')
        seen.add(name)
        _check_ledger(p.get('initial') or {})
        writes = p.get('writes') or []
        if not writes or len(writes) > 30:
            raise ValueError(f'参与账本{name}需1—30条本地写入')
        keys = set()
        for w in writes:
            key, value = w.get('key'), w.get('value')
            if key not in p['initial']:
                raise ValueError(f'参与账本{name}写入键必须存在于初始账本')
            if key in keys:
                raise ValueError(f'参与账本{name}重复写入键{key}')
            keys.add(key)
            if isinstance(value, bool) or not isinstance(value, int) or abs(value) > 1000000000:
                raise ValueError(f'参与账本{name}写入数值超限')
        if p.get('crash_stage') not in STAGES:
            raise ValueError(f'参与账本{name}断电位置仅支持0/1/2')
    # A valid commit decision requires every participant prepared; a lost
    # prepare record means that ledger rolled back and commit would lose data.
    if decision == 'commit' and any(p['crash_stage'] == 0 for p in participants):
        raise ValueError('有效提交裁决要求全员已准备：存在准备记录未落盘的参与账本')
    return True


def _apply(initial, writes):
    ledger = copy.deepcopy(initial)
    for w in writes:
        ledger[w['key']] = w['value']
    return ledger


def recover(decision, decision_durable, participants, supplied=None):
    """Replay one global 2PC transaction from each party's durable prefix.

    supplied maps participant name -> decision backfilled by the operator.
    Returns per-participant outcomes, held locks, pending reasons and, only
    when every participant is resolved, all final ledgers made visible at once.
    """
    validate_case(decision, decision_durable, participants)
    supplied = dict(supplied or {})
    for name, d in supplied.items():
        if name not in {p['name'] for p in participants}:
            raise ValueError(f'补入裁决的参与账本{name}不存在')
        if d not in DECISIONS:
            raise ValueError('补入裁决仅支持commit或abort')
        if d != decision:
            raise ValueError('冲突裁决：与协调者已记录的裁决相反，拒绝接回')
    if decision == 'commit' and any(p['crash_stage'] == 0 for p in participants):
        raise ValueError('有效提交裁决要求全员已准备')

    outcome, trace, pending = [], [], []
    for p in participants:
        name, stage, writes = p['name'], p['crash_stage'], p['writes']
        locks = [w['key'] for w in writes]
        if stage == 0:
            row = {'name': name, 'crash_stage': stage, 'outcome': 'aborted', 'locks': [],
                   'final': copy.deepcopy(p['initial']),
                   'reason': '准备记录未持久化：本地事务按未提交回滚，写锁释放'}
            trace.append({'participant': name, 'event': 'local_abort', 'detail': '准备未落盘，回滚本地事务'})
        elif stage == 2:
            done = decision == 'commit'
            row = {'name': name, 'crash_stage': stage, 'outcome': 'committed' if done else 'aborted', 'locks': [],
                   'final': _apply(p['initial'], writes) if done else copy.deepcopy(p['initial']),
                   'reason': f"裁决记录已持久化：按协调者{'提交' if done else '撤销'}执行，写锁释放"}
            trace.append({'participant': name, 'event': 'apply_durable_decision', 'detail': f'本地裁决记录{decision}已落盘'})
        elif decision_durable:
            done = decision == 'commit'
            row = {'name': name, 'crash_stage': stage, 'outcome': 'committed' if done else 'aborted', 'locks': [],
                   'final': _apply(p['initial'], writes) if done else copy.deepcopy(p['initial']),
                   'reason': '已准备；恢复时从协调者日志取回裁决，接回待决任务'}
            trace.append({'participant': name, 'event': 'fetch_decision', 'detail': '协调者裁决落盘，恢复时取回'})
        elif name in supplied:
            done = supplied[name] == 'commit'
            row = {'name': name, 'crash_stage': stage, 'outcome': 'committed' if done else 'aborted', 'locks': [],
                   'final': _apply(p['initial'], writes) if done else copy.deepcopy(p['initial']),
                   'reason': '已准备；裁决未落盘，补入缺失裁决后接回待决任务'}
            trace.append({'participant': name, 'event': 'supply_decision', 'detail': f'补入裁决{supplied[name]}，幂等接回'})
        else:
            row = {'name': name, 'crash_stage': stage, 'outcome': 'in_doubt', 'locks': locks, 'final': None,
                   'reason': '已准备但裁决未落盘：保持待决与写锁，不得猜为撤销或完成'}
            pending.append(f'{name}：{row["reason"]}')
            trace.append({'participant': name, 'event': 'in_doubt', 'detail': f'待决，持有写锁{",".join(locks)}'})
        row['stage_label'] = STAGE_LABELS[stage]
        row['writes'] = writes
        outcome.append(row)

    finished = all(r['outcome'] != 'in_doubt' for r in outcome)
    # Atomic visibility: final ledgers are published only together, once no
    # participant remains in-doubt, so a partial transfer is never observed.
    final_ledgers = {r['name']: r['final'] for r in outcome} if finished else None
    source = json.dumps({'decision': decision, 'decision_durable': decision_durable,
                         'participants': participants, 'supplied': supplied}, sort_keys=True)
    body = json.dumps(final_ledgers, sort_keys=True) if finished else 'pending'
    return {'simulation': True, 'model_version': 'twopc-blocking-v1', 'decision': decision,
            'decision_durable': decision_durable, 'global_status': 'completed' if finished else 'pending',
            'participants': [{k: v for k, v in r.items() if k != 'writes'} for r in outcome],
            'pending_reasons': pending, 'supplied_decisions': supplied,
            'final_ledgers': final_ledgers, 'ledgers_visible_together': finished,
            'trace': trace, 'result_sha256': hashlib.sha256(body.encode()).hexdigest(),
            'input_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'boundary': 'Python两阶段提交教学模型；协调者与各参与账本分别设定断电位置，已准备未裁决保持待决与写锁。没有注入真实PostgreSQL崩溃，未执行数据库物理恢复。'}
