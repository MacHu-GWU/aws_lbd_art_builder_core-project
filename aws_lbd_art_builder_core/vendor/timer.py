# -*- coding: utf-8 -*-

"""
Simple time profiling tools.
"""

from datetime import datetime, timezone

__version__ = "0.1.1"

default_log_message_template = (
    "from {start_time} to {end_time} elapsed {elapsed:.6f} second."
)


class BaseTimer:
    """
    Abstract timer class.
    """

    _base_log_msg_tpl = "from {start_time} to {end_time} elapsed {elapsed:.6f} second."

    def __init__(
        self,
        title: str = None,
        verbose: bool = True,
        start: bool = True,
    ):
        self.title = title
        self.start_time = None
        self.end_time = None
        self.elapsed = None
        self.verbose = verbose

        if title is not None:
            self.log_msg_tpl = title + ": " + default_log_message_template
        else:
            self.log_msg_tpl = default_log_message_template

        if start is True:
            self.start()

    def __str__(self):
        return self.log_msg_tpl.format(
            start_time=self.start_time,
            end_time=self.end_time,
            elapsed=self.elapsed,
        )

    def __repr__(self):
        if self.elapsed is not None:
            return "Timer(title=%s, elapsed=%.6f)" % (self.title, self.elapsed)
        else:
            return "Timer(title=%s)" % self.title

    def _get_current_time(self):
        raise NotImplementedError

    def _get_delta_in_sec(self, start, end) -> float:
        raise NotImplementedError

    def start(self):
        self.start_time = self._get_current_time()

    def end(self):
        self.end_time = self._get_current_time()
        self.elapsed = self._get_delta_in_sec(self.start_time, self.end_time)
        if self.verbose:
            print(self)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.end()


class DateTimeTimer(BaseTimer):
    """
    Usage::

        # usage 1
        >>> timer = DateTimeTimer(title="first measure") # start measuring immediately, title is optional
        >>> # .. do something
        >>> timer.end()

        # usage 2
        >>> with DateTimeTimer(title="second measure") as timer:
        ...     # do something
        >>> timer.end()

        # usage 3
        >>> timer = DateTimeTimer(start=False) # not start immediately
        >>> # do something
        >>> timer.start()
        >>> # do someting
        >>> timer.end()

        # usage 4
        >>> timer = DateTimeTimer(display=False) # disable auto display information

    .. warning::

        DateTimeTimer takes around 0.003 seconds to get the time.
    """

    def _get_current_time(self):
        return datetime.now(tz=timezone.utc)

    def _get_delta_in_sec(self, start, end):
        return (end - start).total_seconds()


if __name__ == "__main__":
    import uuid

    def my_func():
        n = 1_000
        for _ in range(n):
            uuid.uuid4()

    with DateTimeTimer(title="my function") as timer:
        my_func()
    print(f"{timer.elapsed = }")
