from types import SimpleNamespace
from qq_live_digest import board
from qq_live_digest.notice_focus import focus
from qq_live_digest.store import Store


NOTICE='【温馨提醒】各位同学：秋日气温多变，容易出现流感、肠道类等传染病，如出现发热、腹泻等不适，请及时到校医院就医。同时注意维护宿舍清洁卫生，消除蚊虫孳生环境。另下周五（10月23日）将开展本月卫生大检查，请各位同学提前做好准备[表情]@all'


def test_main_event_is_late_in_notice():
    fields=board.event_fields(NOTICE)
    assert fields['event_name']=='本月卫生大检查'
    assert fields['event_time']=='下周五（10月23日）'
    assert '气温' not in fields['event_name']
    assert '下周五' in fields['focus_text']


def test_time_stays_with_its_event_not_first_unrelated_date():
    text='今天上午8点完成了晨跑，天气转凉注意保暖。下周五下午3点将举办校园科技讲座，请同学们报名。'
    fields=board.event_fields(text)
    assert fields['event_name']=='校园科技讲座'
    assert fields['event_time']=='下周五下午3点'


def test_plain_action_and_structured_title():
    assert '提交' in focus('各位同学好！请大家于本周五提交课程报告，注意格式。')['title']
    fields=board.event_fields('温馨提醒请注意保暖。活动名称：校园志愿服务\n时间：10月25日15:00\n地点：一教101')
    assert fields['event_name']=='校园志愿服务'
    assert fields['location']=='一教101'


def test_deadline_label_is_not_event_time():
    fields=board.event_fields('下周五将举办校园科技讲座。报名截止时间：10月20日22:00。')
    assert fields['event_time']=='下周五'


def test_existing_notice_uses_original_send_time_for_next_friday(tmp_path):
    store=Store(tmp_path/'test.db')
    store.insert_message(msg_id='notice',group_id='1',content=NOTICE,ts='2026-10-16T16:27:18')
    task_id=store.upsert_task(task_key='notice',summary='温馨提醒，各位同学',evidence=NOTICE,groups=['1'],deadline='2026-10-23T23:59:00')
    item=next(t for t in board.payload(store,SimpleNamespace(group_aliases={}))['columns']['other'] if t['id']==task_id)
    assert item['title']=='本月卫生大检查'
    assert item['sort_time'].startswith('2026-10-23')
    assert item['body']==NOTICE


def test_notice_sentence_precedes_action_sentence_and_stays_bound_to_event():
    text='关于开展本学期卫生大检查的通知。下周五将开展本学期卫生大检查，请同学们做好准备。'
    fields=board.event_fields(text)
    assert fields['event_name']=='关于开展本学期卫生大检查的通知'
    assert fields['event_time']=='下周五'
    assert fields['naming_basis']=='notice_sentence'


def test_announcement_precedes_explicit_label():
    fields=board.event_fields('活动名称：待定名称\n关于校园科技讲座的公告\n下周五举办校园科技讲座。')
    assert fields['event_name']=='关于校园科技讲座的公告'


def test_repeated_noun_is_preferred_without_notice_heading():
    fields=board.event_fields('各位同学，校园科技讲座开始报名。校园科技讲座将于下周五举行，请参加校园科技讲座的同学提前准备。')
    assert fields['event_name']=='校园科技讲座'
    assert fields['event_time']=='下周五'
    assert fields['naming_basis']=='repeated_noun'


def test_generic_repetition_and_followup_notice_are_not_event_names():
    fields=board.event_fields('请各位同学关注后续通知。请各位同学注意保暖。下周五将开展卫生大检查，请各位同学提前准备。')
    assert fields['event_name']=='卫生大检查'


def test_bare_notice_label_is_not_a_title():
    assert board.event_fields('【通知】\n下周五将开展卫生大检查。')['event_name']=='卫生大检查'


def test_notice_title_excludes_link_and_following_instructions():
    fields=board.event_fields('【演讲比赛】关于开展校园演讲比赛的通知https://example.com/article，请参赛同学于明天提交报名表。')
    assert fields['event_name']=='关于开展校园演讲比赛的通知'
    assert fields['event_time']=='明天'
    assert board.event_fields('缴费通知：https://example.com/payment')['event_name']=='缴费通知'


SPORTS_NOTICE='''四川大学学生田径运动会开幕式要来啦！
咱们化学工程学院现在开始招募开幕式参与人员～
参与即有——体育二课时长
活动内容：田径运动会开幕式
活动时间：10月23日上午（具体时间另行通知）
招募对象：化学工程学院全体同学
服装要求：灰色文化衫
报名方式：请有意愿参与的同学加入报名群，报名表将在此群中发布。'''


def test_sports_ceremony_recruitment_not_incidental_notification():
    fields=board.event_fields(SPORTS_NOTICE)
    assert fields['event_name']=='田径运动会开幕式参与人员招募'
    assert '10月23日上午' in fields['event_time']
    assert fields['naming_basis']=='repeated_noun'


def test_time_notice_does_not_override_topic_even_without_time_label():
    text=SPORTS_NOTICE.replace('活动时间：','').replace('（具体时间另行通知）','，具体时间稍后通知')
    assert board.event_fields(text)['event_name']=='田径运动会开幕式参与人员招募'


def test_notification_delivery_is_not_an_event_title():
    text='校园科技讲座开始报名。校园科技讲座下周五举行。报名成功通知将在今天通过短信发送。'
    assert board.event_fields(text)['event_name']=='校园科技讲座'


def test_real_notice_heading_keeps_priority_with_notify_later_in_body():
    text='关于学生田径运动会开幕式参与人员招募的通知\n'+SPORTS_NOTICE
    assert board.event_fields(text)['event_name']=='关于学生田径运动会开幕式参与人员招募的通知'
