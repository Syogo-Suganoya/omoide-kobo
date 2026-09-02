from __future__ import annotations


def add_minutes(time_str: str, minutes: int) -> str:
    """"HH:MM" に分を足す。日跨ぎは 24 時間で丸める（旅程は日帰り前提）。"""
    hour, minute = (int(x) for x in time_str.split(":"))
    total = hour * 60 + minute + minutes
    return f"{total // 60 % 24:02d}:{total % 60:02d}"


def diff_minutes(start: str, end: str) -> int:
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    return (eh * 60 + em) - (sh * 60 + sm)
