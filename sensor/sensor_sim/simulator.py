import itertools
import logging
import time
from typing import Callable

from .data_source import Measurement
from .message import build_message
from .publishers import PermanentError, Publisher, TransientError

log = logging.getLogger(__name__)


class Simulator:
    def __init__(self, measurements: list[Measurement], publisher: Publisher, interval: float,
                 max_retries: int = 5, retry_base_delay: float = 1.0,
                 sleep: Callable[[float], None] = time.sleep):
        if not measurements:
            raise ValueError("Inga mätvärden att simulera")
        self._cycle = itertools.cycle(measurements)
        self.publisher, self.interval = publisher, interval
        self.max_retries, self.retry_base_delay, self._sleep = max_retries, retry_base_delay, sleep

    def send_with_retry(self, message: dict) -> bool:
        """Skickar med exponentiell backoff. Returnerar True om leverans lyckades."""
        for attempt in range(1, self.max_retries + 1):
            try:
                self.publisher.send(message)
                return True
            except PermanentError as exc:
                log.error("Avvisad (ingen retry): %s", exc)
                return False
            except TransientError as exc:
                log.warning("Försök %d/%d misslyckades: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    self._sleep(self.retry_base_delay * 2 ** (attempt - 1))
        log.error("Gav upp efter %d försök - datapunkt förlorad: %s", self.max_retries, message)
        return False

    def tick(self) -> bool:
        message = build_message(next(self._cycle))
        ok = self.send_with_retry(message)
        if ok:
            log.info("Skickade %s = %s (%s)", message["sensor_id"], message["value"], message["timestamp"])
        return ok

    def run(self, count: int | None = None) -> int:
        """Kör tills count nåtts (eller för alltid). Returnerar antal lyckade sändningar."""
        sent, n = 0, 0
        while count is None or n < count:
            sent += self.tick()
            n += 1
            if count is None or n < count:
                self._sleep(self.interval)
        return sent
