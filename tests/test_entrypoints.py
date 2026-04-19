"""Unit tests for get_forecast.lambda_handler and get_forecast.main."""
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import get_forecast


class _EnvScope:
    def __init__(self, **overrides):
        self.overrides = overrides
        self.saved = {}

    def __enter__(self):
        for k, v in self.overrides.items():
            self.saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, saved in self.saved.items():
            if saved is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = saved
        return False


class LambdaHandlerTests(unittest.TestCase):
    def test_invokes_publish_forecast_with_module_level_boto3(self):
        with patch.object(get_forecast, "publish_forecast") as pf:
            get_forecast.lambda_handler({}, None)
            pf.assert_called_once_with(get_forecast.boto3)

    def test_wraps_failures_in_generic_exception(self):
        with patch.object(
            get_forecast, "publish_forecast",
            side_effect=RuntimeError("ce down"),
        ):
            # lambda_handler prints the underlying exception before re-raising;
            # capture that so it doesn't leak into test output.
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(Exception) as cm:
                    get_forecast.lambda_handler({}, None)
            self.assertIn("Cannot connect to Cost Explorer", str(cm.exception))


class MainTests(unittest.TestCase):
    def test_exits_zero_on_success(self):
        fake_session = MagicMock(name="session")
        with _EnvScope(GET_FORECAST_AWS_PROFILE=None):
            with patch.object(get_forecast.boto3.session, "Session",
                              return_value=fake_session) as session_cls, \
                 patch.object(get_forecast, "publish_forecast") as pf:
                with self.assertRaises(SystemExit) as cm:
                    get_forecast.main()
                self.assertEqual(cm.exception.code, 0)
                pf.assert_called_once_with(fake_session)
                # Default construction (no profile).
                session_cls.assert_called_once_with()

    def test_uses_profile_env_when_set(self):
        fake_session_default = MagicMock(name="default_session")
        fake_session_profile = MagicMock(name="profile_session")
        with _EnvScope(GET_FORECAST_AWS_PROFILE="jim-zucker"):
            with patch.object(
                get_forecast.boto3.session, "Session",
                side_effect=[fake_session_default, fake_session_profile],
            ) as session_cls, \
                 patch.object(get_forecast, "publish_forecast") as pf:
                with self.assertRaises(SystemExit) as cm:
                    get_forecast.main()
                self.assertEqual(cm.exception.code, 0)
                pf.assert_called_once_with(fake_session_profile)
                kwargs = session_cls.call_args_list[1].kwargs
                self.assertEqual(kwargs.get("profile_name"), "jim-zucker")

    def test_exits_one_on_publish_failure(self):
        fake_session = MagicMock(name="session")
        with _EnvScope(GET_FORECAST_AWS_PROFILE=None):
            with patch.object(get_forecast.boto3.session, "Session",
                              return_value=fake_session), \
                 patch.object(
                     get_forecast, "publish_forecast",
                     side_effect=RuntimeError("boom"),
                 ):
                with self.assertRaises(SystemExit) as cm:
                    get_forecast.main()
                self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
