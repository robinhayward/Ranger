from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ranger.config import ConfigError, load_config, resolve_config


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

    def test_rejects_a_host_with_a_url_scheme(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '[github]\nrepositories = ["acme/api"]\n'
                'host = "https://github.example.com"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ConfigError, "github.host must be a hostname without a scheme"
            ):
                load_config(path)

    def test_resolves_explicit_repository_without_a_config_file(self) -> None:
        config = resolve_config(
            repositories=["acme/api"],
            label="ready-for-agent",
            host="github.example.com",
            default_path=Path("/missing/ranger/config.toml"),
        )

        self.assertEqual(config.repositories, ("acme/api",))
        self.assertEqual(config.label, "ready-for-agent")
        self.assertEqual(config.host, "github.example.com")

    def test_rejects_an_explicit_empty_repository_list(self) -> None:
        with self.assertRaisesRegex(ConfigError, "at least one repository"):
            resolve_config(
                repositories=[],
                default_path=Path("/missing/ranger/config.toml"),
            )

    def test_explicit_values_override_a_selected_config(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '[github]\nrepositories = ["configured/api"]\n'
                'label = "configured"\nhost = "github.com"\n',
                encoding="utf-8",
            )

            config = resolve_config(
                config_path=path,
                repositories=["override/web"],
                label="agent-ready",
                host="github.example.com",
            )

        self.assertEqual(config.repositories, ("override/web",))
        self.assertEqual(config.label, "agent-ready")
        self.assertEqual(config.host, "github.example.com")


if __name__ == "__main__":
    unittest.main()
