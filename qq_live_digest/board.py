"""Personal task board: conservative extraction, persistent marks and complete lists."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from .timeutil import iso, now_local, parse_iso

HOMEWORK = re.compile(r"作业|习题|课后练习|实验报告|实验预习|课程报告|课程论文|课后题")
DATE = re.compile(r"(?<!\d)(?:(20\d{2})[年/.-])?(\d{1,2})[月/.-](\d{1,2})日?(?:[ T，,]*([0-2]?\d)[:：]([0-5]\d))?")
CLOCK = re.compile(r"(?:上午|下午|晚上|中午)?\s*\d{1,2}(?:[:：]\d{2}|点(?:半|\d{1,2}分)?)")
DEADLINE_WORDS = re.compile(r"截止|最晚|之前|前提交|前交|交作业|提交时间|补交")


def is_homework(text: str) -> bool:
    return bool(HOMEWORK.search(text or ""))


def checked_deadline(value: Any, reference: Any, text: str) -> tuple[str, str]:
    due, sent = parse_iso(value), parse_iso(reference)
    if not due or not sent or due > sent:
        return (iso(value) if isinstance(value, dt.datetime) else str(value or "")), ""
    from qq_digest import deadline_after_sent
    corrected = deadline_after_sent(due, sent, text)
    return (iso(corrected), "") if corrected else ("", "时间冲突，待确认")


def explicit_deadline(text: str, reference: Any = None) -> str:
    """Only trust dates near deadline language; do not invent dates for teaching weeks."""
    reference = parse_iso(reference) if not isinstance(reference, dt.datetime) else reference
    reference = reference or now_local()
    choices = []
    for match in DATE.finditer(text or ""):
        context = text[max(0, match.start() - 14): match.end() + 45]
        if not DEADLINE_WORDS.search(context):
            continue
        try:
            year = int(match[1] or reference.year)
            hour, minute = int(match[4] or 23), int(match[5] or 59)
            if not match[4]:
                clock = re.match(r"\s*(上午|下午|晚上|中午|凌晨)?\s*(\d{1,2})点(?:(半)|(\d{1,2})分?)?", text[match.end():match.end()+20])
                if clock:
                    hour, minute = int(clock[2]), 30 if clock[3] else int(clock[4] or 0)
                    if clock[1] in {"下午", "晚上", "中午"} and hour < 12:
                        hour += 12
            # An explicitly stated afternoon clock retains its actual hour.
            if match[4] and re.search(r"下午|晚上", context) and hour < 12:
                hour += 12
            value = dt.datetime(year, int(match[2]), int(match[3]), hour, minute)
            choices.append((0 if match[1] else 1, abs(DEADLINE_WORDS.search(context).start() - (match.start() - max(0, match.start() - 14))), value))
        except ValueError:
            continue
    if choices:
        return checked_deadline(sorted(choices, key=lambda x: (x[0], x[1]))[0][2], reference, text)[0]
    if DEADLINE_WORDS.search(text or "") and re.search(r"今天|明天|后天|今晚|明晚|本周|下周", text or "") and not re.search(r"第[一二三四五六七八九十\d]+周", text or ""):
        import qq_digest
        return iso(qq_digest.extract_deadline(qq_digest.Message(reference, "", text)))
    return ""


def clean_title(text: str) -> str:
    value = re.sub(r"@(?:all|全体成员)|\[CQ:[^\]]+\]", "", text or "").strip()
    return re.split(r"[\n。！？]", value, maxsplit=1)[0].strip(" ：:，,")[:48] or "未命名事项"


def event_fields(text: str) -> dict[str, str]:
    from .notice_focus import focus
    selected = focus(text)
    name = re.search(r"(?:活动名称|讲座主题|活动主题|会议名称|主题)\s*[:：]\s*([^\n。；]{2,100})", text)
    location = re.search(r"(?:活动地点|举办地点|集合地点|上课地点|地点|地址)\s*[:：]\s*([^\n。；]{2,100})", text)
    if not location:
        location = re.search(r"(?:在|到|于)\s*([^\n，。；]{1,35}(?:教室|报告厅|礼堂|体育馆|会议室|操场|广场|[A-Z]?\d{3,4}))(?:[，。；\s]|$)", text)
    time = re.search(r"(?<!截止)(?<!提交)(?:活动时间|举办时间|集合时间|会议时间|时间)\s*[:：]\s*([^\n。；]{2,100})", text)
    time_text = time[1].strip() if time else selected['time']
    title = selected['title'] if selected.get('basis') in {'notice_sentence','repeated_noun'} else (name[1].strip() if name else selected['title'])
    return {"event_name": title, "event_time": time_text, "location": location[1].strip() if location else "", "focus_text": selected['clause'], "naming_basis": selected.get('basis','action_clause')}


def sort_key(task: dict[str, Any], now: dt.datetime) -> tuple:
    deadline = parse_iso(task.get("sort_time") or task.get("deadline"))
    if deadline is None:
        return (2, dt.datetime.max, int(task["id"]))
    if deadline.date() < now.date():
        return (1, -deadline.timestamp(), int(task["id"]))
    return (0, deadline.timestamp(), int(task["id"]))


def payload(store: Any, settings: Any) -> dict[str, Any]:
    now = now_local()
    tasks = store.list_tasks()
    from .event_identity import relation, facts, load_separations
    live = [t for t in tasks if t['status'] not in {'dismissed','expired'}]
    load_separations(store, live)
    for task in live:
        task['_identity_facts'] = facts(task)
    related = []
    for task in live:
        cluster = next((g for g in related if all(relation(task,other)[0] in {'same','suspected'} for other in g)), None)
        if cluster is None:
            related.append([task])
        else:
            cluster.append(task)
    related_ids = {t['id']: min(x['id'] for x in g) for g in related if len(g)>1 for t in g}
    for task in live:
        task.pop('_identity_facts',None)
        task.pop('_separate_with',None)
    names = store.group_names()
    columns: dict[str, list] = {"homework": [], "other": [], "collection": []}
    counts = {"active": 0, "done": 0, "overdue": 0, "candidate": 0}
    for task in tasks:
        if task.get("status") in {"dismissed", "expired"}:
            continue
        body = str(task.get("source_text") or task.get("evidence") or task.get("summary") or "")
        homework = bool(task.get("homework_override")) if task.get("homework_override") is not None else is_homework(body)
        fields = event_fields(body)
        deadline = parse_iso(task.get("deadline"))
        done = task.get("status") == "done"
        labels = []
        for group in task.get("groups") or []:
            label = settings.group_aliases.get(str(group)) or names.get(str(group)) or (str(group) if not str(group).isdigit() else "来源群待确认")
            if label not in labels:
                labels.append(label)
        title = clean_title(str(task.get("summary") or body)) if homework else fields["event_name"]
        if homework:
            match = re.search(r"第[一二三四五六七八九十百\d]+次[^\n，。；]{0,15}(?:作业|报告)|(?:[^\n，。；]{0,18})(?:课后练习|实验报告|课程论文|课程报告|作业)", body)
            if match:
                title = match[0].strip(' ：:，,')
            if fields['naming_basis'] in {'notice_sentence','repeated_noun'}:
                title = fields['event_name']
        event_sort = None
        if not homework and fields["event_time"]:
            # Use the extraction helper to parse the labelled event date without treating it as a task deadline.
            event_sort = explicit_deadline(fields["event_time"] + " 截止", task.get("source_sent_at") or task.get("created_at"))
        item = {**task, **fields, "title": title, "body": body, "sent_at": task.get("source_sent_at") or "", "group_names": labels or ["手动添加"], "is_homework": homework, "priority": 5 if homework else int(task.get("importance") or 3), "priority_label": "最高优先级" if homework else "普通事项", "done": done, "overdue": bool(deadline and deadline < now and not done), "past_day": bool(deadline and deadline.date() < now.date() and not done), "favorite": bool(task.get("favorite") or task.get("pinned")), "highlight": bool(task.get("highlight")), "sort_time": event_sort or task.get("deadline") or ""}
        item['related_id'] = related_ids.get(task['id'])
        item['merged_sources'] = [{'id':t['id'],'sent_at':t.get('source_sent_at') or '', 'body':t.get('source_text') or t.get('evidence') or t.get('summary'), 'group_names':[settings.group_aliases.get(str(g)) or names.get(str(g)) or '来源群待确认' for g in t.get('groups',[])]} for t in tasks if t.get('duplicate_of')==task['id']]
        columns["homework" if homework else "other"].append(item)
        if item["favorite"] or item["highlight"]:
            columns["collection"].append(item)
        counts["done" if done else "active"] += 1
        counts["overdue"] += int(item["overdue"])
        counts["candidate"] += int(task.get("status") == "candidate")
    for values in columns.values():
        values.sort(key=lambda task: (task["done"], *sort_key(task, now)))
    return {"ok": True, "version": "personal-board-1", "columns": columns, "counts": counts, "generated_at": iso(now), "time_order": "当前与未来按时间升序；往日逾期单独折叠，最近逾期优先；无时间排最后"}


def mark(store: Any, data: dict[str, Any]) -> dict[str, Any]:
    task_id = data.get("task_id")
    field, value = data.get("field"), data.get("value")
    if type(task_id) is not int or task_id < 1 or field not in {"favorite", "highlight", "homework_override"}:
        raise ValueError("无效的事项或标记")
    if type(value) is not bool and not (field == "homework_override" and value is None):
        raise ValueError("标记值必须是 true 或 false")
    with store._connect() as connection:
        if not connection.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,)).fetchone():
            raise ValueError("事项不存在")
        connection.execute(f"UPDATE tasks SET {field}=?, updated_at=? WHERE id=?", (None if value is None else int(value), iso(now_local()), task_id))
        if field == "favorite":
            connection.execute("UPDATE tasks SET pinned=? WHERE id=?", (int(value), task_id))
        if field == "homework_override" and value is True:
            connection.execute("UPDATE tasks SET importance=5 WHERE id=?", (task_id,))
        store._task_event(connection, task_id, "board_mark", {"field": field, "value": value})
    return {"ok": True, "id": task_id, "field": field, "value": value}


def repair_store(store: Any) -> dict[str, int]:
    """One-time recovery of explicit homework notices dropped by old batch limits."""
    repair_deadline_order(store)
    from .event_identity import consolidate
    consolidate(store)
    if store.meta_get("personal_board_repair_v1", ""):
        return {"recovered": 0, "deadlines": 0}
    recovered = deadlines = 0
    with store._connect() as connection:
        messages = [dict(row) for row in connection.execute("SELECT * FROM messages ORDER BY ts")]
        rows = [dict(row) for row in connection.execute("SELECT * FROM tasks")]
        for row in rows:
            if is_homework(str(row.get("evidence") or row.get("summary") or "")) and row.get("homework_override") != 0:
                connection.execute("UPDATE tasks SET importance=5 WHERE id=?", (row["id"],))
    by_key = {row["task_key"]: row for row in rows}
    normalized = lambda value: re.sub(r"\s+", "", str(value or ""))
    for message in messages:
        text = message.get("source_text") or message["content"]
        due = explicit_deadline(text, message.get("ts"))
        if not (is_homework(text) and due and re.search(r"提交|上传|交作业|作业.{0,12}发布", text)):
            continue
        existing = by_key.get(message["msg_id"]) or by_key.get("inbox:" + message["msg_id"])
        if not existing:
            target = normalized(text)
            existing = next((row for row in rows if normalized(row.get("evidence")) == target and message["group_id"] in json.loads(row["groups"])), None)
        if existing:
            # Respect deliberate user corrections, including an intentionally cleared date.
            with store._connect() as connection:
                corrected = connection.execute("SELECT 1 FROM task_events WHERE task_id=? AND event='corrected' AND (detail LIKE '%clear_deadline%' OR detail LIKE '%\"type\": \"deadline\"%') LIMIT 1", (existing["id"],)).fetchone()
                if not existing["deadline"] and not corrected:
                    connection.execute("UPDATE tasks SET deadline=?, importance=5, updated_at=? WHERE id=?", (due, iso(now_local()), existing["id"]))
                    store._task_event(connection, existing["id"], "deadline_recovered", {"deadline": due, "source": message["msg_id"]})
                    deadlines += 1
            continue
        store.upsert_task(task_key=message["msg_id"], summary=clean_title(text), deadline=due, category="academic", importance=5, groups=[message["group_id"]], sender=message.get("sender_name", ""), evidence=text, source="qq_message", status="open", confidence=0.95, classification_reason="从原通知的明确作业截止时间补回")
        recovered += 1
    duplicates = 0
    # Old manual promotion used a different task key for the very same message.
    # Merge only pairs that are both still open; preserve any differing user state.
    with store._connect() as connection:
        pairs = connection.execute("SELECT a.id AS first_id,b.id AS second_id FROM tasks a JOIN tasks b ON a.task_key='inbox:'||b.task_key WHERE a.status='open' AND b.status='open'").fetchall()
    for pair in pairs:
        first, second = store.get_task(pair["first_id"]), store.get_task(pair["second_id"])
        with store._connect() as connection:
            connection.execute("UPDATE tasks SET deadline=CASE WHEN deadline='' THEN ? ELSE deadline END, importance=MAX(importance,?), favorite=MAX(favorite,?), highlight=MAX(highlight,?), pinned=MAX(pinned,?) WHERE id=?", (second.get("deadline", ""), second.get("importance", 3), int(second.get("favorite", 0)), int(second.get("highlight", 0)), int(second.get("pinned", 0)), first["id"]))
        store.apply_task_correction(second["id"], "duplicate", value=str(first["id"]))
        duplicates += 1
    store.meta_set("personal_board_repair_v1", iso(now_local()))
    return {"recovered": recovered, "deadlines": deadlines, "duplicates": duplicates}


def html() -> str:
    return Path(__file__).with_name("board.html").read_text(encoding="utf-8")


def repair_deadline_order(store: Any) -> None:
    if store.meta_get("deadline_order_v1", ""):
        return
    for task in store.list_tasks():
        text = "\n".join(str(task.get(k) or "") for k in ("summary", "source_text", "evidence"))
        due, issue = checked_deadline(task.get("deadline"), task.get("source_sent_at"), text)
        if due == (task.get("deadline") or ""):
            continue
        with store._connect() as connection:
            connection.execute("UPDATE tasks SET deadline=?,deadline_issue=?,updated_at=? WHERE id=?", (due, issue, iso(now_local()), task["id"]))
            store._task_event(connection, task["id"], "deadline_order_repaired", {"previous": task.get("deadline"), "deadline": due, "issue": issue})
    store.meta_set("deadline_order_v1", iso(now_local()))
