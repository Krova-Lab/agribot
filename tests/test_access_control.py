"""Regression checks for access-control state transitions."""

import unittest
from unittest.mock import patch

import access_control


class AccessControlTests(unittest.TestCase):
    def test_deactivated_user_stays_blocked_in_public_mode(self):
        with patch.object(access_control, "refresh_cache_if_needed"), patch.dict(
            access_control._ROLES_CACHE,
            {42: {"role": "user", "is_active": False, "lang": "km", "admin_lang": "en"}},
            clear=True,
        ), patch.dict(access_control._SETTINGS_CACHE, {"access_mode": "public"}, clear=True):
            self.assertFalse(access_control.is_allowed_access(42))


if __name__ == "__main__":
    unittest.main()
