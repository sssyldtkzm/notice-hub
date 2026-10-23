"""Select the actionable event clause, keeping its own time expression attached."""
import re

TIME = re.compile(
    r'(?:(?:下周|本周|这周|下星期|本星期|星期|周)[一二三四五六日天]|今天|明天|后天|今晚|明晚|今日|明日|'
    r'(?:20\d{2}[年/.-])?\d{1,2}[月/.-]\d{1,2}日?)'
    r'(?:[（(]\d{1,2}月\d{1,2}日?[）)])?'
    r'(?:\s*(?:凌晨|早上|上午|中午|下午|傍晚|晚上)?\s*(?:\d{1,2}|[一二三四五六七八九十两]+)(?:[:：]\d{2}|点(?:半|\d{1,2}分?)?))?'
)
ACTION = re.compile(r'开展|举行|举办|召开|组织|进行|安排|招募|征集|提交|上传|缴纳|填写|报名|完成|参加|集合|领取|返校|开课|检查|考试|测试|测验|培训|讲座')
EVENT = re.compile(r'卫生(?:大)?检查|大检查|讲座|论坛|会议|考试|测试|测验|作业|报告|报名|培训|比赛|竞赛|评选|评审|演出|答辩|查寝|运动会|开幕式|闭幕式')
ORGANIZE = re.compile(r'开展|举行|举办|召开|组织|进行|安排')
NOUN_END = re.compile(r'(?:大检查|检查|讲座|论坛|会议|考试|测试|测验|作业|报告|培训|比赛|竞赛|评选|评审|演出|答辩|运动会|开幕式|闭幕式|志愿服务|奖学金|助学金|学费减免|保险|体测|军训|查寝|展览|计划|项目|活动|课程|中心|申请表|登记表|汇总表)$')
GENERIC_NOUNS = {'活动','课程','报告','作业','考试','测试','会议','项目','计划','同学','老师','大家','时间','地点','要求','内容','情况','通知','公告','报名','各位同学','请各位同学','请大家','请同学们'}
BOUNDARY = re.compile(r'(?:请各位同学|各位同学|请同学们|请大家|同学们|各位|大家|我们|本次|此次|这个|这次|关于|针对|有关|参加|开展|举行|举办|召开|组织|进行|安排|提交|上传|填写|报名|完成|注意|及时|必须|需要|记得|已经|目前|后续|相关|同时|另外|以及|将于|定于|的|了|在|于|把|为|和|与|及|是|将)')


def notice_heading(sentence):
    """Recognize a notice as a document/topic, not the verb 'notify later'."""
    # Structured attributes never become an event name merely by mentioning 通知.
    if re.match(r'^(?:活动时间|举办时间|会议时间|集合时间|报名时间|截止时间|具体时间|时间|活动地点|地点|地址|报名方式|通知方式|服装要求|招募对象)\s*[:：]',sentence):
        return ''
    cleaned=re.sub(r'https?://[^\s，。；]+','',sentence).strip(' ：:')
    heading=re.search(r'【?(?:关于|有关)[^。！？\n]{3,100}?(?:通知|公告)】?',cleaned)
    bracket=re.search(r'[【《]([^】》\n]{3,100}(?:通知|公告))[】》]',cleaned)
    if heading or bracket:
        return heading[0] if heading else bracket[1]
    # Parenthetical scheduling, delivery/status messages and generic pointers are not headings.
    cleaned=re.sub(r'[（(][^）)]*(?:另行通知|另行公告|后续通知|届时通知|稍后通知)[^）)]*[）)]','',cleaned)
    if not re.search(r'公告|通知',cleaned):
        return ''
    if re.search(r'(?:另行|另作|后续|届时|稍后|到时候|单独|等待|等候|接到|收到|查收|会|再|将)\s*(?:再|另行)?\s*(?:公告|通知)|以.*通知为准|报名成功通知|通知(?:会|将在|将于|时间|方式|短信)',cleaned):
        return ''
    if re.fullmatch(r'请.*(?:后续通知|群公告)|.*(?:关注|阅读|查看)(?:相关)?(?:群)?(?:信息|通知|公告)',cleaned):
        return ''
    content=re.sub(r'公告|通知|重要|紧急|各位同学|同学们|全体成员|请大家|请注意|[\W_]', '',cleaned)
    return cleaned if len(content)>=2 else ''


