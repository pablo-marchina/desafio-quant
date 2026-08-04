import time

_last_call: float = 0.0
_MIN_INTERVAL = 6.5  # safe under 10 calls/min Trial limit


def cohere_wait():
    global _last_call
    now = time.time()
    elapsed = now - _last_call
    if elapsed < _MIN_INTERVAL:
        sleep_time = _MIN_INTERVAL - elapsed
        time.sleep(sleep_time)
    _last_call = time.time()
