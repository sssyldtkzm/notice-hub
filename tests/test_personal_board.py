import datetime as dt
from types import SimpleNamespace

try:
    import pytest
except ImportError:
    import unittest
    raise unittest.SkipTest('Install requirements-dev.txt to run the personal pytest regressions')

from qq_live_digest import board
from qq_live_digest.store import Store
from qq_live_digest.webapp import group_tasks
from qq_live_digest.summarizer import build_digest
from qq_live_digest.config import Settings
from qq_digest import Message, extract_deadline


@pytest.mark.parametrize('text,hour,expected', [
    ('今天5点前请报车牌',13,17), ('今天五点半前请提交',13,17),
    ('今天上午5点前请提交',13,None), ('今早5点前请提交',13,None),
    ('今天05:00前请提交',13,None), ('今天5点前请提交',20,None),
    ('今天17点前请提交',13,17), ('今天13点前请提交',13,None),
])
def test_deadline_follows_original_send_time(text, hour, expected):
    result = extract_deadline(Message(dt.datetime(2026,10,23,hour), '', text))
    assert (result.hour if result else None) == expected


def test_repair_deadline_order_and_manual_validation(tmp_path):
    store = Store(tmp_path / 'order.sqlite')
    for key, text in [('ambiguous','今天5点前请报车牌'),('explicit','今天上午5点前请提交')]:
        store.insert_message(msg_id=key,group_id='42',content=text,ts='2026-10-23T13:43:07')
        task_id=store.upsert_task(task_key=key,summary=text,deadline='2026-10-23T05:00:00')
        # Simulate data written by the previous parser.
        with store._connect() as c:
            c.execute("UPDATE tasks SET deadline='2026-10-23T05:00:00' WHERE id=?",(task_id,))
    board.repair_deadline_order(store)
    tasks={t['task_key']:t for t in store.list_tasks()}
    assert tasks['ambiguous']['deadline']=='2026-10-23T17:00:00'
    assert tasks['explicit']['deadline']==''
    assert tasks['explicit']['deadline_issue']
    with pytest.raises(ValueError,match='晚于'):
        store.apply_task_correction(tasks['ambiguous']['id'],'deadline',value='2026-10-23T05:00:00')
    board.repair_deadline_order(store)
    assert store.get_task(tasks['ambiguous']['id'])['deadline']=='2026-10-23T17:00:00'


def test_explicit_deadline_uses_notice_not_import_date():
    text = '第二次微积分作业，请拍照上传。2026-10-22 22:00截止（满分100）'
    assert board.explicit_deadline(text, '2026-10-10T11:13:55') == '2026-10-22T22:00:00'
    assert board.explicit_deadline('半期考试预计在第十周周六', '2026-10-23T12:00:00') == ''
    assert board.explicit_deadline('活动时间：2026-10-25 15:00 地点：一教', '2026-10-23T12:00:00') == ''
    assert board.explicit_deadline('作业10月25日晚上10点截止', '2026-10-23T12:00:00') == '2026-10-25T22:00:00'


def test_no_40_or_800_item_display_cutoff(tmp_path):
    store = Store(tmp_path / 'test.sqlite')
    for number in range(805):
        store.upsert_task(task_key=f'task:{number}', summary=f'事项{number}', deadline='2026-10-22T22:00:00')
    tasks = store.list_tasks()
    assert len(tasks) == 805
    assert len(group_tasks(tasks, dt.datetime(2026, 10, 23))['today']) == 805
    assert len(store.list_tasks(limit=15)) == 15


def test_inbox_date_and_fulltext_and_priority(tmp_path):
    store = Store(tmp_path / 'test.sqlite')
    body = '第二次作业已发布，请拍照上传。2026-10-22 22:00截止。完整的最后一句'
    store.insert_message(msg_id='onebot:42:1', group_id='42', content=body, ts='2026-10-10T11:00:00')
    task_id = store.upsert_task(task_key='inbox:onebot:42:1', summary='第二次作业', evidence=body, groups=['42'], source='inbox')
    task = store.get_task(task_id)
    assert task['deadline'] == '2026-10-22T22:00:00'
    assert task['source_text'] == body
    assert task['source_sent_at'] == '2026-10-10T11:00:00'
    assert task['importance'] == 5


