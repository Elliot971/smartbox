from datetime import datetime
from zoneinfo import ZoneInfo


CN_TZ = ZoneInfo("Asia/Shanghai")


def now_cn() -> datetime:
    """Return the current time in Asia/Shanghai as a naive datetime.

    The project stores naive datetimes in MySQL to stay consistent with the
    board firmware, which sends local (CST) timestamps without timezone info.
    """
    return datetime.now(CN_TZ).replace(tzinfo=None)
