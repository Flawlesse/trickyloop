class CustomFuture:
    def __init__(self):
        self._result = None
        self._is_finished = False
        self._done_callbacks = []

    def result(self):
        return self._result

    def is_finished(self):
        return self._is_finished

    def set_result(self, result):
        self._result = result
        self._is_finished = True
        # notify all
        if self._done_callbacks:
            [cb(result) for cb in self._done_callbacks]

    def add_done_callback(self, fn):
        self._done_callbacks.append(fn)

    def __await__(self):
        if not self._is_finished:
            yield self
        return self.result()

    def __repr__(self):
        return f"CustomFuture[{self.id[:5]}...{self.id[:-5]}] at <{id(self)}>"
