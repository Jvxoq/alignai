from typing import Literal

from pydantic import BaseModel


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    message: str


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    content: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    report: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


SSEEvent = StatusEvent | TokenEvent | DoneEvent | ErrorEvent
