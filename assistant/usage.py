"""Thread-safe, process-wide hourly API allowance for the portfolio demo.

Reservations cover up to four requests before a question starts. Unused slots
are returned only after known completion; unexpected failures consume the full
reservation. This allowance resets on process restart; it is not a billing cap.
"""
from dataclasses import dataclass
import hmac
import threading
import time


def valid_access_code(candidate, expected):
    return bool(expected and len(expected) >= 12) and hmac.compare_digest(
        str(candidate).encode(), expected.encode())


class BudgetExhausted(Exception):
    pass


@dataclass(frozen=True)
class Reservation:
    identity: int
    bucket: int
    slots: int


class ProcessBudget:
    def __init__(self, limit=30, clock=time.time):
        self.limit, self.clock = limit, clock
        self._lock = threading.Lock()
        self._bucket, self._used, self._sequence = -1, 0, 0
        self._leases = {}

    def reserve(self, requested=4):
        with self._lock:
            bucket = int(self.clock() // 3600)
            if bucket != self._bucket:
                self._bucket, self._used = bucket, 0
                self._leases.clear()
            slots = min(max(0, requested), self.limit - self._used)
            if not slots:
                raise BudgetExhausted('The shared demo API allowance is used for this hour. Query Explorer remains available.')
            self._used += slots
            self._sequence += 1
            lease = Reservation(self._sequence, bucket, slots)
            self._leases[lease.identity] = lease
            return lease

    def settle(self, lease, actual):
        with self._lock:
            if self._leases.pop(lease.identity, None) != lease or lease.bucket != self._bucket:
                return
            # Invalid/unknown request counts do not refund reserved capacity.
            if isinstance(actual, int) and not isinstance(actual, bool) and 0 <= actual <= lease.slots:
                self._used -= lease.slots - actual
