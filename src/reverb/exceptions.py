"""Custom exceptions for Python Reverb."""


class ReverbError(Exception):
    """Base exception for all Reverb errors."""

    pass


class ConnectionError(ReverbError):
    """Failed to establish or maintain WebSocket connection."""

    pass


class AuthenticationError(ReverbError):
    """Channel authentication failed."""

    pass


class SubscriptionError(ReverbError):
    """Failed to subscribe to channel."""

    pass


class ProtocolError(ReverbError):
    """Invalid message or protocol violation."""

    pass


class TimeoutError(ReverbError):
    """Operation timed out."""

    pass
