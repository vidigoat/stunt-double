"""Talk to the MCP server exactly like an agent would: over stdio with the official MCP client."""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).resolve().parents[1] / "server.py"
GOOD = '''def run(ctx):
    rows = ctx.db.execute("""SELECT id, amount_cents FROM charges WHERE created_at >= '2026-10-26' AND status='succeeded'
      AND order_id IN (SELECT order_id FROM charges GROUP BY order_id HAVING COUNT(*) > 1)
      AND id NOT IN (SELECT MIN(id) FROM charges GROUP BY order_id)""").fetchall()
    for cid, amt in rows:
        ctx.db.execute("UPDATE charges SET status='refunded' WHERE id=?", (cid,))
        ctx.payments.refund(cid, amt, "duplicate charge")
'''
EVIL = 'def run(ctx):\n    ctx.db.execute("DELETE FROM customers")\n'


async def main() -> None:
    import httpx
    httpx.post(os.environ.get("STUNT_DOUBLE_API", "http://localhost:8000") + "/api/demo/reset").raise_for_status()   # fresh demo business
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env={**os.environ})
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        tools = {t.name for t in (await s.list_tools()).tools}
        assert tools == {"describe_business", "rehearse", "get_run_status", "list_connectors", "request_undo", "list_workspaces",
                         "keep_only_what_is_right", "what_does_this_mean"}, tools   # no approve tool
        conns = json.loads((await s.call_tool("list_connectors", {})).content[0].text)["connectors"]
        assert any(c["name"] == "slack" for c in conns)
        schema = json.loads((await s.call_tool("describe_business", {})).content[0].text)
        assert "charges" in schema["tables"] and "ctx.payments.refund" in schema["plan_api"]
        good = json.loads((await s.call_tool("rehearse", {"task": "Refund double charges", "plan_code": GOOD})).content[0].text)
        assert good["status"] == "review" and good["refunds"] == 104 and not good["blocked_by_policy"], good
        assert good["approval_url"].endswith(f"/app?run={good['run_id']}")
        evil = json.loads((await s.call_tool("rehearse", {"task": "clean up", "plan_code": EVIL})).content[0].text)
        assert evil["blocked_by_policy"] and evil["row_changes"]["customers"]["deleted"] == 1300, evil
        assert evil["decision"]["decision"] == "blocked" and evil["proof_of_effect"] == "proven", evil
        status = json.loads((await s.call_tool("get_run_status", {"run_id": good["run_id"]})).content[0].text)
        assert status["status"] == "review"
        import httpx as _h
        api = os.environ.get("STUNT_DOUBLE_API", "http://localhost:8000")
        _h.post(f"{api}/api/runs/{good['run_id']}/approve", json={"approver": "Human"}).raise_for_status()   # a human approves
        undo = json.loads((await s.call_tool("request_undo", {"run_id": good["run_id"]})).content[0].text)
        assert undo["status"] == "review" and undo["approvals_required"] == 2 and undo["irreversible"]["refunds"] == 104, undo
        print("MCP OK:", sorted(tools), "| good:", good["refunds"], "refunds", good["money_out_usd"], "USD | evil blocked:", evil["blocked_by_policy"][0])


if __name__ == "__main__":
    asyncio.run(main())
