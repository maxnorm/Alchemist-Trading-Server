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
    DEFAULT_TIMEOUT = float(os.getenv("MT5_SOCKET_TIMEOUT", "30.0"))

    def __init__(
        self, socket, stop_char="\n", verbose=False, console_lock=None, timeout=None
    ):
        self.__socket = socket
        self.__stop_char = stop_char
        self.__verbose = verbose
        self.__console_lock = console_lock
        self.__timeout = timeout or self.DEFAULT_TIMEOUT
        self.__created_at = __import__("time").time()
        self.__last_send_ts = None
        self.__last_recv_ts = None

        # Set socket timeout to prevent indefinite blocking
        try:
            self.__socket.settimeout(self.__timeout)
        except Exception:
            pass  # Socket might already be configured

        # Enable TCP keepalive to avoid silent idle disconnects
        try:
            self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "TCP_KEEPIDLE"):
                self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            if hasattr(socket, "TCP_KEEPINTVL"):
                self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 30)
            if hasattr(socket, "TCP_KEEPCNT"):
                self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 4)
        except Exception:
            pass  # Best effort; not all platforms support these

    def send_msg(self, msg):
        """
        Send a message to the terminal via socket by adding the stop character to end the message
        :param msg: message to send
        """
        # #region agent log
        try:
            import json as json_log
            import os
            import time as _t

            payload = {
                "sessionId": "debug-session",
                "runId": "run-debug",
                "hypothesisId": "H0",
                "location": "conn.py:send_msg",
                "message": "socket_state_before_send_msg",
                "data": {},
                "timestamp": int(_t.time() * 1000),
            }
            try:
                payload["data"]["gettimeout"] = self.__socket.gettimeout()
            except Exception as e:
                payload["data"]["gettimeout_error"] = str(e)
            try:
                payload["data"]["peer"] = str(self.__socket.getpeername())
            except Exception as e:
                payload["data"]["peer_error"] = str(e)
            try:
                payload["data"]["fileno"] = self.__socket.fileno()
            except Exception as e:
                payload["data"]["fileno_error"] = str(e)
            for dest in [
                r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log",
                os.path.join(os.getenv("LOG_DIR", "/app/logs"), "debug.log"),
            ]:
                try:
                    with open(dest, "a") as f:
                        f.write(json_log.dumps(payload) + "\n")
                except Exception:  # pragma: no cover
                    pass
        except Exception:  # pragma: no cover
            pass
        # #endregion
        # #region agent log
        try:
            import json as json_log
            import os
            import time as _t

            payload = {
                "sessionId": "debug-session",
                "runId": "run-debug",
                "hypothesisId": "H1",
                "location": "conn.py:send_msg",
                "message": "about_to_send_msg",
                "data": {"preview": msg[:150]},
                "timestamp": int(_t.time() * 1000),
            }
            try:
                host_log = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                with open(host_log, "a") as f:
                    f.write(json_log.dumps(payload) + "\n")
            except Exception:  # pragma: no cover
                pass
            try:
                log_path = os.path.join(os.getenv("LOG_DIR", "/app/logs"), "debug.log")
                with open(log_path, "a") as f:
                    f.write(json_log.dumps(payload) + "\n")
            except Exception:  # pragma: no cover
                pass
        except Exception:  # pragma: no cover - best effort instrumentation
            pass
        # #endregion
        self.__last_send_ts = __import__("time").time()
        # #region agent log
        try:
            import json
            import os

            log_path = os.path.join(os.getenv("LOG_DIR", "/app/logs"), "debug.log")
            with open(log_path, "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "conn.py:28",
                            "message": "send_msg entry",
                            "data": {
                                "msg_len": len(msg),
                                "socket_fileno": (
                                    self.__socket.fileno()
                                    if hasattr(self.__socket, "fileno")
                                    else None
                                ),
                            },
                            "timestamp": int(__import__("time").time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        # #region agent log
        try:
            import json
            import os

            sock_state = {"closed": False, "timeout": None}
            try:
                sock_state["timeout"] = self.__socket.gettimeout()
            except Exception:
                pass
            try:
                self.__socket.getpeername()
            except Exception as e:
                sock_state["closed"] = True
                sock_state["error"] = str(e)
            log_path = os.path.join(os.getenv("LOG_DIR", "/app/logs"), "debug.log")
            with open(log_path, "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "conn.py:28",
                            "message": "socket state before send",
                            "data": sock_state,
                            "timestamp": int(__import__("time").time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        try:
            self.__socket.send(bytes(msg + self.__stop_char, "utf-8"))
            self.__last_send_ts = __import__("time").time()
            # #region agent log
            try:
                import json
                import os

                log_path = os.path.join(os.getenv("LOG_DIR", "/app/logs"), "debug.log")
                with open(log_path, "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "A",
                                "location": "conn.py:28",
                                "message": "send_msg success",
                                "data": {"bytes_sent": len(msg + self.__stop_char)},
                                "timestamp": int(__import__("time").time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
        except socket.timeout:
            # #region agent log
            try:
                import json
                import os

                log_path = os.path.join(os.getenv("LOG_DIR", "/app/logs"), "debug.log")
                with open(log_path, "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "C",
                                "location": "conn.py:28",
                                "message": "send_msg timeout",
                                "data": {},
                                "timestamp": int(__import__("time").time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
            raise TimeoutError(
                f"Timeout sending message to MT5 terminal after {self.__timeout}s"
            )
        except Exception as e:
            # #region agent log
            try:
                import json
                import os
                import time as _t

                data = {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "uptime_s": round(__import__("time").time() - self.__created_at, 3),
                    "last_send_delta_s": (
                        round((__import__("time").time() - self.__last_send_ts), 3)
                        if self.__last_send_ts
                        else None
                    ),
                    "last_recv_delta_s": (
                        round((__import__("time").time() - self.__last_recv_ts), 3)
                        if self.__last_recv_ts
                        else None
                    ),
                }
                payload = {
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "B",
                    "location": "conn.py:28",
                    "message": "send_msg exception",
                    "data": data,
                    "timestamp": int(_t.time() * 1000),
                }
                try:
                    log_path = os.path.join(
                        os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                    )
                    with open(log_path, "a") as f:
                        f.write(json.dumps(payload) + "\n")
                except Exception:
                    pass
                try:
                    host_log = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                    with open(host_log, "a") as f:
                        f.write(json.dumps(payload) + "\n")
                except Exception:
                    pass
            except Exception:
                pass
            # #endregion
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
                self._receive_response(), timeout=response_timeout
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
        # #region agent log
        try:
            import json as json_log
            import os
            import time as _t

            payload = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "E",
                "location": "conn.py:117",
                "message": "_receive_response entry",
                "data": {},
                "timestamp": int(_t.time() * 1000),
            }
            try:
                log_path = os.path.join(os.getenv("LOG_DIR", "/app/logs"), "debug.log")
                with open(log_path, "a") as f:
                    f.write(json_log.dumps(payload) + "\n")
            except Exception:
                pass
            try:
                host_log = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                with open(host_log, "a") as f:
                    f.write(json_log.dumps(payload) + "\n")
            except Exception:
                pass
        except Exception:
            pass
        # #endregion
        # #region agent log
        try:
            import json as json_log
            import time as _t

            log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
            sock_state = {
                "fileno": (
                    self.__socket.fileno() if hasattr(self.__socket, "fileno") else None
                )
            }
            with open(log_path, "a") as f:
                f.write(
                    json_log.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run-debug",
                            "hypothesisId": "H2",
                            "location": "conn.py:_receive_response",
                            "message": "enter_receive_response",
                            "data": sock_state,
                            "timestamp": int(_t.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:  # pragma: no cover
            pass
        # #endregion
        cum_data = ""
        loop = asyncio.get_event_loop()

        while True:
            # Run socket.recv in executor to make it non-blocking
            try:
                # #region agent log
                try:
                    import json as json_log
                    import os

                    log_path = os.path.join(
                        os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                    )
                    with open(log_path, "a") as f:
                        f.write(
                            json_log.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "E",
                                    "location": "conn.py:117",
                                    "message": "_receive_response before recv",
                                    "data": {},
                                    "timestamp": int(__import__("time").time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion
                # Use run_in_executor to avoid blocking the event loop
                raw_data = await loop.run_in_executor(None, self.__socket.recv, 1024)

                # #region agent log
                try:
                    import json as json_log
                    import os

                    log_path = os.path.join(
                        os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                    )
                    with open(log_path, "a") as f:
                        f.write(
                            json_log.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "E",
                                    "location": "conn.py:117",
                                    "message": "_receive_response after recv",
                                    "data": {
                                        "raw_data_len": len(raw_data) if raw_data else 0
                                    },
                                    "timestamp": int(__import__("time").time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion

                if not raw_data:
                    # #region agent log
                    try:
                        import json as json_log
                        import os
                        import time as _t

                        payload = {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "F",
                            "location": "conn.py:117",
                            "message": "_receive_response empty data",
                            "data": {},
                            "timestamp": int(_t.time() * 1000),
                        }
                        try:
                            log_path = os.path.join(
                                os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                            )
                            with open(log_path, "a") as f:
                                f.write(json_log.dumps(payload) + "\n")
                        except Exception:
                            pass
                        try:
                            host_log = (
                                r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                            )
                            with open(host_log, "a") as f:
                                f.write(json_log.dumps(payload) + "\n")
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # #endregion
                    # #region agent log (socket state on empty read)
                    try:
                        import json as json_log
                        import time as _t

                        sock_state = {
                            "fileno": (
                                self.__socket.fileno()
                                if hasattr(self.__socket, "fileno")
                                else None
                            )
                        }
                        payload = {
                            "sessionId": "debug-session",
                            "runId": "run-debug",
                            "hypothesisId": "H2",
                            "location": "conn.py:_receive_response",
                            "message": "empty_raw_data_connection_closed",
                            "data": sock_state,
                            "timestamp": int(_t.time() * 1000),
                        }
                        for dest in [
                            r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log",
                            os.path.join(
                                os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                            ),
                        ]:
                            try:
                                with open(dest, "a") as f:
                                    f.write(json_log.dumps(payload) + "\n")
                            except Exception:  # pragma: no cover
                                pass
                    except Exception:  # pragma: no cover
                        pass
                    # #endregion
                    # If we have partial data accumulated, try to parse before failing
                    if cum_data:
                        try:
                            parsed = json.loads(cum_data)
                            return parsed
                        except Exception:
                            pass
                    raise ConnectionError("Connection closed by MT5 terminal")

                data = raw_data.decode("utf-8")
                cum_data += data

                if self.__stop_char not in cum_data:
                    # #region agent log
                    try:
                        import json as json_log
                        import time as _t

                        payload = {
                            "sessionId": "debug-session",
                            "runId": "run-debug",
                            "hypothesisId": "H5",
                            "location": "conn.py:_receive_response",
                            "message": "stop_char_not_found_yet",
                            "data": {
                                "cum_len": len(cum_data),
                                "preview": cum_data[:120],
                            },
                            "timestamp": int(_t.time() * 1000),
                        }
                        for dest in [
                            r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log",
                            os.path.join(
                                os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                            ),
                        ]:
                            try:
                                with open(dest, "a") as f:
                                    f.write(json_log.dumps(payload) + "\n")
                            except Exception:  # pragma: no cover
                                pass
                    except Exception:  # pragma: no cover
                        pass
                    # #endregion
                    continue
                self.__last_recv_ts = __import__("time").time()

                if self.__stop_char in cum_data:
                    response_str = cum_data[: cum_data.index(self.__stop_char)]
                    # #region agent log
                    try:
                        import json as json_log
                        import os

                        log_path = os.path.join(
                            os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                        )
                        with open(log_path, "a") as f:
                            f.write(
                                json_log.dumps(
                                    {
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "E",
                                        "location": "conn.py:117",
                                        "message": "_receive_response complete",
                                        "data": {
                                            "response_preview": response_str[:100]
                                        },
                                        "timestamp": int(
                                            __import__("time").time() * 1000
                                        ),
                                    }
                                )
                                + "\n"
                            )
                    except Exception:
                        pass
                    # #endregion
                    # #region agent log
                    try:
                        import json as json_log
                        import os
                        import time as _t

                        payload = {
                            "sessionId": "debug-session",
                            "runId": "run-debug",
                            "hypothesisId": "H6",
                            "location": "conn.py:_receive_response",
                            "message": "stop_char_found",
                            "data": {"response_preview": response_str[:150]},
                            "timestamp": int(_t.time() * 1000),
                        }
                        for dest in [
                            os.path.join(
                                os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                            ),
                            r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log",
                        ]:
                            try:
                                with open(dest, "a") as f:
                                    f.write(json_log.dumps(payload) + "\n")
                            except Exception:
                                pass
                    except Exception:  # pragma: no cover
                        pass
                    # #endregion
                    try:
                        parsed = json.loads(response_str)
                        # #region agent log
                        try:
                            import json as json_log
                            import os

                            sock_state = {"closed": False, "timeout": None}
                            try:
                                sock_state["timeout"] = self.__socket.gettimeout()
                            except Exception:
                                pass
                            try:
                                self.__socket.getpeername()
                            except Exception as e:
                                sock_state["closed"] = True
                                sock_state["error"] = str(e)
                            log_path = os.path.join(
                                os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                            )
                            with open(log_path, "a") as f:
                                f.write(
                                    json_log.dumps(
                                        {
                                            "sessionId": "debug-session",
                                            "runId": "run1",
                                            "hypothesisId": "G",
                                            "location": "conn.py:117",
                                            "message": "_receive_response socket state after response",
                                            "data": sock_state,
                                            "timestamp": int(
                                                __import__("time").time() * 1000
                                            ),
                                        }
                                    )
                                    + "\n"
                                )
                        except Exception:
                            pass
                        # #endregion
                        return parsed
                    except json.JSONDecodeError as e:
                        # #region agent log
                        try:
                            import json as json_log
                            import os
                            import time as _t

                            payload = {
                                "sessionId": "debug-session",
                                "runId": "run-debug",
                                "hypothesisId": "H3",
                                "location": "conn.py:_receive_response",
                                "message": "json_decode_error",
                                "data": {
                                    "error": str(e),
                                    "response_preview": response_str[:200],
                                },
                                "timestamp": int(_t.time() * 1000),
                            }
                            try:
                                host_log = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                                with open(host_log, "a") as f:
                                    f.write(json_log.dumps(payload) + "\n")
                            except Exception:
                                pass
                            try:
                                log_path = os.path.join(
                                    os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                                )
                                with open(log_path, "a") as f:
                                    f.write(json_log.dumps(payload) + "\n")
                            except Exception:
                                pass
                        except Exception:  # pragma: no cover
                            pass
                        # #endregion
                        raise ValueError(
                            f"Invalid JSON response from MT5 terminal: {e}"
                        )
                else:
                    # #region agent log
                    try:
                        import json as json_log
                        import os
                        import time as _t

                        payload = {
                            "sessionId": "debug-session",
                            "runId": "run-debug",
                            "hypothesisId": "H5",
                            "location": "conn.py:_receive_response",
                            "message": "chunk_without_stop_char",
                            "data": {
                                "chunk_len": len(data),
                                "chunk_preview": data[:150],
                                "cum_len": len(cum_data),
                            },
                            "timestamp": int(_t.time() * 1000),
                        }
                        for dest in [
                            os.path.join(
                                os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                            ),
                            r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log",
                        ]:
                            try:
                                with open(dest, "a") as f:
                                    f.write(json_log.dumps(payload) + "\n")
                            except Exception:
                                pass
                    except Exception:  # pragma: no cover
                        pass
                    # #endregion
            except socket.timeout:
                # #region agent log
                try:
                    import json as json_log
                    import os

                    log_path = os.path.join(
                        os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                    )
                    with open(log_path, "a") as f:
                        f.write(
                            json_log.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "F",
                                    "location": "conn.py:117",
                                    "message": "_receive_response timeout",
                                    "data": {},
                                    "timestamp": int(__import__("time").time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion
                raise TimeoutError(f"Socket timeout after {self.__timeout}s")
            except OSError as e:
                # #region agent log
                try:
                    import json as json_log
                    import os

                    log_path = os.path.join(
                        os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                    )
                    with open(log_path, "a") as f:
                        f.write(
                            json_log.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "F",
                                    "location": "conn.py:117",
                                    "message": "_receive_response OSError",
                                    "data": {"error": str(e)},
                                    "timestamp": int(__import__("time").time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion
                if "timed out" in str(e).lower():
                    raise TimeoutError(f"Socket timeout after {self.__timeout}s")
                raise ConnectionError(f"Socket error: {e}")

    def __del__(self):
        try:
            self.__socket.close()
        except Exception:
            pass

    # Utility accessors for health checks
    def is_alive(self) -> bool:
        try:
            self.__socket.getpeername()
            return True
        except Exception:
            return False

    def last_recv_ts(self):
        return self.__last_recv_ts

    def last_send_ts(self):
        return self.__last_send_ts
