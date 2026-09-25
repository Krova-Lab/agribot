"""Unit tests for the future public bot onboarding contract."""

import unittest
from unittest.mock import patch

from config.prod_database import get_prod_db_params
from prod_onboarding import ProductionUser, infer_language, settings_message, welcome_message


class ProductionOnboardingTests(unittest.TestCase):
    def test_language_hint_is_normalized_with_khmer_default(self):
        self.assertEqual(infer_language("fr-FR"), "fr")
        self.assertEqual(infer_language("en-US"), "en")
        self.assertEqual(infer_language("km"), "km")
        self.assertEqual(infer_language("de"), "km")
        self.assertEqual(infer_language(None), "km")

    def test_welcome_explains_waitlist_and_optional_settings(self):
        message = welcome_message("en", 12)
        self.assertIn("wait-list", message)
        self.assertIn("12", message)
        self.assertIn("optional", message)

    def test_settings_escapes_user_location(self):
        user = ProductionUser(1, "waitlist", "en", "<script>", None, None, "complete", 1)
        message = settings_message(user)
        self.assertNotIn("<script>", message)
        self.assertIn("&lt;script&gt;", message)

    def test_production_database_does_not_fall_back_to_pilot_settings(self):
        with patch.dict("os.environ", {
            "PROD_DB_NAME": "krova_prod",
            "PROD_DB_USER": "prod_user",
            "PROD_DB_PASSWORD": "prod_password",
            "DB_NAME": "pilot_db",
            "DB_USER": "pilot_user",
            "DB_PASSWORD": "pilot_password",
        }, clear=False):
            params = get_prod_db_params()
        self.assertEqual(params["dbname"], "krova_prod")
        self.assertEqual(params["user"], "prod_user")
        self.assertEqual(params["password"], "prod_password")


if __name__ == "__main__":
    unittest.main()
