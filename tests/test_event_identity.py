import json
from types import SimpleNamespace
try:
    import pytest
except ImportError:
    import unittest
    raise unittest.SkipTest('Install requirements-dev.txt to run the personal pytest regressions')
from qq_live_digest.store import Store
from qq_live_digest import board
from qq_live_digest.event_identity import relation, consolidate, merge, separate


def task(i,body,due='',group='1',sent='2026-10-23T13:00:00'):
    return dict(id=i,summary=body,evidence=body,source_sent_at=sent,deadline=due,groups=[group],source='qq_message')


@pytest.mark.parametrize('a,b,kind',[
 ('活动名称：校园科技讲座\n活动时间：明天早上6点\n地点：一教101\n请同学们准时参加校园科技讲座',
  '活动名称：校园科技讲座\n活动时间：明天\n请同学们准时参加校园科技讲座','suspected'),
 ('活动名称：校园科技讲座\n活动时间：明天早上6点\n地点：一教101\n请同学们准时参加校园科技讲座',
  '活动名称：校园科技讲座\n活动时间：明天早上7点\n地点：一教101\n请同学们准时参加校园科技讲座','different'),
 ('活动名称：校园科技讲座\n活动时间：明天早上6点\n地点：一教101\n请同学们准时参加校园科技讲座',
  '活动名称：校园科技讲座\n活动时间：明天早上6点\n地点：一教102\n请同学们准时参加校园科技讲座','different'),
 ('第二次微积分作业已发布，请拍照上传函数极限所有题目，10月30日22点截止',
  '第三次微积分作业已发布，请拍照上传函数极限所有题目，10月30日22点截止','different'),
 ('请大家完成微积分课程作业，10月30日22点前提交所有题目',
  '请大家完成大学英语课程作业，10月30日22点前提交所有题目','different'),
])
def test_event_facts(a,b,kind):
    assert relation(task(1,a),task(2,b))[0]==kind


def test_time_place_keywords_can_confirm_same():
    a='活动名称：校园科技讲座\n活动时间：明天早上6点\n地点：一教101\n请同学们准时参加校园科技讲座，报名截止10月23日22点'
    b=a.replace('请同学们准时','再次提醒同学们准时')
    assert relation(task(1,a),task(2,b))[0]=='same'
    assert relation(task(1,a),task(2,b.replace('校园科技讲座','校园艺术讲座')))[0]=='different'


def test_daily_notice_and_different_deadlines_stay_separate():
    text='请各位寝室长按时填写寝室晚点名情况，及时跟进尚未归寝同学'
    assert relation(task(1,text),task(2,text,sent='2026-10-24T13:00:00'))[0]=='different'
    text='请同学们完成本次微积分作业并上传学习通，注意按时提交'
    assert relation(task(1,text,'2026-10-25T22:00:00'),task(2,text,'2026-10-30T22:00:00'))[0]=='different'


def test_brief_course_reminder_uses_course_assignment_and_due():
    a='第二次微积分作业已在学习通发布，请拍照上传所有课后习题，10月30日22点截止'
    b='提醒：第二次微积分作业记得交哦，10月30日22点截止'
    assert relation(task(1,a),task(2,b))[0]=='suspected'


def insert(store,key,body,group='1',due=''):
    store.insert_message(msg_id=key,group_id=group,content=body,ts='2026-10-23T13:00:00')
    return store.upsert_task(task_key=key,summary=body,evidence=body,groups=[group],deadline=due,source='qq_message')


def test_cross_group_merge_keeps_sources_marks_and_done_on_future_reminder(tmp_path):
    store=Store(tmp_path/'test.db')
    body='第二次微积分作业已发布，请拍照上传函数极限所有题目，10月30日22点截止'
    first=insert(store,'teacher',body)
    board.mark(store,{'task_id':first,'field':'favorite','value':True})
    store.apply_task_action(first,'done')
    again=insert(store,'class',body,group='2')
    assert again==first
    rows=store.list_tasks();child=next(t for t in rows if t['task_key']=='class')
    assert child['duplicate_of']==first
    assert store.get_task(first)['status']=='done'
    assert set(store.get_task(first)['groups'])=={'1','2'}
    data=board.payload(store,SimpleNamespace(group_aliases={'1':'课程群','2':'班级群'}))
    item=data['columns']['homework'][0]
    assert data['counts']['done']==1 and item['favorite']
    assert len(item['merged_sources'])==1
    assert item['merged_sources'][0]['body']==body
    assert insert(store,'class',body,group='2')==first
    assert consolidate(store)==[]
    separate(store,first,child['id'])
    assert store.get_task(child['id'])['duplicate_of']==0
    assert consolidate(store)==[]


def test_suspected_group_does_not_complete_other_until_confirmation(tmp_path):
    store=Store(tmp_path/'test.db')
    a='活动名称：校园科技讲座\n活动时间：明天早上6点\n地点：一教101\n请同学们准时参加校园科技讲座'
    b='活动名称：校园科技讲座\n活动时间：明天\n请同学们准时参加校园科技讲座'
    first=insert(store,'a',a);second=insert(store,'b',b,'2')
    assert first!=second
    data=board.payload(store,SimpleNamespace(group_aliases={}))
    items=data['columns']['other']
    assert len(items)==2 and items[0]['related_id']==items[1]['related_id']
    store.apply_task_action(first,'done')
    assert store.get_task(second)['status']=='open'
    merge(store,first,second)
    assert store.get_task(first)['status']=='done'
    assert store.get_task(second)['duplicate_of']==first
    with pytest.raises(ValueError): merge(store,first,first)


def test_unrelated_generic_titles_never_merge(tmp_path):
    store=Store(tmp_path/'test.db')
    a=insert(store,'a','#接龙\n校园科技讲座报名截止10月30日22点')
    b=insert(store,'b','#接龙\n校园艺术晚会报名截止10月30日22点')
    assert a!=b
