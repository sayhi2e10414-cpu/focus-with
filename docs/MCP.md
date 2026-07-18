# Connect an AI client with MCP

Focus includes a local stdio MCP server with seven tools for reading context, creating and updating projects/tasks, controlling the timer, and completing tasks.

Run it through the wrapper:

```bash
/absolute/path/to/focus-with/scripts/focus-mcp
```

In any MCP client, add a stdio server named `focus` whose command is that absolute wrapper path. No API key is passed to the model or MCP client because the server reads the same local database directly.

Example configuration shape:

```json
{
  "mcpServers": {
    "focus": {
      "command": "/absolute/path/to/focus-with/scripts/focus-mcp"
    }
  }
}
```

This local connector works with desktop and command-line MCP clients. Claude.ai's connector originates from Anthropic's cloud, so it cannot reach this local stdio server. To use Claude.ai, deploy the built-in authenticated HTTPS connector described in [REMOTE_MCP.md](REMOTE_MCP.md). FocusWith never publishes an unauthenticated write-capable MCP endpoint.
