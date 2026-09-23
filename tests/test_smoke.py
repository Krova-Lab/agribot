"""Fast, dependency-light regression checks for the public repository."""

import unittest

from config.prompt_loader import load_prompts, render_prompt


class PromptSmokeTests(unittest.TestCase):
    def test_public_prompts_are_loadable(self):
        prompts = load_prompts()
        self.assertIn("system_prompt", prompts)
        self.assertTrue(prompts["system_prompt"])

    def test_render_prompt_replaces_named_values(self):
        self.assertEqual(render_prompt("Hello {name}", name="Krova"), "Hello Krova")

if __name__ == "__main__":
    unittest.main()
