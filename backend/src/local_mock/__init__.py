"""Local mock mode.

In-memory fakes and an inline agent runner that make the full user journey
clickable locally without AWS. Only used when ``APP_ENV=local`` and
``LOCAL_MOCK=true`` (see ``Settings.use_local_mock``). The real AWS-backed paths
are unchanged and remain the default.

The fakes implement the same repository/port protocols as the real
implementations, so the application services are reused as-is.
"""
