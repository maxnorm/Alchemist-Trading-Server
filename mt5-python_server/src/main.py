from server import Server
from database import Database


def main():
    """Main"""
    server = Server('127.0.0.1', 1234)
    server.start()
    print("Server On")
    while True:
        msg = server.receive_msg()
        print(msg)


if __name__ == '__main__':
    main()
