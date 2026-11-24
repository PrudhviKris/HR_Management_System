from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

T = TypeVar("T")

# Decimals serialised as JSON numbers (rounded to 2 places) instead of strings
Money = Annotated[Decimal, PlainSerializer(lambda v: float(round(v, 2)) if v is not None else None, return_type=float)]
Days = Annotated[Decimal, PlainSerializer(lambda v: float(v) if v is not None else None, return_type=float)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StrictInput(BaseModel):
    """Base for request bodies: unknown fields rejected, strings trimmed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class Message(BaseModel):
    message: str


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


def not_blank(v: str | None) -> str | None:
    if v is not None and not v.strip():
        raise ValueError("must not be blank")
    return v


class IdName(ORMModel):
    id: int
    name: str

