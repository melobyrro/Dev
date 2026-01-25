#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const sdkRoot = path.resolve(__dirname, "..", "node_modules/@modelcontextprotocol/sdk/dist/cjs");
const { Client } = require(path.join(sdkRoot, "client/index.js"));
const { StdioClientTransport } = require(path.join(sdkRoot, "client/stdio.js"));
const { ListToolsResultSchema, CallToolResultSchema } = require(path.join(sdkRoot, "types.js"));

const requestTimeoutMsec = Number(process.env.MCP_REQUEST_TIMEOUT_MSEC || "120000");

function resolveCommand(cmd) {
  if (cmd.includes("/") || cmd.includes("\\")) return cmd;
  const envPath = process.env.PATH || "";
  for (const dir of envPath.split(path.delimiter)) {
    if (!dir) continue;
    const candidate = path.join(dir, cmd);
    try {
      fs.accessSync(candidate, fs.constants.X_OK);
      return candidate;
    } catch {
    }
  }
  return cmd;
}

function missingEnvVars(requiredEnv) {
  return (requiredEnv || []).filter((k) => !process.env[k]);
}

const tests = [
  {
    key: "browser",
    name: "browser",
    command: resolveCommand("mcp-server-browser"),
    args: ["--headless", "--viewport-size", "1280,720"],
    tool: "browser_navigate",
    toolArgs: { url: "https://www.google.com" },
    afterCalls: [
      { name: "browser_close" }
    ]
  },
  {
    key: "semgrep",
    name: "semgrep",
    command: "/Users/andrebyrro/bin/custom-semgrep-mcp",
    tool: "semgrep_scan",
    toolArgs: { target: "scripts/mcp_smoke.js" }
  },
  {
    key: "ref",
    name: "ref",
    command: resolveCommand("ref-tools-mcp"),
    requiredEnv: ["REF_API_KEY"],
    tool: "ref_search_documentation",
    toolArgs: { query: "Node.js fs promises" }
  },
  {
    key: "tavily",
    name: "tavily",
    command: resolveCommand("tavily-mcp"),
    requiredEnv: ["TAVILY_API_KEY"],
    tool: "tavily-search",
    toolArgs: { query: "latest homelab best practices" }
  },
  {
    key: "exa",
    name: "exa",
    command: resolveCommand("exa-mcp-server"),
    requiredEnv: ["EXA_API_KEY"],
    tool: "web_search_exa",
    toolArgs: { query: "authelia forward auth" }
  }
];

const only = process.env.MCP_ONLY ? new Set(process.env.MCP_ONLY.split(",")) : null;

async function runTest(test) {
  console.log(`\n=== ${test.name} MCP ===`);
  const env = { ...process.env, ...(test.env || {}) };
  const transport = new StdioClientTransport({
    command: test.command,
    args: test.args || [],
    env,
    stderr: "inherit"
  });
  const client = new Client({ name: "codex-mcp-smoke", version: "1.0.0" });
  try {
    await client.connect(transport);
    const toolsResponse = await client.request(
      { method: "tools/list", params: {} },
      ListToolsResultSchema,
      { timeout: requestTimeoutMsec }
    );
    const toolNames = toolsResponse.tools?.map(t => t.name).join(", ") || "(none)";
    console.log(`${test.name} tools: ${toolNames}`);
    if (Array.isArray(test.beforeCalls)) {
      for (const step of test.beforeCalls) {
        await client.request(
          {
            method: "tools/call",
            params: { name: step.name, arguments: step.arguments || {} }
          },
          CallToolResultSchema,
          { timeout: requestTimeoutMsec, resetTimeoutOnProgress: true }
        );
      }
    }
    if (test.tool) {
      const callResponse = await client.request(
        {
          method: "tools/call",
          params: {
            name: test.tool,
            arguments: test.toolArgs || {}
          }
        },
        CallToolResultSchema,
        { timeout: requestTimeoutMsec, resetTimeoutOnProgress: true }
      );
      console.log(`${test.name} call result:`, JSON.stringify(callResponse, null, 2));
    }
    if (Array.isArray(test.afterCalls)) {
      for (const step of test.afterCalls) {
        await client.request(
          {
            method: "tools/call",
            params: { name: step.name, arguments: step.arguments || {} }
          },
          CallToolResultSchema,
          { timeout: requestTimeoutMsec, resetTimeoutOnProgress: true }
        );
      }
    }
  } catch (err) {
    console.error(`${test.name} smoke test failed:`, err);
    throw err;
  } finally {
    await transport.close();
  }
}

(async () => {
  for (const test of tests) {
    if (only && !only.has(test.key)) continue;
    const missing = missingEnvVars(test.requiredEnv);
    if (missing.length) {
      console.log(`\n=== ${test.name} MCP ===`);
      console.log(`Skipping ${test.name}: missing env var(s): ${missing.join(", ")}`);
      continue;
    }
    try {
      await runTest(test);
    } catch (err) {
      process.exitCode = 1;
      break;
    }
  }
})();
