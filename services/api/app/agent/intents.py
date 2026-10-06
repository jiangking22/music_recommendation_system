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
        r"(?:适合)?(emo|伤感|难过|缓慢|慢节奏|舒缓|安静|放松|学习|专注|爵士|摇滚)"
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
    return bool(re.fullmatch(r"(?:再来(?:几首|一些|点|一首)?(?:歌)?|more(?: songs| like this)?)"
                             r"[。！!?？.]*", message.casefold().strip()))
