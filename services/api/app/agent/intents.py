"""Narrow offline listening phrases; never infer a theme from a quoted song title."""

import re


def quoted_song(message: str) -> str | None:
    match = re.fullmatch(
        r'(?:请)?(?:推荐(?:与)?|播放|我想听|想听)?(?:《([^》]{1,120})》|"([^"\n]{1,120})")'
        r"(?:类似的歌)?[。！!?？.]*", message.strip())
    return (match[1] or match[2]).strip() if match else None


def theme_seed(message: str) -> str | None:
    text = message.casefold().strip().rstrip("。！!?？.")
    chinese = re.fullmatch(
        r"(?:请)?(?:(?:给我|帮我)?(?:推荐|来|找)(?:一些|几首|点)?|我想听|想听)?"
        r"(?:适合)?(?:(?:曲风|节奏|风格|旋律)(?:要|是|比较|偏)?)?"
        r"(emo|伤感|难过|缓慢|慢节奏|舒缓|安静|放松|学习|专注|爵士|摇滚)"
        r"(?:的)?(?:歌曲|音乐|歌)?(?:吧)?", text)
    if chinese:
        return {"emo": "emo", "伤感": "sad", "难过": "sad", "缓慢": "calm",
                "慢节奏": "calm", "舒缓": "calm", "安静": "calm", "放松": "calm",
                "学习": "calm jazz", "专注": "calm jazz", "爵士": "jazz",
                "摇滚": "rock"}[chinese[1]]
    english = re.fullmatch(
        r"(?:please )?(?:(?:recommend|play)(?: some)? )?"
        r"(emo|sad|slow|calm|calm jazz|relaxing|study|focus|jazz|rock)"
        r"(?: (?:songs|music|playlist))?", text)
    if english:
        return {"slow": "calm", "relaxing": "calm", "study": "calm jazz",
                "focus": "calm jazz"}.get(english[1], english[1])
    return None


def is_followup(message: str) -> bool:
    return bool(re.fullmatch(r"(?:再来(?:几首|一些|点|一首|[0-9一二两三四五六七八九十]+首)?(?:歌)?|more(?: songs| like this)?)"
                             r"[。！!?？.]*", message.casefold().strip()))


def requested_count(message: str, default: int = 5) -> int:
    match = re.search(r'([0-9]{1,3}|[一二两三四五六七八九十])\s*首|\b([0-9]{1,3})\s+songs\b', message)
    if not match:
        return default
    value = match[1] or match[2]
    number = int(value) if value.isdecimal() else '一二三四五六七八九十'.find(value) + 1 if value != '两' else 2
    return max(1, min(number, 10))


def preference_updates(message: str) -> dict:
    """A narrow fallback for common refinements; the model handles richer sentences."""
    text = message.casefold().strip().rstrip("。！!?？.")
    updates = {}
    if re.fullmatch(r"(?:不要|不想要|别来|不听)纯音乐|(?:要|想要|只要|带|偏)(?:点|些)?人声(?:的|一点)?", text):
        updates["vocals"] = "vocal"
    elif re.fullmatch(r"(?:只要|想要|要|偏)?纯音乐(?:的|一点)?", text):
        updates["vocals"] = "instrumental"
    if re.fullmatch(r"(?:偏|要|想要|换成|只要)?(?:华语|中文|国语)(?:的|歌|音乐|一点|些)?", text):
        updates["language"] = "zh"
    elif re.fullmatch(r"(?:偏|要|想要|换成|只要)?(?:英语|英文)(?:的|歌|音乐|一点|些)?", text):
        updates["language"] = "en"
    return updates


def is_discussion(message: str) -> bool:
    return any(word in message.casefold() for word in (
        "为什么", "为何", "解释", "区别", "聊聊", "先不推荐", "不推荐", "说不上来", "有点累",
        "why", "explain", "difference", "let's talk"))
