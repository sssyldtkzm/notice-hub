"""Conservative event identity: exact evidence merges, incomplete evidence groups for review."""
from __future__ import annotations

import datetime as dt
import difflib
import json
import re
from .timeutil import parse_iso, iso, now_local


def normalize(text):
    text = re.sub(r'@(?:all|全体成员)|\[CQ:[^\]]+\]|\[(?:表情|图片)\]', '', text or '')
    return re.sub(r'[^\w\u4e00-\u9fff]', '', text).lower()


def facts(task):
    from .board import event_fields, explicit_deadline, is_homework
    body = str(task.get('source_text') or task.get('evidence') or task.get('summary') or '')
    # Sign-up roster revisions are not changes to the event identity.
    if '#接龙' in body:
        body = re.split(r'\n\s*1[.、]', body, maxsplit=1)[0]
    sent = parse_iso(task.get('source_sent_at') or task.get('sent_at'))
    fields = event_fields(body)
    reference = sent or parse_iso(task.get('created_at')) or now_local()
    # Keep date-only precision distinct from a known clock.
    due = explicit_deadline(body, reference) or task.get('deadline') or ''
    event = re.search(r'(?:活动时间|举办时间|会议时间|集合时间|时间)\s*[:：]\s*([^\n。；]+)', body)
    event_text = event[1] if event and not re.search(r'截止\s*$', body[max(0,event.start()-3):event.start()]) else ''
    if not event_text and not is_homework(body):
        event_text = fields.get('event_time') or ''
    event_date = explicit_deadline(event_text+' 截止', reference) if event_text else ''
    dates = {(int(m[1]),int(m[2])) for m in re.finditer(r'(?<!\d)(\d{1,2})[月/.-](\d{1,2})日?', body)}
    clock = bool(re.search(r'\d{1,2}[:：点时]|[一二三四五六七八九十两]+点', event_text))
    location = normalize(fields['location'])
    ordinals = set(re.findall(r'第([一二三四五六七八九十百\d]+)(次|章|讲|周)', body))
    courses = set(re.findall(r'微积分|高等数学|线性代数|概率论|大学英语|大学物理|有机化学|无机化学|分析化学|物理化学', body))
    name = re.search(r'(?:活动名称|讲座主题|活动主题|会议名称|主题)\s*[:：]\s*([^\n。；]+)',body)
    works = set(re.findall(r'《([^》]+)》',body))
    return dict(body=body, norm=normalize(body), sent=sent, due=parse_iso(due), event=parse_iso(event_date), clock=clock,
                location=location, dates=dates, ordinals=ordinals, courses=courses, homework=is_homework(body), name=normalize(name[1]) if name else '',works=works)


def relation(a, b):
    """Return (same|suspected|different, explanation). Never use generic title alone."""
    if b['id'] in a.get('_separate_with',set()) or a['id'] in b.get('_separate_with',set()):
        return 'different', ''
    x, y = a.get('_identity_facts') or facts(a), b.get('_identity_facts') or facts(b)
    if a.get('source') == 'manual' or b.get('source') == 'manual':
        return 'different', ''
    if not x['sent'] or not y['sent'] or x['homework'] != y['homework']:
        return 'different', ''
    if x['courses'] and y['courses'] and x['courses'].isdisjoint(y['courses']):
        return 'different', ''
    if x['name'] and y['name'] and x['name']!=y['name']:
        return 'different', ''
    if x['works'] and y['works'] and x['works'].isdisjoint(y['works']):
        return 'different', ''
    if x['ordinals'] and y['ordinals'] and x['ordinals'] != y['ordinals']:
        return 'different', ''
    if x['dates'] and y['dates'] and x['dates'].isdisjoint(y['dates']):
        return 'different', ''
    if x['location'] and y['location'] and x['location'] != y['location']:
        # Contained room names might be abbreviations, so leave them for review.
        if x['location'] not in y['location'] and y['location'] not in x['location']:
            return 'different', ''
    for key in ('due', 'event'):
        if x[key] and y[key]:
            if x[key].date() != y[key].date():
                return 'different', ''
            if key == 'due' and x[key] != y[key] and x[key].time() != dt.time(23,59) and y[key].time() != dt.time(23,59):
                return 'different', ''
            if key == 'event' and x['clock'] and y['clock'] and x[key] != y[key]:
                return 'different', ''
    recurring = re.search(r'晚点名|每日|每天|今日|今天|明天|签到|值日', x['body']+y['body'])
    if recurring and not (x['due'] and y['due']):
        if x['sent'].date() != y['sent'].date():
            return 'different', ''
    anchored = bool((x['due'] and y['due']) or (x['event'] and y['event']))
    if abs((x['sent']-y['sent']).days) > (35 if anchored else 2):
        return 'different', ''
    nx, ny = x['norm'], y['norm']
    identity_anchor = bool(anchored and ((x['name'] and x['name']==y['name'] and len(x['name'])>=4) or
                           (x['courses'] & y['courses'] and x['ordinals'] & y['ordinals']) or (x['works'] & y['works'])))
    if min(len(nx),len(ny)) < (10 if identity_anchor else 18):
        return 'different', ''
    exact = nx == ny
    ratio = difflib.SequenceMatcher(None,nx,ny,autojunk=False).ratio()
    bx,by={nx[i:i+2] for i in range(len(nx)-1)},{ny[i:i+2] for i in range(len(ny)-1)}
    overlap=len(bx&by)/max(1,min(len(bx),len(by)))
    # Multi-topic digests must not merge with a notice about only one of their topics.
    composite = any(re.search(r'消息通|\n\s*2[.、]', f['body']) for f in (x,y))
    strong = exact or (not composite and identity_anchor) or (not composite and ratio >= .72 and overlap >= .75) or (not composite and ratio >= .87) or (not composite and anchored and min(len(nx),len(ny))>=35 and overlap>=.96)
    if not strong:
        return 'different', ''
    if exact and (anchored or x['sent'].date()==y['sent'].date()):
        return 'same', '正文一致，日期吻合'
    precise_due = x['due'] and x['due']==y['due']
    precise_event = x['event'] and x['event']==y['event'] and x['clock'] and y['clock']
    precise_place = x['location'] and x['location']==y['location']
    if precise_place and precise_event and precise_due:
        return 'same', '活动时间、地点、截止日期及正文关键词吻合'
    if precise_place and precise_event and not x['due'] and not y['due']:
        return 'same', '活动时间、地点及正文关键词吻合'
    return 'suspected', '正文关键词相近，时间或地点信息不够完整，需确认'


