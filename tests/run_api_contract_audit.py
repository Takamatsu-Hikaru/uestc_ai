"""Run isolated API tests and record method+route coverage without response bodies.

Use only a development checkout. Do not source production environment files.
Provider, mail, compute and Docker business tests use loopback fixtures/mocks;
the runner rejects non-loopback socket connections as a final boundary.
"""
from __future__ import annotations

import argparse
from collections import Counter
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "test-results" / "api-audit.json")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--strict-coverage", action="store_true")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    events, outcomes = [], {}
    active_test = {"id": "inventory"}
    lock = threading.Lock()
    blocked = []

    with tempfile.TemporaryDirectory(prefix="uestc-api-audit-") as temporary:
        runtime = Path(temporary)
        # Test-specific create_app configurations override these safe fallbacks.
        os.environ["DATABASE_URL"] = "sqlite:///" + str(runtime / "fallback.sqlite3")
        os.environ["UPLOAD_FOLDER"] = str(runtime / "uploads")
        os.environ["REDIS_URL"] = ""
        for name in ("RESEND_API_KEY", "EVALUATION_API_KEY", "EVALUATION_API_TOKEN", "UESTC_MODEL_API_KEY"):
            os.environ.pop(name, None)
        from flask import Flask, g, request
        from platform_api import create_app

        app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://",
                          "UPLOAD_FOLDER": str(runtime / "inventory-uploads"),
                          "AUTO_CREATE_SCHEMA": False, "SEED_DATABASE": False, "REDIS_URL": ""})
        inventory = sorted([
            {"rule": rule.rule, "method": method, "endpoint": rule.endpoint,
             "module": app.view_functions[rule.endpoint].__module__}
            for rule in app.url_map.iter_rules() if rule.rule.startswith("/api/")
            for method in rule.methods - {"HEAD", "OPTIONS"}
        ], key=lambda row: (row["rule"], row["method"]))
        dispatch = Flask.full_dispatch_request

        def traced_dispatch(instance):
            before = time.monotonic()
            response = None
            try:
                response = dispatch(instance)
                return response
            finally:
                rule = request.url_rule
                if rule and rule.rule.startswith("/api/") and request.method not in {"HEAD", "OPTIONS"}:
                    user = getattr(g, "current_user", None)
                    # No tokens, request bodies, concrete resource IDs or mail addresses.
                    with lock:
                        events.append({"test": active_test["id"], "method": request.method,
                                       "rule": rule.rule, "endpoint": rule.endpoint,
                                       "status": response.status_code if response is not None else 500,
                                       "role": getattr(user, "role", "anonymous-or-unresolved"),
                                       "handler_ms": round((time.monotonic() - before) * 1000, 2)})

        connect, connect_ex = socket.socket.connect, socket.socket.connect_ex

        def permitted(sock, address):
            if sock.family == getattr(socket, "AF_UNIX", None):
                return True
            host = address[0] if isinstance(address, tuple) and address else ""
            try:
                allowed = host == "localhost" or ipaddress.ip_address(host).is_loopback
            except ValueError:
                allowed = False
            if not allowed:
                blocked.append({"test": active_test["id"], "host": str(host)})
                raise RuntimeError("API audit blocked non-loopback network access")
            return True

        def safe_connect(sock, address):
            permitted(sock, address)
            return connect(sock, address)

        def safe_connect_ex(sock, address):
            permitted(sock, address)
            return connect_ex(sock, address)

        class Result(unittest.TextTestResult):
            def startTest(self, test):
                active_test["id"] = test.id()
                super().startTest(test)

            def addSuccess(self, test):
                outcomes[test.id()] = {"outcome": "passed"}
                super().addSuccess(test)

            def addFailure(self, test, error):
                outcomes[test.id()] = {"outcome": "failed", "reason": str(error[1])}
                super().addFailure(test, error)

            def addError(self, test, error):
                outcomes[test.id()] = {"outcome": "error", "reason": str(error[1])}
                super().addError(test, error)

            def addSkip(self, test, reason):
                outcomes[test.id()] = {"outcome": "skipped", "reason": reason}
                super().addSkip(test, reason)

            def stopTest(self, test):
                super().stopTest(test)
                if self.testsRun % 25 == 0:
                    print(f"AUDIT_PROGRESS tests={self.testsRun} requests={len(events)} failures={len(self.failures)} errors={len(self.errors)}", flush=True)

        with patch.object(Flask, "full_dispatch_request", traced_dispatch), \
             patch.object(socket.socket, "connect", safe_connect), \
             patch.object(socket.socket, "connect_ex", safe_connect_ex):
            suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=args.pattern)
            result = unittest.TextTestRunner(verbosity=1, resultclass=Result).run(suite)

        coverage = []
        for route in inventory:
            matches = [event for event in events if event["method"] == route["method"] and event["rule"] == route["rule"]]
            passing = [event for event in matches if outcomes.get(event["test"], {}).get("outcome") == "passed"]
            statuses = Counter(str(event["status"]) for event in passing)
            coverage.append({**route, "request_count": len(passing), "observed_statuses": dict(statuses),
                             "success_exercised": any(200 <= event["status"] < 300 for event in passing),
                             "redirect_exercised": any(300 <= event["status"] < 400 for event in passing),
                             "rejection_exercised": any(400 <= event["status"] < 500 for event in passing),
                             "passing_tests": sorted(set(event["test"] for event in passing)),
                             "roles": sorted(set(event["role"] for event in passing))})
        summary = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                   "skipped": len(result.skipped), "registered_method_routes": len(inventory),
                   "covered_method_routes": sum(bool(route["request_count"]) for route in coverage),
                   "success_method_routes": sum(route["success_exercised"] for route in coverage),
                   "redirect_method_routes": sum(route["redirect_exercised"] for route in coverage),
                   "rejection_method_routes": sum(route["rejection_exercised"] for route in coverage),
                   "requests_recorded": len(events), "seconds": round(time.monotonic() - started, 2)}
        document = {"summary": summary, "scope": "isolated SQL/upload paths; external sockets blocked; method+route coverage excludes HEAD/OPTIONS",
                    "coverage": coverage, "tests": outcomes, "events": events, "blocked_external_connections": blocked}
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        print("AUDIT_SUMMARY " + json.dumps(summary), flush=True)
        return 0 if result.wasSuccessful() and (not args.strict_coverage or summary["covered_method_routes"] == len(inventory)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
