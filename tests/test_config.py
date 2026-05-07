import importlib
import os
import unittest
from unittest.mock import patch

import src.config as config


class ConfigTest(unittest.TestCase):
    def test_require_login_config_reports_missing_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            reloaded = importlib.reload(config)
            with self.assertRaisesRegex(RuntimeError, "MEDREC_USERNAME"):
                reloaded.require_login_config()

    def test_require_login_config_accepts_username_and_password(self):
        with patch.dict(os.environ, {"MEDREC_USERNAME": "u", "MEDREC_PASSWORD": "p"}, clear=True):
            reloaded = importlib.reload(config)
            reloaded.require_login_config()


if __name__ == "__main__":
    unittest.main()
