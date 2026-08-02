# Connect an AI client with MCP

Focus includes a local stdio MCP server with eleven tools for reading context, creating and updating projects/tasks, controlling the timer, completing tasks, and managing uninterrupted-focus rewards.

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

Reward tools can read progress, create a custom target, select it, and redeem an
earned copy. MCP cannot start or stop a camera; FocusFloat keeps that permission
and its visible indicator local. See [REWARDS.md](REWARDS.md).
