"""Regression checks for Khmer (km), French, and English UI language detection."""

import unittest

from language_detection import detect_ui_lang


class LanguageDetectionTests(unittest.TestCase):
    def test_common_unaccented_french_question_is_detected(self):
        self.assertEqual(detect_ui_lang("Je peux traiter mes tomates ?"), "fr")

    def test_english_question_is_detected(self):
        self.assertEqual(detect_ui_lang("What should I do for my tomatoes?"), "en")

    def test_khmer_script_is_detected(self):
        self.assertEqual(detect_ui_lang("ស្រូវនៅកំពត"), "km")

    def test_empty_input_defaults_to_khmer(self):
        self.assertEqual(detect_ui_lang(""), "km")


if __name__ == "__main__":
    unittest.main()
