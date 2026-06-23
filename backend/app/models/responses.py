from typing import Literal

from pydantic import BaseModel


class StartEvent(BaseModel):
    type: Literal["start"] = "start"
    response_type: Literal["report", "chat", "failure"]


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    message: str


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    data: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: int
    message: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"


SSEEvent = StartEvent | StatusEvent | TokenEvent | ErrorEvent | DoneEvent