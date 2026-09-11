import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { execFileSync, execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";
import { homedir } from "node:os";
import { pathToFileURL } from "node:url";

export default function modHarness(pi: ExtensionAPI) {
  // 2026-09-11: project-only adapter. Global configuration now loads local-harness.
  // Preserve existing tools; /pre-flight delegates to the common deterministic CLI below.
  // 1. Session Start Banner
  pi.on("session_start", async (_event, ctx) => {
    // Former banner retained: MOD Project Harness Active: Governance & Safe Tooling Enabled
    ctx.ui?.notify?.("MOD project tools loaded; task policy is provided by the global Pi extension.", "info");
  });

  // 2. Custom Tool: Safe Read-only DB Query
  pi.registerTool({
    name: "mod_db_query",
    label: "MOD Read-Only DB Query",
    description: "Safely execute a read-only SQL query (SELECT/SHOW/DESC/EXPLAIN) on the local MOD database without passwords or bash execution. Returns clean JSON.",
    parameters: Type.Object({
      query: Type.String({ description: "The read-only SQL query to execute" }),
      limit: Type.Optional(Type.Number({ description: "Maximum rows to return (default 50, max 200)" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const sql = params.query.trim();
      const rowLimit = String(Math.min(params.limit || 50, 200));

      try {
        const output = execFileSync(
          "/home/ubuntu/mod/backend/.venv/bin/python",
          ["/home/ubuntu/mod/scripts/project/safe_db_query.py", sql, rowLimit],
          {
            env: {
              ...process.env,
              PYTHONPATH: "/home/ubuntu/mod/backend",
            },
            encoding: "utf8",
            timeout: 15000,
          }
        );
        const data = JSON.parse(output.trim());
        if (!data.success) {
          return {
            content: [{ type: "text", text: `[DB Error] ${data.error}` }],
            details: { success: false },
          };
        }
        return {
          content: [
            {
              type: "text",
              text: `[Query OK] ${data.count} rows returned:\n` + JSON.stringify(data.rows, null, 2),
            },
          ],
          details: { rowCount: data.count },
        };
      } catch (err: any) {
        return {
          content: [{ type: "text", text: `[Execution Error] ${err.message || String(err)}` }],
          details: { error: true },
        };
      }
    },
  });

  // 3. Custom Tool: Check Simulator Health & Fuse Limits
  pi.registerTool({
    name: "mod_simulator_status",
    label: "MOD Simulator Health Monitor",
    description: "Check the runtime health, fuse rate limits (per minute/day), and degraded status of mod-simulator daemon.",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, _ctx) {
      try {
        const out = execSync("python3 scripts/project/check_simulator_status.py", {
          cwd: "/home/ubuntu/mod",
          encoding: "utf8",
          timeout: 5000,
        });
        return {
          content: [{ type: "text", text: out.trim() }],
          details: { success: true },
        };
      } catch (e: any) {
        return {
          content: [{ type: "text", text: `[Error querying simulator] ${e.stdout || e.stderr || e.message}` }],
          details: { error: true },
        };
      }
    },
  });

}

