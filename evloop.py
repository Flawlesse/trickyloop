from selectors import BaseSelector
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
        self.current_result = None  # idk why is it here
        self.completed_tasks = dict()

    def _register_socket_to_read(self, sock: socket.socket, callback: Callable):
        """Bind socket READ event to the callback that would resolve Future bound to it.\n
        Returns newly created Future, representing result of read event happening."""

        future = CustomFuture()

        try:
            self.selector.get_key(sock)
        except KeyError:
            # socket is new (non-registered before)
            # assign a callback-future pair
            sock.setblocking(False)
            self.selector.register(sock, selectors.EVENT_READ, functools.partial(callback, future))
        else:
            # socket is reused, register a new callback-future pairs
            self.selector.modify(sock, selectors.EVENT_READ, functools.partial(callback, future))

        return future

    def _set_current_result(self, result):
        self.current_result = result

    async def sock_recv(self, sock):
        print("Регистрируется сокет для прослушивания данных...")
        return await self._register_socket_to_read(sock, self.recieved_data)

    async def sock_accept(self, sock):
        print("Регистрируется сокет для приема подключений...")
        return await self._register_socket_to_read(sock, self.accept_connection)

    def sock_close(self, sock):
        # socket is unneeded
        # unregister and close
        self.selector.unregister(sock)
        sock.close()

    def register_task(self, task):
        self._tasks_to_run.append(task)

    def recieved_data(self, future: CustomFuture, sock):
        """Callback for selector READ event.\n
        Make socket .recv() bytes read and set result to the bound future."""
        data = sock.recv(1024)
        future.set_result(data)

    def accept_connection(self, future: CustomFuture, sock):
        """Callback for selector READ event. \n
        Make socket .accept() bytes read and set result to the bound future."""
        result = sock.accept()
        future.set_result(result)

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
    assert seconds >= 0
    return await Timer(seconds)


async def count(n):
    c = 0
    for i in range(n):
        c += i
        await sleep(1)
        print(i)
    return c


async def main(loop):
    t1 = CustomTask(count(10), loop)
    t2 = CustomTask(count(15), loop)
    print(await t1)
    print(await t2)


if __name__ == "__main__":
    _loop = EventLoop()
    res = _loop.run(main(_loop))
    print(f"main() finished with result = {res}")
