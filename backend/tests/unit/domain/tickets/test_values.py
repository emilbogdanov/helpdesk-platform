import pytest

from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.tickets.values import (
    DESCRIPTION_MAX_LENGTH,
    SUBJECT_MAX_LENGTH,
    Description,
    Subject,
)


class TestSubject:
    def test_accepts_a_single_line(self) -> None:
        subject = Subject("Invoice PDF shows last month's VAT rate")

        assert str(subject) == "Invoice PDF shows last month's VAT rate"

    def test_accepts_exactly_the_maximum_length(self) -> None:
        assert len(Subject("a" * SUBJECT_MAX_LENGTH).value) == SUBJECT_MAX_LENGTH

    @pytest.mark.parametrize("value", ["", " ", "\t  "])
    def test_rejects_blank(self, value: str) -> None:
        with pytest.raises(InvalidValueError, match="blank"):
            Subject(value)

    def test_rejects_over_maximum_length(self) -> None:
        with pytest.raises(InvalidValueError, match="at most"):
            Subject("a" * (SUBJECT_MAX_LENGTH + 1))

    @pytest.mark.parametrize("value", ["Login fails\nafter reset", "Login fails\r\nafter reset"])
    def test_rejects_line_breaks(self, value: str) -> None:
        with pytest.raises(InvalidValueError, match="single line"):
            Subject(value)

    def test_equal_by_value(self) -> None:
        assert Subject("Export stuck at 99%") == Subject("Export stuck at 99%")


class TestDescription:
    def test_keeps_multiline_text(self) -> None:
        text = "Steps:\n1. Open Billing\n2. Click Download\n\nThe PDF still shows 19%."

        assert str(Description(text)) == text

    @pytest.mark.parametrize("value", ["", "\n\n", "   "])
    def test_rejects_blank(self, value: str) -> None:
        with pytest.raises(InvalidValueError, match="blank"):
            Description(value)

    def test_rejects_over_maximum_length(self) -> None:
        with pytest.raises(InvalidValueError, match="at most"):
            Description("a" * (DESCRIPTION_MAX_LENGTH + 1))
