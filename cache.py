import time

CACHE = {}

CACHE_TIME = 60 * 60 * 2  # ساعتان


def get(key):
    if key not in CACHE:
        return None

    value, created = CACHE[key]

    if time.time() - created > CACHE_TIME:
        del CACHE[key]
        return None

    return value


def set(key, value):
    CACHE[key] = (value, time.time())
