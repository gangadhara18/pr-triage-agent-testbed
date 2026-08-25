import time


def retry(func, max_attempts=3, delay=1):
    """
    Retries a function call if it raises an exception, up to max_attempts times,
    waiting `delay` seconds between attempts.
    """
    attempts = 0
    while attempts < max_attempts:
        try:
            return func()
        except Exception as e:
            attempts += 1
            if attempts == max_attempts:
                raise e
            time.sleep(delay)