def repeated_noun(clauses):
    """Find recurring nominal phrases, excluding greetings and generic instruction words."""
    candidates=set()
    cleaned=[TIME.sub('',c) for c in clauses]
    for clause in cleaned:
        for quoted in re.findall(r'[《【“]([^》】”]{2,24})[》】”]',clause):
            if quoted not in GENERIC_NOUNS and not re.search(r'提醒|通知|公告',quoted):
                candidates.add(quoted)
        for chunk in BOUNDARY.split(clause):
            for part in re.findall(r'[\u4e00-\u9fffA-Za-z0-9]{2,24}',chunk):
                for end in range(2,len(part)+1):
                    if NOUN_END.search(part[:end]):
                        value=re.sub(r'^本月','',part[:end])
                        if value not in GENERIC_NOUNS and (len(value)>=4 or value in {'体测','军训','查寝'}):
                            candidates.add(value)
    counts={noun:sum(c.count(noun) for c in cleaned) for noun in candidates}
    counts={noun:count for noun,count in counts.items() if count>=2}
    if not counts:
        return ''
    # Prefer a complete recurring noun phrase over an inner substring with the same count.
    return max(counts,key=lambda n:(counts[n]*min(len(n),12),len(n)))


def focus(text):
    value=re.sub(r'@(?:all|全体成员)|\[CQ:[^\]]+\]|\[(?:表情|图片)\]', '',text or '')
    clauses=[c.strip() for c in re.split(r'[\n。！？；，,]',value) if c.strip()]
    if not clauses:
        return {'title':'未命名事项','clause':'','time':''}
    def score(clause):
        has_time=bool(TIME.search(clause))
        has_action=bool(ACTION.search(clause))
        has_event=bool(EVENT.search(clause))
        result=6*has_time+4*has_action+3*has_event
        if has_time and (has_action or has_event): result+=6
        if ORGANIZE.search(clause): result+=3
        if re.search(r'截止时间|报名时间|活动时间|活动地点',clause) and not has_action: result-=6
        if re.search(r'温馨提醒|气温|流感|传染病|注意保暖|身体健康|发热|腹泻',clause) and not has_event: result-=5
        if re.search(r'已结束|已经结束|上周|去年|此前|回顾',clause): result-=5
        if re.search(r'请及时|请注意|做好准备',clause) and not has_time and not has_event: result-=3
        return result
    chosen=max(clauses,key=score)
    # A standalone date/venue follows an explicitly named event in structured notices.
    if score(chosen)<=0:
        chosen=clauses[0]
    basis='action_clause'
    notice_title=''
    notice_sentence=''
    sentences=[c.strip() for c in re.split(r'[\n。！？；]',value) if c.strip()]
    for sentence in sentences:
        if not re.search(r'公告|通知',sentence):
            continue
        candidate=notice_heading(sentence)
        if not candidate:
            continue
        notice_title=candidate
        notice_sentence=sentence
        break
    noun=repeated_noun(clauses) if not notice_title else ''
    if notice_title:
        basis='notice_sentence'
        # A heading may have no date: bind its topic to the relevant dated clause below.
        topic=re.sub(r'关于|公告|通知|[\W_]', '',notice_title)
        related=[c for c in clauses if c in notice_sentence or (topic and topic in c)]
        chosen=max(related or clauses,key=score)
        if not TIME.search(chosen):
            dated=[c for c in clauses if TIME.search(c) and (ACTION.search(c) or EVENT.search(c))]
            if len(dated)==1:
                chosen=dated[0]
    elif noun:
        basis='repeated_noun'
        chosen=max((c for c in clauses if noun in c),key=score)
    times=list(TIME.finditer(chosen))
    title=chosen
    organizing=ORGANIZE.search(chosen)
    if organizing and chosen[organizing.end():].strip():
        title=chosen[organizing.end():].strip()
    else:
        title=TIME.sub('',title)
        title=re.sub(r'(?:将于|定于|拟于|将|拟|于|前|后)\s*$', '',title)
        action=ACTION.search(title)
        if action and action.start()>0 and re.match(r'^(?:请|各位|全体|同学|大家|另|同时|提醒)',title):
            title=title[action.start():]
    title=re.sub(r'^(?:【温馨提醒】|温馨提醒|友情提醒|再次提醒|各位同学|各位老师|全体同学|同学们|大家好|另|另外|请大家|请各位同学)[：:、\s]*','',title).strip(' ：:、（）()')
    title=notice_title or noun or title
    if noun and not notice_title:
        recruitment=re.search(r'招募[^。！？\n]{0,24}?(参与人员|志愿者|工作人员|选手|参加人员|参加者)',value)
        if recruitment:
            title=noun+recruitment[1]+'招募'
    return {'title':title[:120] or chosen[:60],'clause':chosen,'time':times[0][0] if times else '', 'basis':basis}
