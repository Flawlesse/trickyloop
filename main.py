from evloop import EventLoop, sleep, get_running_loop, set_event_loop
from custom_task import CustomTask
import socket


###### TEST CASE 1  #########
async def count(n):
    c = 0
    for i in range(n):
        c += i
        await sleep(1)
        print(i)
    return c


def test_case1():
    async def main(loop):
        t1 = CustomTask(count(10), loop)
        t2 = CustomTask(count(15), loop)
        print("t1 result: ", await t1)
        print("t2 result: ", await t2)

    set_event_loop(EventLoop())
    loop = get_running_loop()
    res = loop.run(main(loop))
    print(f"main() finished with result = {res}")
    print(f"loop info: \n{loop._tasks_to_run=}\n{loop.completed_tasks}")


####### TEST CASE 2 #########
async def read_from_client(conn, loop: EventLoop):
    """Background CLI for each client conneciton."""

    print(f"Чтение данных от клиента {conn}")
    try:
        while data := await loop.sock_recv(conn):
            print(f"Получены данные {data} от клиента!")
    finally:
        print(f"Client socket {conn} was closed!")
        loop.sock_close(conn)


async def listen_for_connections(server_sock: socket.socket, loop: EventLoop):
    """
    So, we use server socket as a mean of communication for listening on new connections.\n
    Once we got one, the NEW socket is created to serve CLI for client.\n
    Thus called client socket.
    """

    while True:
        print("Ожидание подключения...")
        conn, addr = await loop.sock_accept(server_sock)
        # create background task to handle each client connection
        CustomTask(read_from_client(conn, loop), loop)
        print(f"Новое подключение к сокету {server_sock}!")


def test_case2():
    async def main(loop):
        server_socket = socket.socket()
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("127.0.0.1", 8000))
        server_socket.listen()
        server_socket.setblocking(False)
        await listen_for_connections(server_socket, loop)

    set_event_loop(EventLoop())
    loop = get_running_loop()
    res = loop.run(main(loop))
    print(f"main() finished with result = {res}")
    print(f"loop info: \n{loop._tasks_to_run=}\n{loop.completed_tasks}")


if __name__ == "__main__":
    # test_case1()
    test_case2()
