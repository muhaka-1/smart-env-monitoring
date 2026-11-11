import unittest
from datetime import datetime, timezone
from collections import Counter
from unittest.mock import MagicMock

import requests

from sensor_sim.config import Config
from sensor_sim.data_source import Measurement, load_measurements
from sensor_sim.message import build_message
from sensor_sim.publishers import HttpPublisher, PermanentError, Publisher, TransientError
from sensor_sim.simulator import Simulator

M = [Measurement("s1", "turbidity", 1.0, "good", "NTU"), Measurement("s2", "temperature", 2.0, "good", "°C")]


class FakePublisher(Publisher):
    def __init__(self, errors=()):
        self.errors, self.sent = list(errors), []

    def send(self, message):
        if self.errors:
            raise self.errors.pop(0)
        self.sent.append(message)


class MessageTests(unittest.TestCase):
    def test_contains_required_fields(self):
        msg = build_message(M[0])
        self.assertEqual(set(msg), {"sensor_id", "metric", "timestamp", "value", "unit", "quality"})


class SimulatorTests(unittest.TestCase):
    def sim(self, pub, **kw):
        return Simulator(M, pub, interval=0, sleep=lambda s: None, **kw)

    def test_sends_requested_count_cycling(self):
        pub = FakePublisher()
        self.assertEqual(self.sim(pub).run(count=3), 3)
        self.assertEqual([m["sensor_id"] for m in pub.sent], ["s1", "s2", "s1"])

    def test_six_sensors_keep_values_and_current_send_times(self):
        items = load_measurements(Config(), offline=True)
        pub = FakePublisher()
        sleeps = []
        started = datetime.now(timezone.utc)
        Simulator(items, pub, interval=5, sleep=sleeps.append).run(count=12)
        ended = datetime.now(timezone.utc)
        self.assertEqual(set(Counter(m["sensor_id"] for m in pub.sent).values()), {2})
        self.assertEqual(len({m["sensor_id"] for m in pub.sent}), 6)
        self.assertEqual(sleeps, [5] * 11)
        for source, message in zip(items, pub.sent):
            self.assertEqual((message["sensor_id"], message["value"], message["unit"]),
                             (source.sensor_id, source.value, source.unit))
            self.assertTrue(started <= datetime.fromisoformat(message["timestamp"]) <= ended)

    def test_retries_transient_then_succeeds(self):
        pub = FakePublisher([TransientError("x"), TransientError("y")])
        self.assertTrue(self.sim(pub, max_retries=5).tick())
        self.assertEqual(len(pub.sent), 1)

    def test_gives_up_after_max_retries(self):
        pub = FakePublisher([TransientError("x")] * 3)
        self.assertFalse(self.sim(pub, max_retries=3).tick())

    def test_permanent_error_not_retried(self):
        pub = FakePublisher([PermanentError("bad"), TransientError("never reached")])
        self.assertFalse(self.sim(pub).tick())
        self.assertEqual(len(pub.errors), 1)


class HttpPublisherTests(unittest.TestCase):
    def pub(self, response=None, exc=None):
        session = MagicMock(headers={})
        if exc:
            session.post.side_effect = exc
        else:
            session.post.return_value = MagicMock(status_code=response, text="")
        return HttpPublisher(Config(), session)

    def test_status_mapping(self):
        self.pub(201).send({})
        with self.assertRaises(PermanentError):
            self.pub(400).send({})
        with self.assertRaises(TransientError):
            self.pub(503).send({})
        with self.assertRaises(TransientError):
            self.pub(exc=requests.ConnectionError("down")).send({})
