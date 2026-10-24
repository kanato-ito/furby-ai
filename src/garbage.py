"""ごみの収集日

設定ページで 1 行に 1 種類ずつ書く。曜日の前に「第2」などを付けると、その月の第何週だけになる。
    燃えるごみ: 月 木
    資源ごみ: 水
    不燃ごみ: 第2 第4 金
"""
import re
from dataclasses import dataclass
from datetime import date

WEEKDAYS = '月火水木金土日'


@dataclass(frozen=True)
class GarbageRule:
    name: str
    weekdays: frozenset  # 0 = 月曜
    weeks: frozenset     # 空なら毎週。1〜5 = その月の第何週


def parse_garbage(text: str) -> list[GarbageRule]:
    """書き方がおかしい行があれば ValueError（設定ページにそのまま表示する）"""
    rules = []
    for n, line in enumerate((text or '').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^(.+?)\s*[:：]\s*(.+)$', line)
        if not m:
            raise ValueError(f"ごみの日 {n} 行目: 「燃えるごみ: 月 木」の形で書いてください")
        name, days = m.groups()
        weeks = frozenset(int(w) for w in re.findall(r'第\s*(\d)', days))
        if any(not 1 <= w <= 5 for w in weeks):
            raise ValueError(f"ごみの日 {n} 行目: 第1〜第5 で書いてください")
        days = re.sub(r'第\s*\d|曜日?', '', days)  # 「水曜日」の「日」を日曜と読まないように
        if '毎日' in days:
            days = WEEKDAYS
        weekdays = frozenset(WEEKDAYS.index(c) for c in days if c in WEEKDAYS)
        if not weekdays:
            raise ValueError(f"ごみの日 {n} 行目: 曜日（月火水木金土日）がありません")
        rules.append(GarbageRule(name, weekdays, weeks))
    return rules


def garbage_on(rules: list[GarbageRule], day: date) -> list[str]:
    week = (day.day - 1) // 7 + 1  # 第何週（その月の何回目のこの曜日か）
    return [
        r.name for r in rules
        if day.weekday() in r.weekdays and (not r.weeks or week in r.weeks)
    ]
