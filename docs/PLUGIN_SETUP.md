# Connect the Spec2Proof plugin

The standalone browser demo is ready without these steps. This setup is optional and requires access to your OpenAI account. It does not require publishing the source or exposing the browser server.

## 1. Start the shared local store

Install the project into your chosen Python environment if the MCP process will start outside the checkout:

```sh
python -m pip install -e /absolute/path/to/spec2proof
python -m spec2proof.server --data-dir /absolute/path/to/spec2proof/.spec2proof
```

Use the same Python interpreter and absolute `--data-dir` for the MCP process:

```sh
python -m spec2proof.mcp_server --data-dir /absolute/path/to/spec2proof/.spec2proof
```

It waits for newline-delimited JSON-RPC on stdin; that is normal. Do not run it as a web server. The included `mcp.json` uses the installed Python package and its default data directory. Before installing the package as a plugin, customize it using `mcp.json.example`: set the correct Python executable and the absolute shared data directory. Alternatively, set `SPEC2PROOF_DATA` to that absolute directory in the environment inherited by both processes. No connection is installed or registered just by having these files.

## 2. Connect privately using the documented tunnel flow

Follow the current [Secure MCP Tunnel instructions](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels). You need a tunnel ID, a runtime key, tunnel permissions, and association with the target ChatGPT workspace. Keep credentials out of this repository.

Use `tunnel-client help quickstart`, then initialize the documented `sample_mcp_stdio_local` profile with `--mcp-command` set to the full Python MCP command above. Run `tunnel-client doctor --profile local-stdio --explain` and `tunnel-client run --profile local-stdio`.

In ChatGPT Plugins, add a custom MCP server, choose **Tunnel**, select the associated tunnel, review permissions, create the personal plugin, and install it. These steps require the account holder's login and any applicable workspace-admin permission. They were not performed during the local build.

## 3. Host acceptance check

1. Ask `@Spec2Proof` to open the workbench. Check both sidebar and conversation-panel discovery.
2. Ask: “Create a proof for full refunds of unused items within 14 calendar days, including day 14. Used or late items get no refund; negative inputs are rejected.”
3. Confirm the displayed contract, then ask to run the baseline. Expect AC2 and AC4 to fail.
4. Ask for a proposed patch. Verify that the agent does not claim it has applied it.
5. Open `http://127.0.0.1:8765/#PROOF_ID` on the same computer. Approve the displayed diff there.
6. Ask ChatGPT to refresh the proof. Expect 10/10 passing and unchanged test hashes.

If the host blocks navigation to localhost, copy that URL into a normal browser. If you use a different port, replace 8765 manually. The ChatGPT panel cannot approve or download; those actions remain local.

Negative tests: partial refunds or fees must prompt clarification; approval requests must direct the user to local review; missing confirmation must fail. Tool/resource refresh may be needed after changes.

The adapter implements initialize, ping, tools/list, tools/call, resources/list, resources/read, and ignores notifications. It does not expose streamable HTTP, OAuth, subscriptions, prompts, or an arbitrary-code tool. A public, multi-user service would need a fuller transport/authentication design.
