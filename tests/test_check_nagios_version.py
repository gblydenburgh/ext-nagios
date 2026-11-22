"""Small offline tests for the Nagios version comparison rules."""

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check-nagios-version.py"
SPEC = importlib.util.spec_from_file_location("check_nagios_version", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VersionCheckTests(unittest.TestCase):
    """Check current, old, newer, and invalid version values."""

    def test_current_version_is_ok(self):
        status, message = MODULE.result_for_versions("4.5.14", "nagios-4.5.14")
        self.assertEqual(status, 0)
        self.assertIn("latest stable release", message)

    def test_old_version_is_warning(self):
        status, message = MODULE.result_for_versions("4.5.9", "nagios-4.5.14")
        self.assertEqual(status, 1)
        self.assertIn("installed 4.5.9", message)
        self.assertIn("latest stable is 4.5.14", message)

    def test_newer_version_is_ok(self):
        status, message = MODULE.result_for_versions("4.6.0", "nagios-4.5.14")
        self.assertEqual(status, 0)
        self.assertIn("newer than", message)

    def test_invalid_version_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.parse_version("release-candidate")


if __name__ == "__main__":
    unittest.main()