def merge(store, target_id, source_id, reason='用户确认同一事件'):
    """Persist a source link without deleting the source task, text, or prior actions."""
    if type(target_id) is not int or type(source_id) is not int or target_id == source_id:
        raise ValueError('请选择两个不同的事项')
    with store._connect() as c:
        c.execute('BEGIN IMMEDIATE')
        target=c.execute('SELECT * FROM tasks WHERE id=?',(target_id,)).fetchone()
        source=c.execute('SELECT * FROM tasks WHERE id=?',(source_id,)).fetchone()
        if not target or not source or target['duplicate_of'] or source['duplicate_of']:
            raise ValueError('事项已变动，请刷新后重试')
        if target['status'] in ('dismissed','expired') or source['status'] in ('dismissed','expired'):
            raise ValueError('无法合并已忽略的事项')
        # Preserve completed work when an additional reminder arrives.
        done = target['status']=='done' or source['status']=='done'
        store._merge_task_groups(c,target_id,source['groups'])
        c.execute("UPDATE tasks SET status=?,done_at=CASE WHEN ? THEN ? ELSE done_at END,favorite=MAX(favorite,?),highlight=MAX(highlight,?),pinned=MAX(pinned,?),importance=MAX(importance,?),updated_at=? WHERE id=?",
                  ('done' if done else target['status'],done,source['done_at'] or target['done_at'] or iso(now_local()),source['favorite'],source['highlight'],source['pinned'],source['importance'],iso(now_local()),target_id))
        c.execute("UPDATE tasks SET status='dismissed',duplicate_of=?,updated_at=? WHERE id=?",(target_id,iso(now_local()),source_id))
        # Flatten links to avoid hidden chains if another canonical task is merged.
        c.execute('UPDATE tasks SET duplicate_of=? WHERE duplicate_of=?',(target_id,source_id))
        store._task_event(c,target_id,'event_merged',{'source_id':source_id,'reason':reason,'source_status':source['status']})
        store._task_event(c,source_id,'event_merged_into',{'target_id':target_id,'reason':reason,'previous_status':source['status']})
    return target_id


def consolidate(store, task_id=None):
    if task_id is not None:
        task=store.get_task(task_id)
        if not task or not task.get('source_sent_at') or task.get('duplicate_of'):
            return []
    rows=[t for t in store.list_tasks() if t['status'] in ('open','candidate','done') and not t.get('duplicate_of')]
    load_separations(store, rows)
    for row in rows:
        row['_identity_facts']=facts(row)
    rows.sort(key=lambda t:t['id'])
    merged=[]
    for i,a in enumerate(rows):
        if a.get('_merged'):
            continue
        for b in rows[i+1:]:
            if b.get('_merged') or (task_id is not None and task_id not in (a['id'],b['id'])):
                continue
            kind,reason=relation(a,b)
            if kind=='same':
                try:
                    merge(store,a['id'],b['id'],reason)
                except ValueError:
                    # Another ingestion worker may have already linked this source.
                    continue
                merged.append((a['id'],b['id']))
                b['_merged']=True
                a=store.get_task(a['id'])
    return merged


def load_separations(store, rows):
    with store._connect() as c:
        keys=[r['key'] for r in c.execute("SELECT key FROM meta WHERE key LIKE 'event_separate:%'")]
    pairs=[tuple(map(int,k.split(':')[1:])) for k in keys]
    for row in rows:
        row['_separate_with']={b if a==row['id'] else a for a,b in pairs if row['id'] in (a,b)}


def separate(store, first_id, second_id):
    if type(first_id) is not int or type(second_id) is not int or first_id==second_id:
        raise ValueError('请选择两个不同的事项')
    a,b=store.get_task(first_id),store.get_task(second_id)
    if not a or not b:
        raise ValueError('事项不存在')
    with store._connect() as c:
        for source,target in ((a,b),(b,a)):
            if source['duplicate_of']==target['id']:
                event=c.execute("SELECT detail FROM task_events WHERE task_id=? AND event='event_merged_into' ORDER BY id DESC LIMIT 1",(source['id'],)).fetchone()
                status=json.loads(event['detail']).get('previous_status','open') if event else 'open'
                c.execute('UPDATE tasks SET duplicate_of=0,status=?,updated_at=? WHERE id=?',(status,iso(now_local()),source['id']))
                store._task_event(c,source['id'],'event_separated',{'from_id':target['id']})
    store.meta_set('event_separate:'+':'.join(map(str,sorted((first_id,second_id)))),'1')
    return {'ok':True}
