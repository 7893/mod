"""Read-only live business projection for dashboard presentation."""

from .broker import LiveProjectionBroker, get_live_projection_broker

__all__ = ["LiveProjectionBroker", "get_live_projection_broker"]
