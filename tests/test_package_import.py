"""Package scaffold tests."""

from pathlib import Path
import importlib
import sys
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_pyproject():
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


class PackageImportTests(unittest.TestCase):
    def test_tests_run_on_python_311_or_newer(self):
        self.assertGreaterEqual(sys.version_info, (3, 11))

    def test_package_imports(self):
        package = importlib.import_module("authority_workspace")
        self.assertEqual(package.__name__, "authority_workspace")

    def test_version_exists(self):
        package = importlib.import_module("authority_workspace")
        self.assertTrue(hasattr(package, "__version__"))
        self.assertIsInstance(package.__version__, str)
        self.assertTrue(package.__version__)

    def test_pyproject_declares_python_311_plus(self):
        pyproject = load_pyproject()

        self.assertEqual(pyproject["project"]["requires-python"], ">=3.11")

    def test_pyproject_has_no_runtime_dependencies(self):
        pyproject = load_pyproject()

        self.assertEqual(pyproject["project"]["dependencies"], [])

    def test_package_version_matches_pyproject(self):
        package = importlib.import_module("authority_workspace")
        pyproject = load_pyproject()

        self.assertEqual(package.__version__, pyproject["project"]["version"])


if __name__ == "__main__":
    unittest.main()
