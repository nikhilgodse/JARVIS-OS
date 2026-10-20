import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(ROOT, "frontend", name), encoding="utf-8") as f:
        return f.read()


# Strings that claimed success, live data, or security without a backend
# behind them. If any reappears in the normal command path, this fails.
# (Brittle by design: it is a tripwire, not a style check.)
FORBIDDEN = [
    "All systems online and operational",
    "Arc Reactor output nominal",
    "Reactors at 100%",
    "Suit diagnostics green",
    "At your service, sir. All systems nominal.",
    "Math.random() * 18",
    "fall through to demo drift",
    "Created ${",
    "Removed ${",
    "3 matches in local index",
    "reactor_check",
    "Access granted. Welcome, sir. (default password",
    "running local heuristic",
    "works without Google speech servers",
    "LLM ${s.llm.configured ? 'CONNECTED",
]

REQUIRED_JS = [
    "nothing was executed",
    "primary_health",
    "Server transcription: sending mic audio",
]

REQUIRED_HTML = [
    "CORE TEMP (EST)",
    "app.js?v=",
]


class TestFrontendHonesty(unittest.TestCase):
    def test_no_simulated_success(self):
        js = _read("app.js")
        for s in FORBIDDEN:
            self.assertNotIn(s, js, f"fiction leaked back into app.js: {s!r}")

    def test_honest_replacements_present(self):
        js = _read("app.js")
        for s in REQUIRED_JS:
            self.assertIn(s, js, f"expected honesty marker missing: {s!r}")

    def test_estimated_temp_labelled(self):
        html = _read("index.html")
        for s in REQUIRED_HTML:
            self.assertIn(s, html, f"expected marker missing in index.html: {s!r}")


if __name__ == "__main__":
    unittest.main()
