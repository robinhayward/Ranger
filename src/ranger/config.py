from dataclasses import dataclass
from pathlib import Path
import tomllib


class ConfigError(ValueError):
    """Configuration cannot be used by Ranger."""


@dataclass(frozen=True)
class Config:
    repositories: tuple[str, ...]
    label: str = "agent-ready"
    host: str = "github.com"

    def __post_init__(self) -> None:
        if not self.repositories:
            raise ConfigError(
                "github.repositories must contain at least one repository"
            )
        for repository in self.repositories:
            _validate_repository(repository)
        if not isinstance(self.label, str) or not self.label.strip():
            raise ConfigError("github.label must be a non-empty string")
        if (
            not isinstance(self.host, str)
            or not self.host
            or not self.host[0].isalnum()
            or not self.host[-1].isalnum()
            or ".." in self.host
            or any(
                not (character.isalnum() or character in ".-")
                for character in self.host
            )
        ):
            raise ConfigError("github.host must be a hostname without a scheme")


def load_config(path: Path) -> Config:
    try:
        with path.open("rb") as config_file:
            data = tomllib.load(config_file)
    except FileNotFoundError as error:
        raise ConfigError(f"Configuration not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"Invalid TOML in {path}: {error}") from error

    github = data.get("github")
    if not isinstance(github, dict):
        raise ConfigError("Configuration must contain a [github] table")

    repositories = github.get("repositories")
    if not isinstance(repositories, list):
        raise ConfigError("github.repositories must be a list")

    return Config(
        repositories=tuple(repositories),
        label=github.get("label", "agent-ready"),
        host=github.get("host", "github.com"),
    )


def _validate_repository(repository: object) -> None:
    if (
        not isinstance(repository, str)
        or len(repository.split("/")) != 2
        or any(not part for part in repository.split("/"))
        or any(character.isspace() for character in repository)
    ):
        raise ConfigError(
            f"Repository must use OWNER/NAME format: {repository!r}"
        )
