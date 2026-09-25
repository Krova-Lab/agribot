import unittest
from datetime import datetime, timedelta, timezone

from response_preferences import DetailSignal, infer_detail_preference, user_requests_more_detail


class ResponsePreferenceTests(unittest.TestCase):
    def test_only_explicit_detail_requests_are_signals(self):
        self.assertTrue(user_requests_more_detail("Please give me more details."))
        self.assertTrue(user_requests_more_detail("Peux-tu développer ?"))
        self.assertFalse(user_requests_more_detail("What are the sources?"))

    def test_repeated_recent_requests_infer_detailed_preference(self):
        now = datetime.now(timezone.utc)
        signals = [
            DetailSignal(index < 3, now - timedelta(days=index))
            for index in range(10)
        ]
        self.assertEqual(infer_detail_preference(signals)[0], "detailed")

    def test_sparse_or_insufficient_requests_do_not_infer_preference(self):
        now = datetime.now(timezone.utc)
        signals = [
            DetailSignal(index < 2, now - timedelta(days=index))
            for index in range(10)
        ]
        self.assertIsNone(infer_detail_preference(signals))
        self.assertIsNone(infer_detail_preference(signals[:4]))


if __name__ == "__main__":
    unittest.main()
