from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ranger.config import ConfigError, load_config


class LoadConfigTests(unittest.TestCase):
    def test_loads_repositories_and_defaults(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '[github]\nrepositories = ["acme/api", "acme/web"]\n',
                encoding="utf-8",
            )

            config = load_config(path)

        self.assertEqual(config.repositories, ("acme/api", "acme/web"))
        self.assertEqual(config.label, "agent-ready")
        self.assertEqual(config.host, "github.com")

    def test_rejects_an_empty_repository_list(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text("[github]\nrepositories = []\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ConfigError, "github.repositories must contain at least one repository"
            ):
                load_config(path)

    def test_reports_a_missing_file(self) -> None:
        path = Path("/missing/ranger/config.toml")

        with self.assertRaisesRegex(ConfigError, "Configuration not found"):
            load_config(path)

    def test_rejects_a_malformed_repository(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '[github]\nrepositories = ["not a repository"]\n', encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ConfigError, "Repository must use OWNER/NAME format"
            ):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
