"""Regression checks for access-control state transitions."""

import unittest
from unittest.mock import MagicMock, patch

import access_control


class AccessControlTests(unittest.TestCase):
    def test_deactivated_user_stays_blocked_in_public_mode(self):
        with patch.object(access_control, "refresh_cache_if_needed"), patch.dict(
            access_control._ROLES_CACHE,
            {42: {"role": "user", "is_active": False, "lang": "km", "admin_lang": "en"}},
            clear=True,
        ), patch.dict(access_control._SETTINGS_CACHE, {"access_mode": "public"}, clear=True):
            self.assertFalse(access_control.is_allowed_access(42))

    def _rate_limit_connection(self, returned):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = returned
        return connection

    def test_persistent_rate_limit_allows_request_and_reports_remaining_quota(self):
        connection = self._rate_limit_connection((1, 1))
        with patch.object(access_control, "get_db_connection", return_value=connection):
            result = access_control.check_user_rate_limit(1001, max_per_minute=5, max_per_day=30)

        self.assertEqual(result, (True, "", 1, 29))
        connection.commit.assert_called_once()
        sql = connection.cursor.return_value.execute.call_args.args[0]
        self.assertIn("ON CONFLICT (telegram_id) DO UPDATE", sql)

    def test_persistent_rate_limit_rejects_minute_limit(self):
        connection = self._rate_limit_connection((6, 6))
        with patch.object(access_control, "get_db_connection", return_value=connection):
            result = access_control.check_user_rate_limit(1002, max_per_minute=5, max_per_day=30)

        self.assertEqual(result, (False, "minute_limit", 6, 24))

    def test_persistent_rate_limit_rejects_daily_limit(self):
        connection = self._rate_limit_connection((1, 31))
        with patch.object(access_control, "get_db_connection", return_value=connection):
            result = access_control.check_user_rate_limit(1003, max_per_minute=5, max_per_day=30)

        self.assertEqual(result, (False, "daily_limit", 31, 0))

    def test_persistent_rate_limit_fails_closed_when_database_is_unavailable(self):
        with patch.object(
            access_control,
            "get_db_connection",
            side_effect=access_control.psycopg2.OperationalError("database unavailable"),
        ):
            result = access_control.check_user_rate_limit(1004)

        self.assertEqual(result, (False, "rate_limit_unavailable", 0, 0))


if __name__ == "__main__":
    unittest.main()
