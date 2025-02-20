#!/usr/bin/env python3
"""Merci encore d’avoir répondu à ma question au forum
Main
"""
import os
import argparse
from datetime import datetime
from dotenv import load_dotenv

from server import Server

def parse_arguments():
    """
    Parse the arguments form terminal
    """
    parser = argparse.ArgumentParser(
        description='Server with database to connect with MT5',
        epilog=f'{datetime.now().year}, Alchemist Capital')
    parser.add_argument('-v', '--verbose', action='store_true', help="Activate the verbose mode on the server")
    args = parser.parse_args()
    return args


def start():
    """Start the program"""
    args = parse_arguments()
    load_dotenv()
    Server(verbose=args.verbose)


if __name__ == '__main__':
    start()
