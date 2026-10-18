import json

import pytest

from helpdesk.api.app import openapi_schema
from helpdesk.cli import main


def test_openapi_prints_the_schema_without_any_settings(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for variable in ("HELPDESK_DATABASE_URL", "HELPDESK_REDIS_URL", "HELPDESK_JWT_SECRET"):
        monkeypatch.delenv(variable, raising=False)

    assert main(["openapi"]) == 0

    printed = capsys.readouterr().out
    assert json.loads(printed) == openapi_schema()
    assert printed.isascii()
