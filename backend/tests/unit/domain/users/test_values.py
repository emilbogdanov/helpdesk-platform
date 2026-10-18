import pytest

from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.users.values import (
    DISPLAY_NAME_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    DisplayName,
    EmailAddress,
    Password,
)


class TestEmailAddress:
    def test_is_normalised_to_lowercase_without_surrounding_spaces(self) -> None:
        assert str(EmailAddress("  Mila.Georgieva@Northwind.BG ")) == "mila.georgieva@northwind.bg"

    def test_different_spellings_of_one_address_are_equal(self) -> None:
        assert EmailAddress("Mila@Northwind.bg") == EmailAddress("mila@northwind.bg")

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "mila",
            "mila@",
            "@northwind.bg",
            "mila@northwind",
            "mila@northwind.",
            "mila@.bg",
            "mila georgieva@northwind.bg",
        ],
    )
    def test_rejects_malformed_addresses(self, value: str) -> None:
        with pytest.raises(InvalidValueError, match="must look like"):
            EmailAddress(value)

    def test_rejects_over_maximum_length(self) -> None:
        local = "a" * (EMAIL_MAX_LENGTH - len("@northwind.bg") + 1)

        with pytest.raises(InvalidValueError, match="at most"):
            EmailAddress(f"{local}@northwind.bg")


class TestDisplayName:
    def test_keeps_the_name_as_written(self) -> None:
        assert str(DisplayName("Mila Georgieva")) == "Mila Georgieva"

    @pytest.mark.parametrize("value", ["", "   "])
    def test_rejects_blank(self, value: str) -> None:
        with pytest.raises(InvalidValueError, match="blank"):
            DisplayName(value)

    def test_rejects_line_breaks(self) -> None:
        with pytest.raises(InvalidValueError, match="single line"):
            DisplayName("Mila\nGeorgieva")

    def test_rejects_over_maximum_length(self) -> None:
        with pytest.raises(InvalidValueError, match="at most"):
            DisplayName("a" * (DISPLAY_NAME_MAX_LENGTH + 1))


class TestPassword:
    @pytest.mark.parametrize("length", [PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH])
    def test_accepts_lengths_at_the_limits(self, length: int) -> None:
        assert Password("p" * length).value == "p" * length

    @pytest.mark.parametrize("length", [PASSWORD_MIN_LENGTH - 1, PASSWORD_MAX_LENGTH + 1])
    def test_rejects_lengths_outside_the_limits(self, length: int) -> None:
        with pytest.raises(InvalidValueError, match="password must be"):
            Password("p" * length)

    def test_never_shows_up_in_logs(self) -> None:
        password = Password("correct horse battery")

        assert "correct horse" not in repr(password)
        assert "correct horse" not in str(password)
