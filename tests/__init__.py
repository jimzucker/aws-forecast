"""
Test package bootstrap.

Responsibilities (run before any test module is imported):
1. Put the project root on sys.path so ``import get_forecast`` works without
   installing the module as a package.
2. If ``boto3`` / ``botocore`` aren't installed (e.g. running offline), stub
   them with the minimum surface get_forecast imports. Every test mocks the
   boto3 interactions anyway, so a real SDK is not required to run the suite.
"""
import logging
import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Silence the noisy get_forecast logger during tests. Several tests exercise
# error branches on purpose and we don't want their log output cluttering
# stdout/stderr. ``basicConfig`` is installed first so that the one inside
# get_forecast.py becomes a no-op; ``disable`` then drops everything at or
# below CRITICAL.
logging.basicConfig(level=logging.CRITICAL)
logging.disable(logging.CRITICAL)


def _install_boto3_stub():
    boto3 = ModuleType("boto3")
    session_mod = ModuleType("boto3.session")

    class _StubSession:
        """Minimal stand-in so ``boto3.session.Session()`` is callable.

        Tests never hit this class directly — they either patch it out or
        supply a MagicMock session. It exists so the module import succeeds.
        """

        def __init__(self, *args, **kwargs):
            self._kwargs = kwargs

        def client(self, name, *args, **kwargs):  # pragma: no cover
            raise RuntimeError(
                "boto3 is stubbed in this environment; tests must mock clients."
            )

    session_mod.Session = _StubSession
    boto3.session = session_mod
    boto3.client = lambda *a, **kw: (_ for _ in ()).throw(  # pragma: no cover
        RuntimeError("boto3 is stubbed; tests must mock clients.")
    )
    sys.modules.setdefault("boto3", boto3)
    sys.modules.setdefault("boto3.session", session_mod)


def _install_botocore_stub():
    botocore = ModuleType("botocore")
    exceptions_mod = ModuleType("botocore.exceptions")

    class _ClientError(Exception):
        def __init__(self, response=None, operation_name=None):
            super().__init__(operation_name or "ClientError")
            self.response = response or {"Error": {"Code": "Unknown"}}
            self.operation_name = operation_name

    exceptions_mod.ClientError = _ClientError
    botocore.exceptions = exceptions_mod
    sys.modules.setdefault("botocore", botocore)
    sys.modules.setdefault("botocore.exceptions", exceptions_mod)


try:
    import boto3  # noqa: F401
except ModuleNotFoundError:
    _install_boto3_stub()

try:
    import botocore.exceptions  # noqa: F401
except ModuleNotFoundError:
    _install_botocore_stub()
