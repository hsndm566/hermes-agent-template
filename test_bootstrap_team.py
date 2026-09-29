import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("bootstrap_team", Path(__file__).parent / "scripts/bootstrap-hermes-team.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BootstrapTeamTests(unittest.TestCase):
    def test_honcho_config_uses_shared_workspace_and_distinct_ai_peer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            MODULE.ensure_honcho_config(path, ai_peer="auditor")
            data = json.loads((path / "honcho.json").read_text())
            self.assertEqual(data["workspace"], "hasan")
            self.assertEqual(data["peerName"], "hasan")
            self.assertTrue(data["pinUserPeer"])
            self.assertEqual(data["aiPeer"], "auditor")
            self.assertNotIn("apiKey", data)

    def test_topic_routes_require_real_ids_and_known_profiles(self):
        old = os.environ.get("HERMES_TELEGRAM_PROFILE_ROUTES_JSON")
        try:
            os.environ["HERMES_TELEGRAM_PROFILE_ROUTES_JSON"] = json.dumps([
                {"profile": "marketing", "chat_id": "99", "thread_id": "7"},
                {"profile": "unknown", "chat_id": "99", "thread_id": "8"},
                {"profile": "cfo", "chat_id": "", "thread_id": "9"},
            ])
            routes = MODULE.topic_routes_from_env()
            self.assertEqual(len(routes), 1)
            self.assertEqual(routes[0]["profile"], "marketing")
            self.assertEqual(routes[0]["chat_id"], "99")
            self.assertEqual(routes[0]["thread_id"], "7")
        finally:
            if old is None:
                os.environ.pop("HERMES_TELEGRAM_PROFILE_ROUTES_JSON", None)
            else:
                os.environ["HERMES_TELEGRAM_PROFILE_ROUTES_JSON"] = old


if __name__ == "__main__":
    unittest.main()
