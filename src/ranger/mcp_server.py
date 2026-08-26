from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__
from .config import ConfigError, resolve_config
from .discovery import ClientFactory, DiscoveryDocument, discover, document
from .github import GitHubClient, GitHubError


INSTRUCTIONS = (
    "Ranger discovers GitHub issues for coding agents. This Ranger release is "
    "read-only: it never claims issues or changes repositories. Use list_issues "
    "to find open issues with the configured label."
)


def create_server(
    client_factory: ClientFactory = GitHubClient,
) -> MCPServer:
    server = MCPServer(
        "ranger",
        title="Ranger",
        description="Read-only GitHub issue discovery for coding agents.",
        instructions=INSTRUCTIONS,
        version=__version__,
    )

    @server.tool(
        title="List agent-ready GitHub issues",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def list_issues(
        repositories: list[str] | None = None,
        label: str | None = None,
        host: str | None = None,
        config_path: str | None = None,
    ) -> DiscoveryDocument:
        """List open GitHub issues carrying Ranger's ready label."""
        try:
            config = resolve_config(
                config_path=None if config_path is None else Path(config_path),
                repositories=repositories,
                label=label,
                host=host,
            )
            return document(config.label, discover(config, client_factory))
        except (ConfigError, GitHubError) as error:
            raise ToolError(str(error)) from error

    return server


mcp = create_server()


def main() -> None:
    mcp.run()
