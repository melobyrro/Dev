const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

// Adjust these paths based on script location in homelab/
const repoRoot = path.resolve(__dirname, "../..");
const sdkPath = path.join(repoRoot, "node_modules/@modelcontextprotocol/sdk/dist/cjs");
const { Client } = require(path.join(sdkPath, "client/index.js"));
const { StdioClientTransport } = require(path.join(sdkPath, "client/stdio.js"));
const { ListToolsResultSchema, CallToolResultSchema } = require(path.join(sdkPath, "types.js"));

// Path to the MCP server executable
const serverScript = path.join(repoRoot, "node_modules/chrome-devtools-mcp/build/src/index.js");

async function run() {
  console.log("Starting Dashboard Inventory Extraction...");
  console.log("Server Script:", serverScript);

  if (!fs.existsSync(serverScript)) {
    console.error("MCP Server script not found!");
    process.exit(1);
  }

  const transport = new StdioClientTransport({
    command: "node",
    args: [serverScript],
    stderr: "inherit"
  });

  const client = new Client({ name: "dashboard-validator", version: "1.0.0" });

  try {
    await client.connect(transport);
    console.log("Connected to MCP Server.");

    // List tools
    const tools = await client.request({ method: "tools/list", params: {} }, ListToolsResultSchema);
    const toolNames = tools.tools.map(t => t.name);
    console.log("Available Tools:", toolNames);
    
    // Identify navigation tool
    const navTool = toolNames.find(n => n.includes("navigate") || n.includes("Page.navigate"));
    if (!navTool) {
      console.error("No navigation tool found!");
      return;
    }

    const targets = [
      "http://192.168.1.11:8123/homelab",
      "http://localhost:8123/homelab"
    ];

    for (const url of targets) {
        console.log(`\nChecking URL: ${url}`);
        try {
            // Navigate
            await client.request({
                method: "tools/call",
                params: { name: navTool, arguments: { url } }
            }, CallToolResultSchema);
            console.log("Navigated.");

            // Wait for HA to load (needs more time for frontend to initialize)
            await new Promise(r => setTimeout(r, 5000));

            // Extract Inventory via 'hass' object
            if (toolNames.includes("evaluate_script")) {
                 const func = `() => {
                    const ha = document.querySelector('home-assistant');
                    if (!ha || !ha.hass) return { error: "HASS object not found" };
                    
                    const states = ha.hass.states;
                    return { 
                        keys: Object.keys(states),
                        sample: Object.keys(states).slice(0, 5)
                    };
                 }`;
                 
                 const res = await client.request({
                    method: "tools/call",
                    params: { name: "evaluate_script", arguments: { function: func } }
                }, CallToolResultSchema);
                
                // Try to parse the result
                // It might be a JSON string or an object depending on the implementation
                console.log("Raw Result:", res.content[0].text.substring(0, 200));
                
                let result;
                try {
                     result = JSON.parse(res.content[0].text);
                } catch (e) {
                     // If it's not JSON, maybe it's the stringified object directly?
                     // Or maybe the tool returns the value directly?
                     console.log("JSON parse failed, assuming raw output needs inspection.");
                }
                
                if (result && result.keys) {
                    console.log(`✅ SUCCESS: Found ${result.keys.length} entities!`);
                    fs.writeFileSync("inventory.json", JSON.stringify(result.keys, null, 2));
                    console.log("Saved to inventory.json");
                    break; // Stop after success
                } else if (result && result.error) {
                    console.log(`❌ ERROR: ${result.error}`);
                    if (result.error === "HASS object not found") {
                        // Check for login screen
                        const loginCheck = `() => document.body.innerText`;
                        const resText = await client.request({
                            method: "tools/call",
                            params: { name: "evaluate_script", arguments: { function: loginCheck } }
                        }, CallToolResultSchema);
                        if (resText.content[0].text.includes("Username")) {
                            console.log("   -> Redirected to Login Screen.");
                        }
                    }
                }
            }

        } catch (e) {
            console.error(`   -> Failed to check ${url}:`, e.message);
        }
    }

  } catch (err) {
    console.error("Validation failed:", err);
  } finally {
    await transport.close();
    process.exit(0);
  }
}

run();