from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"
    ADMIN = "admin"

    @property
    def is_staff(self) -> bool:
        return self is not Role.CUSTOMER
