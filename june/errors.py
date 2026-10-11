"""Provider-neutral inference failure."""


class BrainUnavailable(RuntimeError):
    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after
