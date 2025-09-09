from typing import Callable
import socket
import functools
import selectors
import time
from custom_future import CustomFuture
from custom_task import CustomTask, Timer


_loop = None


class EventLoop:
    _tasks_to_run: list[CustomTask] = []

    def __init__(self):
        self.selector = selectors.DefaultSelector()
        self.completed_tasks = dict()

    def _register_socket(
        self,
        sock: socket.socket,
        callback: Callable,
        selector_events,
    ):
        """Bind socket (R/W) events to the callback that would resolve Future bound to it.\n
        Returns newly created Future, representing result of event happening."""

        # So, the flow goes like this:
        # 1. Somehow, this method is called. It registeres the socket in the Selector.
        # 2. Then, once it registered a non-blocking socket, it creates a Future,
        #    which then binds to a callback -- it will be called to resolve the Future
        #    setting its result to something. Now, when is this callback being called?
        # 3. The callback was REGISTERED before, so once EventLoop reaches the Selector
        #    polling stage, then all the callbacks will be called one by one for each event.
        # 4. This gets our Future (the one we returned) resolved! Now it has value!
        # 5. The new iteration of EventLoop happens. Now, EventLoop polls all the running
        #    tasks for their Futures (task._current_future) resolution. It finds out that
        #    our Future has been resolved and that's why it triggers coro.send(Future.result()).
        # 6. Repeat the whole thing. It's gorgeous.

        future = CustomFuture()

        try:
            self.selector.get_key(sock)
        except KeyError:
            # socket is new (non-registered before)
            # assign a callback-future pair
            sock.setblocking(False)
            self.selector.register(sock, selector_events, functools.partial(callback, future))
        else:
            # socket is reused, register a new callback-future pairs
            self.selector.modify(sock, selector_events, functools.partial(callback, future))

        return future

    async def sock_recv(self, sock):
        print("Регистрируется сокет для прослушивания данных...")
        return await self._register_socket(sock, self.recieve_data, selectors.EVENT_READ)

    async def sock_accept(self, sock):
        print("Регистрируется сокет для приема подключений...")
        return await self._register_socket(sock, self.accept_connection, selectors.EVENT_READ)

    def sock_close(self, sock):
        """Once socket is unneeded, unregister and close it."""
        self.selector.unregister(sock)
        sock.close()

    def recieve_data(self, future: CustomFuture, sock: socket.socket):
        """Callback for selector READ event.\n
        Make socket .recv() bytes read and set result to the bound future.\n
        Essentially, just an await-compatible wrapper around `sock.recv()`"""
        data = sock.recv(1024)
        future.set_result(data)

    def accept_connection(self, future: CustomFuture, sock: socket.socket):
        """Callback for selector READ event. \n
        Make socket .accept() bytes read and set result to the bound future.\n
        Essentially, just an await-compatible wrapper around `sock.accept()`"""
        result = sock.accept()
        future.set_result(result)

    def register_task(self, task):
        self._tasks_to_run.append(task)

    def run(self, coro):
        self._main_coro = coro
        self._main_task = CustomTask(coro, self)

        while True:
            for task in self._tasks_to_run:
                # Если задача запускается впервые -- у неё ещё нет _curr_future.
                if task._curr_future is None:
                    task.step()
                    continue
                # Если результат -- неразрешённый таймер, значит цикл событий САМ им управляет
                if isinstance(task._curr_future, Timer):
                    task._curr_future._manage()
                # Нужно проверить, готова ли задача к шагу (есть ли результат для её Future)
                # И ОБЯЗАТЕЛЬНО проверить, завершена ли корутина! Если да -- не важно, что у неё
                # разрешённое промежуточное состояние (Future), ей отсылать уже НИЧЕГО НЕ НАДО.
                if task._curr_future.is_finished() and not task.is_finished():
                    task.step(task._curr_future.result())

            # 2. Обрабатываем IO события
            events = self.selector.select(timeout=0)  # Неблокирующий опрос
            for key, _ in events:
                callback = key.data
                callback(key.fileobj)

            # 3. Убираем завершенные задачи
            self.completed_tasks.update(
                {task.id: task.result() for task in self._tasks_to_run if task.is_finished()}
            )
            self._tasks_to_run = [task for task in self._tasks_to_run if not task.is_finished()]

            # 4. Если главная корутина завершена - выходим
            if self._main_task.is_finished():
                return self._main_task.result()

            # 5. Короткая пауза, чтобы не грузить CPU впустую
            time.sleep(0.001)


async def sleep(seconds: float):
    """EventLoop implementation of asyncio.sleep()"""

    assert seconds >= 0
    return await Timer(seconds)


def get_running_loop() -> EventLoop:
    global _loop

    if _loop:
        return _loop
    raise ValueError("No EventLoop is set!")


def set_event_loop(loop: EventLoop):
    global _loop

    _loop = loop
