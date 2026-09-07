from dataclasses import dataclass
from enum import Enum
from typing import Optional





# Теперь можно наследоваться от BaseMetricType
class CounterType(Enum):
    """Типы счетчиков (monotonic counters)."""
    REQUESTS = "http.server.requests"
    ERRORS = "http.server.errors"
    ACTIVE = "http.server.active"

    @property
    def description(self) -> str:
        descriptions = {
            "http.server.requests": "Total number of HTTP requests",
            "http.server.errors": "Total number of HTTP errors",
            "http.server.active": "Number of active HTTP requests",
        }
        return descriptions.get(self.value)

    @property
    def unit(self) -> str:
        units = {
            "http.server.requests": "1",
            "http.server.errors": "1",
            "http.server.active": "1",
        }
        return units.get(self.value)


class HistogramType(Enum):
    """Типы гистограмм."""
    DURATION = "http.server.duration"
    SIZE = "http.server.request_size"

    @property
    def description(self) -> str:
        descriptions = {
            "http.server.duration": "Duration of HTTP requests in seconds",
            "http.server.request_size": "Size of HTTP requests in bytes",
        }
        return descriptions.get(self.value)

    @property
    def unit(self) -> str:
        units = {
            "http.server.duration": "s",
            "http.server.request_size": "bytes",
        }
        return units.get(self.value)

@dataclass
class Tags:
    route: Optional[str] = None
    status_code: Optional[str] = None
    method: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}