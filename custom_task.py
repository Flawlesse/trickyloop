from custom_future import CustomFuture
from uuid import uuid1
import time


class CustomTask(CustomFuture):
    def __init__(self, coro, loop):
        super().__init__()
        self._coro = coro
        self._loop = loop
        self._curr_future: CustomFuture | None = None
        self.id = uuid1()
        loop.register_task(self)

    def step(self, result=None):
        try:
            self._curr_future = self._coro.send(result)
        except StopIteration as si:
            self.set_result(si.value)

    def __repr__(self):
        return f"CustomTask[{self.id[:5]}...{self.id[:-5]}] at <{id(self)}>"


class Timer(CustomFuture):
    def __init__(self, seconds: float):
        super().__init__()
        self._end_time = time.time() + seconds
        self._sleep_time = seconds
        self.add_done_callback(self._notify_awake)

    def _manage(self):
        """Event-Loop related method, that manages timer's underlying future."""

        if self._end_time <= time.time():
            self.set_result(None)

    def _notify_awake(self, result):
        print(f"Good god! Timer ended in {self._sleep_time} seconds! Result of future: {result}.")
