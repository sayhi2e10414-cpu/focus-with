# AI providers and chat clients

FocusWith keeps the model layer replaceable. The built-in Companion calls a provider from the server, while existing chat products connect through MCP. Provider keys stay in the ignored `.env` file and are never returned to browser JavaScript.

## Built-in Companion

Choose one provider shape, set a model that supports function/tool calling, and restart FocusWith.

### OpenAI Responses API

```dotenv
FOCUS_AI_PROVIDER=openai-responses
FOCUS_AI_API_KEY=your-openai-api-key
FOCUS_AI_MODEL=your-tool-capable-model
FOCUS_AI_BASE_URL=https://api.openai.com/v1
```

### Anthropic Messages API

```dotenv
FOCUS_AI_PROVIDER=anthropic
FOCUS_AI_API_KEY=your-anthropic-api-key
FOCUS_AI_MODEL=your-tool-capable-model
FOCUS_AI_BASE_URL=https://api.anthropic.com
```

### DeepSeek

```dotenv
FOCUS_AI_PROVIDER=openai-compatible
FOCUS_AI_API_KEY=your-deepseek-api-key
FOCUS_AI_MODEL=your-current-tool-capable-deepseek-model
FOCUS_AI_BASE_URL=https://api.deepseek.com
```

### GLM / Zhipu

```dotenv
FOCUS_AI_PROVIDER=openai-compatible
FOCUS_AI_API_KEY=your-zhipu-api-key
FOCUS_AI_MODEL=your-current-tool-capable-glm-model
FOCUS_AI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

### Ollama or another local endpoint

```dotenv
FOCUS_AI_PROVIDER=openai-compatible
FOCUS_AI_API_KEY=
FOCUS_AI_MODEL=your-local-tool-capable-model
FOCUS_AI_BASE_URL=http://127.0.0.1:11434/v1
```

Local endpoints work only when FocusWith runs on the same machine or can otherwise reach that address. A text-only model can answer ordinary messages, but Focus actions require OpenAI-compatible tool calls.

## Existing chat products

- **Codex, Claude Desktop/Code, and other local MCP clients:** point a stdio server at `scripts/focus-mcp`; see [MCP.md](MCP.md).
- **Claude.ai:** connect the OAuth-protected HTTPS `/mcp` endpoint; see [REMOTE_MCP.md](REMOTE_MCP.md).
- **ChatGPT:** create a developer-mode app that points to the same HTTPS `/mcp` endpoint. ChatGPT supports OAuth discovery, DCR, and PKCE, which FocusWith already implements. FocusWith intentionally rejects OAuth callback URLs that are not explicitly allowed; add the exact callback presented by the client to `FOCUS_OAUTH_ALLOWED_REDIRECT_URIS` instead of using a wildcard.

Chat-product availability and write permissions depend on the account and workspace. The FocusWith server always advertises tool safety annotations, uses one scoped OAuth permission, and lets the client decide when to ask for confirmation.

## Security boundary

- The built-in Companion receives only the seven Focus tools defined by the server.
- MCP clients never receive the provider API key.
- The phone token cannot access projects, task notes, AI keys, or OAuth tokens.
- Remote MCP stays disabled unless HTTPS and the OAuth owner-password hash are both configured.
