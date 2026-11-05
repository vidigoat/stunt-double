"""The browser double (Pattern B): a real Chromium in the sandbox drives a double of the admin site."""
from app import agent, sandbox
from tests.conftest import needs_browser

WRONG = '''def run(ctx):
    ctx.browser.open("/subscriptions")
    ctx.browser.search("Nora Dubois")
    ctx.browser.click("Cancel")
'''
RIGHT = WRONG.replace('click("Cancel")', 'click("#cancel-4411")')


def _sub_change(c):
    return [(u["rowid"], u["after"]["status"]) for u in c["tables"].get("subscriptions", {}).get("samples", {}).get("updated", [])]


@needs_browser
def test_the_first_cancel_button_cancels_the_wrong_subscription(fresh_business):
    c = sandbox.rehearse(WRONG)["consequences"]
    assert c["ok"], c.get("error")
    assert _sub_change(c) == [(4141, "cancelled")]
    assert [s["action"] for s in c["browser"]["steps"]] == ["open", "search", "click"]
    assert c["sandbox"]["profile"] == "browser" and c["sandbox"]["screenshots"] == 3
    assert agent._screenshots(c)   # the verifier gets the screens as images


@needs_browser
def test_the_right_click_cancels_only_the_duplicate(fresh_business):
    c = sandbox.rehearse(RIGHT)["consequences"]
    assert _sub_change(c) == [(4411, "cancelled")]


@needs_browser
def test_the_browser_sandbox_is_still_contained(fresh_business):
    code = '''def run(ctx):
    ctx.browser.open("/subscriptions")
    page = ctx.browser._page
    try:
        page.goto("https://example.com", timeout=4000)
        ctx.log("REACHED THE INTERNET")
    except Exception as e:
        ctx.log("blocked: " + type(e).__name__)
    import os
    ctx.log("env=" + ",".join(sorted(os.environ)))
'''
    c = sandbox.rehearse(code)["consequences"]
    logs = " ".join(c["logs"])
    assert "REACHED THE INTERNET" not in logs and "blocked" in logs
    assert "KEY" not in logs and "TOKEN" not in logs and "SECRET" not in logs
    assert c["sandbox"]["network"] == "none"
