import json
import os
import socket
import asyncio


class Connection:
    """
    Class to connect to MT5 terminal via socket
    """
    # Default timeout for socket operations (30 seconds)
    # Can be overridden with MT5_SOCKET_TIMEOUT environment variable
    DEFAULT_TIMEOUT = float(os.getenv('MT5_SOCKET_TIMEOUT', '30.0'))
    
    def __init__(self, socket, stop_char='\n', verbose=False, console_lock=None, timeout=None):
        self.__socket = socket
        self.__stop_char = stop_char
        self.__verbose = verbose
        self.__console_lock = console_lock
        self.__timeout = timeout or self.DEFAULT_TIMEOUT
        
        # Set socket timeout to prevent indefinite blocking
        try:
            self.__socket.settimeout(self.__timeout)
        except Exception:
            pass  # Socket might already be configured

    def send_msg(self, msg):
        """
        Send a message to the terminal via socket by adding the stop character to end the message
        :param msg: message to send
        """
        try:
            self.__socket.send(bytes(msg + self.__stop_char, 'utf-8'))
        except socket.timeout:
            raise TimeoutError(f"Timeout sending message to MT5 terminal after {self.__timeout}s")
        except Exception as e:
            raise ConnectionError(f"Error sending message to MT5 terminal: {e}")

    async def get_response(self, timeout=None):
        """
        Get the response in json format from MT5 terminal
        :param timeout: Optional timeout override (defaults to instance timeout)
        :return: Parsed JSON response
        :raises TimeoutError: If no response received within timeout
        :raises ConnectionError: If connection error occurs
        """
        response_timeout = timeout or self.__timeout
        
        try:
            # Use asyncio.wait_for to add timeout to the async operation
            return await asyncio.wait_for(
                self._receive_response(),
                timeout=response_timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Timeout waiting for response from MT5 terminal after {response_timeout}s. "
                f"The terminal may not be responding or the connection may be lost."
            )
        except socket.timeout:
            raise TimeoutError(
                f"Socket timeout waiting for response from MT5 terminal after {self.__timeout}s"
            )
        except Exception as e:
            raise ConnectionError(f"Error receiving response from MT5 terminal: {e}")

    async def _receive_response(self):
        """
        Internal method to receive response from socket
        """
        cum_data = ''
        loop = asyncio.get_event_loop()
        
        while True:
            # Run socket.recv in executor to make it non-blocking
            try:
                # Use run_in_executor to avoid blocking the event loop
                raw_data = await loop.run_in_executor(
                    None,
                    self.__socket.recv,
                    1024
                )
                
                if not raw_data:
                    raise ConnectionError("Connection closed by MT5 terminal")
                
                data = raw_data.decode("utf-8")
                cum_data += data
                
                if self.__stop_char in cum_data:
                    response_str = cum_data[:cum_data.index(self.__stop_char)]
                    try:
                        return json.loads(response_str)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON response from MT5 terminal: {e}")
            except socket.timeout:
                raise TimeoutError(f"Socket timeout after {self.__timeout}s")
            except OSError as e:
                if "timed out" in str(e).lower():
                    raise TimeoutError(f"Socket timeout after {self.__timeout}s")
                raise ConnectionError(f"Socket error: {e}")

    def __del__(self):
        try:
            self.__socket.close()
        except Exception:
            pass