def test_columns_names_marks_and_sorting_survive_restart(tmp_path):
    path = tmp_path / 'test.sqlite'
    store = Store(path)
    store.remember_group_names({'42': '微积分课程群'})
    past = store.upsert_task(task_key='past', summary='作业', deadline='2026-09-22T22:00:00', groups=['42'])
    future = store.upsert_task(task_key='future', summary='作业提交', deadline='2099-10-30T22:00:00', groups=['42'])
    event = store.upsert_task(task_key='event', summary='志愿活动', evidence='活动名称：校园志愿服务\n时间：2099-10-25 15:00\n地点：江安图书馆报告厅', groups=['42'])
    board.mark(store, {'task_id': event, 'field': 'favorite', 'value': True})
    board.mark(store, {'task_id': past, 'field': 'highlight', 'value': True})
    data = board.payload(Store(path), SimpleNamespace(group_aliases={}))
    assert [item['id'] for item in data['columns']['homework']] == [future, past]
    assert data['columns']['homework'][0]['group_names'] == ['微积分课程群']
    assert data['columns']['homework'][0]['priority'] == 5
    assert data['columns']['other'][0]['location'] == '江安图书馆报告厅'
    assert {item['id'] for item in data['columns']['collection']} == {event, past}
    with pytest.raises(ValueError):
        board.mark(store, {'task_id': event, 'field': 'favorite; DROP TABLE tasks', 'value': True})
    with pytest.raises(ValueError):
        board.mark(store, {'task_id': event, 'field': 'favorite', 'value': 'true'})


def test_repair_recovers_missed_homework_once_and_keeps_done(tmp_path):
    store = Store(tmp_path / 'test.sqlite')
    body = '第二次微积分作业已发布，请拍照上传。2026-10-22 22:00截止'
    store.insert_message(msg_id='onebot:42:missed', group_id='42', content=body, ts='2026-10-10T11:00:00')
    store.mark_processed(['onebot:42:missed'], None)
    assert board.repair_store(store)['recovered'] == 1
    task = store.list_tasks()[0]
    assert task['deadline'] == '2026-10-22T22:00:00'
    store.apply_task_action(task['id'], 'done')
    assert board.repair_store(store)['recovered'] == 0
    assert store.get_task(task['id'])['status'] == 'done'


def test_more_than_30_notices_become_digest_items():
    records = []
    for number in range(45):
        month, day = 11 + number // 28, 1 + number % 28
        records.append({'msg_id': f'msg:{number}', 'group_id': str(number), 'group_name': f'课程{number}', 'sender_name': '老师', 'ts': '2026-10-23T12:00:00', 'received_at': '2026-10-23T12:00:00', 'content': f'第{number}次作业已发布，请提交报告。2026-{month:02}-{day:02} 22:00截止'})
    digest = build_digest(Settings(llm_enabled=False, max_items=1), records, now=dt.datetime(2026, 10, 23, 13))
    assert len(digest.items) == 45


def test_promoted_and_auto_task_share_same_message(tmp_path):
    store = Store(tmp_path / 'test.sqlite')
    first = store.upsert_task(task_key='inbox:onebot:42:1', summary='第二次作业')
    second = store.upsert_task(task_key='onebot:42:1', summary='第二次作业', deadline='2026-10-22T22:00:00')
    assert first == second
    assert len(store.list_tasks()) == 1


def test_board_api_rejects_unauthenticated_marks(tmp_path):
    import urllib.request
    import urllib.error
    import json
    from qq_live_digest.webapp import TaskWebServer
    store = Store(tmp_path / 'test.sqlite')
    task = store.upsert_task(task_key='a', summary='课程作业')
    settings = Settings(web_host='127.0.0.1', web_port=0, web_token='test-token')
    server = TaskWebServer(settings, store)
    server.start()
    base = 'http://127.0.0.1:' + str(server.server.server_address[1])
    try:
        with pytest.raises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(base + '/api/board')
        assert failure.value.code == 401
        body = json.dumps({'task_id': task, 'field': 'highlight', 'value': True}).encode()
        request = urllib.request.Request(base + '/api/board/mark', data=body, headers={'X-Token': 'test-token', 'Content-Type': 'application/json'}, method='POST')
        assert json.load(urllib.request.urlopen(request))['ok']
        request = urllib.request.Request(base + '/api/board', headers={'X-Token': 'test-token'})
        assert json.load(urllib.request.urlopen(request))['columns']['collection'][0]['id'] == task
    finally:
        server.stop()
