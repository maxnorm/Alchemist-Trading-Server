#!/usr/bin/env python3
"""
Main
"""
import os
import argparse
from dotenv import load_dotenv

from server import Server

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))

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
    """Start the program"""
    args = parse_arguments()
    load_dotenv(env_path)
    Server(verbose=args.verbose)


if __name__ == '__main__':
    start()
