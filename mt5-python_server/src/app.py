"""
Main
"""
import argparse

from server import Server


def parse_arguments():
    """
    Parse the arguments form terminal
    """
    parser = argparse.ArgumentParser(
        description='Server with database to connect with MT5',
        epilog='2023, Alchemist Capital Management')
    parser.add_argument('-v', '--verbose', action='store_true', help="Activate the verbose mode on the server")
    args = parser.parse_args()
    return args


def start():
    """Main"""
    args = parse_arguments()
    Server(verbose=args.verbose)


if __name__ == '__main__':
    start()
