"""Small retry helper — exponential backoff for transient catalog/COG failures.

Deliberately not tenacity: three lines of logic, one less dependency.
"""

import time
from collections.abc import Callable


def with_retry[T](fn: Callable[[], T], *, attempts: int = 3, base_delay_s: float = 0.5) -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if i < attempts - 1:
                time.sleep(base_delay_s * 2**i)
    assert last is not None
    raise last
