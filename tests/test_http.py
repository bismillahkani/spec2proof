import json
import re
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from spec2proof.core import DEFAULT_REQUIREMENT
from spec2proof.server import make_server


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = make_server(0, self.temp.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        html = urlopen(self.base).read().decode()
        self.token = re.search(r"TOKEN='([^']+)'", html)[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def post(self, path, data, token=None, origin=None):
        headers = {"Content-Type": "application/json", "X-Spec2Proof-Token": token or self.token}
        if origin:
            headers["Origin"] = origin
        return json.load(urlopen(Request(self.base + path, json.dumps(data).encode(), headers)))

    def test_http_complete_workflow(self):
        p = self.post("/api/proofs", {"requirement": DEFAULT_REQUIREMENT})
        path = "/api/proofs/" + p["id"]
        p = self.post(path + "/run", {"confirmed": True})
        p = self.post(path + "/propose", {})
        p = self.post(path + "/approve", {"approved": True, "proposal_sha256": p["proposal"]["sha256"]})
        self.assertEqual(p["state"], "verified")
        response = urlopen(Request(self.base + path + "/bundle", headers={"X-Spec2Proof-Token": self.token}))
        self.assertEqual(response.read()[:2], b"PK")

    def test_csrf_rejected(self):
        for kwargs in ({"token": "wrong"}, {"origin": "https://attacker.invalid"}):
            with self.assertRaises(HTTPError) as caught:
                self.post("/api/proofs", {"requirement": DEFAULT_REQUIREMENT}, **kwargs)
            self.assertEqual(caught.exception.code, 403)

    def test_confirmation_required(self):
        p = self.post("/api/proofs", {"requirement": DEFAULT_REQUIREMENT})
        with self.assertRaises(HTTPError) as caught:
            self.post("/api/proofs/" + p["id"] + "/run", {})
        self.assertEqual(caught.exception.code, 400)

    def test_bad_host_and_invalid_json_object(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.base, headers={"Host": "attacker.invalid"}))
        self.assertEqual(caught.exception.code, 403)
        with self.assertRaises(HTTPError) as caught:
            self.post("/api/proofs", [])
        self.assertEqual(caught.exception.code, 400)
