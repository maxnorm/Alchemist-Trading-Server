import asyncio


class Account:
    """
    Class for an account
    """

    def __init__(self, terminal):
        self.__terminal = terminal

        self.login = None
        self.balance = None
        self.currency = None
        self.current_trade = []

    def __set_account_infos(self):
        """
        Set the account infos by getting them from the terminal
        """
        res = asyncio.run(self.__terminal.get_all_infos())
        self.login = res[0]
        self.balance = res[1]
        self.currency = res[2]


