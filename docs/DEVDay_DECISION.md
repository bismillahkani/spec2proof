# Capability decision — checked October 10, 2026

## Selected path

Build the local Python proof engine and browser UI first, and expose the same workflow through an MCP App with sidebar and conversation-panel entrypoints. This keeps the working demonstration independent of hosting and account provisioning. Python execution is required; a static page alone cannot provide it.

## What official sources establish

| Question | Verified documentation | Consequence |
| --- | --- | --- |
| Do plugin extensions exist? | [Plugin Extensions](https://developers.openai.com/plugins/build/extensions) describes sidebar and conversation-panel entrypoints, registered through MCP tool metadata. | Implement `ui.resourceUri` and `openai/ui.entrypoints` for global and thread surfaces. |
| How is UI served? | [Add UI](https://developers.openai.com/plugins/build/chatgpt-ui) describes MCP App HTML resources and tool calls/results. | Use the shared app resource and host bridge; keep tools useful without UI. |
| What is required to connect? | [Connect and test](https://developers.openai.com/plugins/deploy/connect-chatgpt) requires reachable public HTTPS or a Secure MCP Tunnel and applicable workspace access. | Local functionality does not prove ChatGPT installation. Verify inside the host after connecting. |
| Can the server stay private? | [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) supports private stdio/HTTP servers. | Use a private stdio connection for this single-user MVP; tunnel ID, runtime key, and organization/workspace permissions are needed. |
| Are Spaces/Pages equivalent to Sites? | [ChatGPT Space](https://learn.chatgpt.com/docs/space) distinguishes pages/documents from Sites/web tools. [Getting started](https://learn.chatgpt.com/docs/space/getting-started) requires Space enabled on the account. | Do not assume a rename means a Python app can run inside a Page. A Page can document/link the project; it is not the execution backend. |
| How is a plugin packaged? | [Package your plugin](https://developers.openai.com/plugins/build/plugins) defines a root `plugin.json` and optional MCP configuration. | Include a portable manifest and a configuration example to be customized for the user's paths. |

Availability caveat: the extensions page says web access for Free and Go is coming soon and composer mentions are desktop-only. Documentation availability does not verify this account's plan, feature rollout, or administrator permissions.

## Why not publish a Site now?

Sites tooling is exposed in the build environment, but no site was registered or deployed because the user explicitly requested no publication/deployment. The installed Sites instructions describe a Cloudflare Workers runtime, not a conventional CPython subprocess host. A future hosted version needs an execution service with authentication and isolation. Hosting a visual simulation would not demonstrate real Python testing.

## Implementation confidence

The local workflow is the submission path. The MCP adapter is a bounded, dependency-free implementation of standard stdio request/response methods, not a full MCP SDK replacement. Metadata/resource behavior is tested locally. Private tunnel creation, host install, sidebar discovery, and actual ChatGPT bridge behavior are still integration checks requiring account access. No claim of live OpenAI model inference is made for standalone mode.
