import unittest
from unittest.mock import MagicMock

import requests

from sensor_sim.config import Config
from sensor_sim.data_source import Measurement
from sensor_sim.message import build_message
from sensor_sim.publishers import HttpPublisher, PermanentError, Publisher, TransientError
from sensor_sim.simulator import Simulator

M = [Measurement("s1", 1.0, "good"), Measurement("s2", 2.0, "good")]


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
        self.assertEqual(set(msg), {"sensor_id", "timestamp", "value", "unit", "quality"})


class SimulatorTests(unittest.TestCase):
    def sim(self, pub, **kw):
        return Simulator(M, pub, interval=0, sleep=lambda s: None, **kw)

    def test_sends_requested_count_cycling(self):
        pub = FakePublisher()
        self.assertEqual(self.sim(pub).run(count=3), 3)
        self.assertEqual([m["sensor_id"] for m in pub.sent], ["s1", "s2", "s1"])

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
