#!/usr/bin/env python3
"""End-to-end happy-path smoke test (spec group 15).

Drives the full user journey over HTTP against a running backend:

    search -> upload -> ingest job -> 5-minute reading -> cross-chapter
    question -> save progress -> continue -> unauthorized access rejected

Runs against **local-mock mode now** and the **real AWS deployment post-deploy**
without changes — only the base URL and auth differ.

Usage:
    # Local mock (backend started with APP_ENV=local LOCAL_MOCK=true
    # AUTH_ALLOW_LOCAL_DEV_USER=true). No token needed:
    python scripts/e2e_smoke.py --base-url http://localhost:8000

    # Real deployment (Cognito): pass an access token:
    python scripts/e2e_smoke.py --base-url https://api.example.com --token "$JWT"

Exit code 0 = all steps passed; non-zero = a step failed (details printed).

Depends only on the standard library (urllib), so it needs no extra installs.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


class Client:
    def __init__(self, base_url: str, token: str | None) -> None:
        self._base = base_url.rstrip("/")
        self._token = token

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> tuple[int, Any]:
        url = f"{self._base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = resp.read().decode()
                return resp.status, (json.loads(payload) if payload else None)
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode()
            try:
                return exc.code, json.loads(payload)
            except json.JSONDecodeError:
                return exc.code, payload

    def get(self, path: str) -> tuple[int, Any]:
        return self._request("GET", path)

    def post(self, path: str, body: dict[str, Any]) -> tuple[int, Any]:
        return self._request("POST", path, body)

    def put(self, path: str, body: dict[str, Any]) -> tuple[int, Any]:
        return self._request("PUT", path, body)


class Runner:
    def __init__(self, client: Client) -> None:
        self.client = client
        self.passed = 0
        self.failed = 0

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        mark = "PASS" if condition else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail and not condition else ""))
        if condition:
            self.passed += 1
        else:
            self.failed += 1

    def run(self) -> int:
        c = self.client
        api = "/api/v1"

        # 0. Health
        status, _ = c.get("/health")
        self.check("health endpoint responds 200", status == 200, f"got {status}")

        # 1. Search (requirement 2.1)
        status, results = c.get(f"{api}/books/search?q=atomic+habits&limit=5")
        self.check("book search returns 200", status == 200, f"got {status}")
        items = (results or {}).get("items", []) if isinstance(results, dict) else []
        self.check("search returns at least one book (2.1)", len(items) >= 1)

        # 2. Upload (requirement 3.1/3.2/3.3)
        status, presign = c.post(
            f"{api}/uploads/presign",
            {
                "filename": "e2e.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1000,
                "authorized_confirmation": True,
            },
        )
        self.check("presign returns 201", status == 201, f"got {status}")
        if status != 201:
            return self._finish()
        book_id = presign["book_id"]
        object_key = presign["object_key"]

        # Upload the bytes to the presigned target (skipped for the local sentinel).
        if not presign["upload_url"].startswith("local-mock://"):
            self._put_s3(presign, b"%PDF-1.4 e2e placeholder")

        # 3. Ingest -> job (requirement 3.4/8.1)
        status, ingest = c.post(
            f"{api}/books/{book_id}/ingest", {"object_key": object_key}
        )
        self.check("ingest returns 202", status == 202, f"got {status}")
        if status != 202:
            return self._finish()
        job_id = ingest["job_id"]

        ingest_job = self._poll_job(job_id)
        self.check(
            "ingestion job completes (8.1)",
            ingest_job.get("status") == "COMPLETED",
            f"status={ingest_job.get('status')} error={ingest_job.get('error_code')}",
        )

        # 4. 5-minute balanced reading (requirement 4.7/4.5/4.6)
        status, gen = c.post(
            f"{api}/reading/generate",
            {
                "book_id": book_id,
                "duration_minutes": 5,
                "mode": "balanced_read",
                "focus": "key_ideas",
            },
        )
        self.check("reading generate returns 202 with job id (4.7)", status == 202)
        reading_id = gen["job_id"] if status == 202 else None
        if reading_id:
            self._poll_job(reading_id)
            status, reading = c.get(f"{api}/reading/{reading_id}")
            self.check("reading result fetched 200", status == 200, f"got {status}")
            content = (reading or {}).get("content", "")
            self.check("reading has coherent content (4.5)", len(content.split()) > 20)
            self.check(
                "reading reports target vs actual words",
                (reading or {}).get("target_words") == 750,
            )

        # 5. Discussion: cross-chapter question (requirement 5.1/5.4)
        status, conv = c.post(f"{api}/discussions", {"book_id": book_id})
        self.check("create conversation returns 201", status == 201, f"got {status}")
        if status == 201:
            conv_id = conv["conversation_id"]
            status, msg = c.post(
                f"{api}/discussions/{conv_id}/messages",
                {"question": "How do the ideas connect across chapters?"},
            )
            self.check("grounded answer returns 201 (5.1)", status == 201, f"got {status}")
            self.check(
                "answer is grounded with content (5.4)",
                bool((msg or {}).get("content")),
            )

        # 6. Progress save + continue (requirement 6.1/6.2)
        status, prog = c.put(
            f"{api}/progress/{book_id}",
            {"position": 120, "selected_mode": "balanced_read"},
        )
        self.check("save progress returns 200 (6.1)", status == 200, f"got {status}")
        status, cont = c.get(f"{api}/progress/{book_id}")
        self.check(
            "continue reading reflects saved position (6.2)",
            status == 200 and (cont or {}).get("position") == 120,
        )

        # 7. Unauthorized access rejected (requirement 1.3)
        status, _ = c.get(f"{api}/jobs/this-job-does-not-belong-to-me")
        self.check(
            "unauthorized/unknown resource rejected (1.3)",
            status in (403, 404),
            f"got {status}",
        )

        return self._finish()

    def _poll_job(self, job_id: str, *, attempts: int = 60, interval: float = 2.0) -> dict:
        for _ in range(attempts):
            status, job = self.client.get(f"/api/v1/jobs/{job_id}")
            if status != 200 or not isinstance(job, dict):
                return {"status": "UNKNOWN"}
            if job.get("status") in ("COMPLETED", "FAILED"):
                return job
            time.sleep(interval)
        return {"status": "TIMEOUT"}

    @staticmethod
    def _put_s3(presign: dict[str, Any], data: bytes) -> None:
        req = urllib.request.Request(
            presign["upload_url"],
            data=data,
            headers=presign.get("required_headers", {}),
            method=presign.get("method", "PUT"),
        )
        urllib.request.urlopen(req, timeout=60)

    def _finish(self) -> int:
        print(f"\n{self.passed} passed, {self.failed} failed")
        return 1 if self.failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Book Companion e2e smoke test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default=None, help="Bearer token (real AWS only)")
    args = parser.parse_args()

    print(f"Running e2e smoke against {args.base_url}\n")
    return Runner(Client(args.base_url, args.token)).run()


if __name__ == "__main__":
    sys.exit(main())
