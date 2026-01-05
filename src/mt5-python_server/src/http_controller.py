"""
HTTP Controller for handling HTTP requests in the MT5 server

This controller handles HTTP and HTTPS requests (like Prometheus metrics scraping)
that come through the same socket as MT5 connections.
"""

import os
import socket
import ssl
from typing import Tuple, Optional, Union
from utils.time_utils import print_with_datetime


class HTTPRequest:
    """Represents a parsed HTTP request"""
    
    def __init__(self, method: str, path: str, headers: dict, body: str = ""):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body


class HTTPResponse:
    """Represents an HTTP response"""
    
    def __init__(self, status_code: int, status_text: str, headers: dict = None, body: bytes = b""):
        self.status_code = status_code
        self.status_text = status_text
        self.headers = headers or {}
        self.body = body
    
    def to_bytes(self) -> bytes:
        """Convert HTTP response to bytes for sending over socket"""
        response = f"HTTP/1.1 {self.status_code} {self.status_text}\r\n"
        
        # Add headers
        for key, value in self.headers.items():
            response += f"{key}: {value}\r\n"
        
        # Add content length if body exists
        if self.body:
            response += f"Content-Length: {len(self.body)}\r\n"
        
        # Add connection close header
        response += "Connection: close\r\n"
        
        # End headers
        response += "\r\n"
        
        # Add body
        result = response.encode("utf-8")
        if self.body:
            result += self.body
        
        return result


class HTTPController:
    """
    Controller for handling HTTP and HTTPS requests
    
    Routes HTTP/HTTPS requests to appropriate handlers and manages responses.
    Supports both plain HTTP and SSL/TLS encrypted HTTPS connections.
    
    HTTPS Configuration:
        To enable HTTPS, set the following environment variables:
        - SSL_CERT_FILE: Path to SSL certificate file (e.g., /path/to/cert.pem)
        - SSL_KEY_FILE: Path to SSL private key file (e.g., /path/to/key.pem)
        
        Alternatively, pass these paths when initializing:
        HTTPController(ssl_cert_file="/path/to/cert.pem", ssl_key_file="/path/to/key.pem")
        
        If SSL certificates are not provided, only HTTP will be supported.
        
    Example:
        # HTTP only (default)
        controller = HTTPController()
        
        # HTTPS enabled
        controller = HTTPController(
            ssl_cert_file="/etc/ssl/certs/server.crt",
            ssl_key_file="/etc/ssl/private/server.key"
        )
    """
    
    def __init__(self, console_lock=None, ssl_cert_file=None, ssl_key_file=None):
        """
        Initialize HTTP controller
        
        :param console_lock: Optional threading lock for console output
        :param ssl_cert_file: Optional path to SSL certificate file for HTTPS
        :param ssl_key_file: Optional path to SSL private key file for HTTPS
        """
        self.console_lock = console_lock
        self._routes = {}
        self._register_default_routes()
        
        # SSL/TLS configuration
        self.ssl_cert_file = ssl_cert_file or os.getenv("SSL_CERT_FILE")
        self.ssl_key_file = ssl_key_file or os.getenv("SSL_KEY_FILE")
        self._ssl_context = None
        
        # Initialize SSL context if certificates are provided
        if self.ssl_cert_file and self.ssl_key_file:
            self._init_ssl_context()
    
    def _init_ssl_context(self):
        """Initialize SSL context for HTTPS support"""
        try:
            self._ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self._ssl_context.load_cert_chain(self.ssl_cert_file, self.ssl_key_file)
            if self.console_lock:
                with self.console_lock:
                    print_with_datetime(f"HTTPS enabled with certificate: {self.ssl_cert_file}")
            else:
                print_with_datetime(f"HTTPS enabled with certificate: {self.ssl_cert_file}")
        except Exception as e:
            if self.console_lock:
                with self.console_lock:
                    print_with_datetime(f"Warning: Failed to initialize SSL context: {e}. HTTPS disabled.")
            else:
                print_with_datetime(f"Warning: Failed to initialize SSL context: {e}. HTTPS disabled.")
            self._ssl_context = None
            self.ssl_cert_file = None
            self.ssl_key_file = None
    
    def _is_ssl_handshake(self, data: bytes) -> bool:
        """
        Detect if incoming data is an SSL/TLS handshake
        
        :param data: Raw bytes from socket
        :return: True if data appears to be an SSL handshake
        """
        if len(data) < 1:
            return False
        
        # SSL/TLS handshake starts with 0x16 (22) for handshake record
        # See RFC 5246 for TLS protocol
        return data[0] == 0x16  # SSL/TLS handshake record type
    
    def _wrap_ssl_socket(self, client: socket.socket) -> Optional[ssl.SSLSocket]:
        """
        Wrap a plain socket with SSL/TLS
        
        :param client: Plain socket connection
        :return: SSL-wrapped socket or None if SSL is not available
        """
        if not self._ssl_context:
            return None
        
        try:
            # Wrap the socket with SSL
            ssl_socket = self._ssl_context.wrap_socket(client, server_side=True)
            return ssl_socket
        except Exception as e:
            if self.console_lock:
                with self.console_lock:
                    print_with_datetime(f"Error wrapping socket with SSL: {e}")
            else:
                print_with_datetime(f"Error wrapping socket with SSL: {e}")
            return None
    
    def _register_default_routes(self):
        """Register default route handlers"""
        self.register_route("GET", "/metrics", self._handle_metrics)
    
    def register_route(self, method: str, path: str, handler):
        """
        Register a route handler
        
        :param method: HTTP method (GET, POST, etc.)
        :param path: URL path
        :param handler: Callable that takes (request, client) and returns HTTPResponse
        """
        route_key = (method.upper(), path)
        self._routes[route_key] = handler
    
    def parse_request(self, data: str) -> Optional[HTTPRequest]:
        """
        Parse HTTP request from raw data
        
        :param data: Raw HTTP request string
        :return: HTTPRequest object or None if parsing fails
        """
        try:
            lines = data.split("\n")
            if not lines:
                return None
            
            # Parse request line
            request_line = lines[0].strip()
            parts = request_line.split()
            if len(parts) < 2:
                return None
            
            method = parts[0]
            path = parts[1] if len(parts) > 1 else "/"
            
            # Parse headers
            headers = {}
            body_start = 1
            for i, line in enumerate(lines[1:], start=1):
                line = line.strip()
                if not line:
                    body_start = i + 1
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Parse body if present
            body = "\n".join(lines[body_start:]) if body_start < len(lines) else ""
            
            return HTTPRequest(method, path, headers, body)
        except Exception:
            return None
    
    def handle_request(self, client: socket.socket, data: Union[str, bytes]) -> bool:
        """
        Handle an HTTP or HTTPS request
        
        :param client: Client socket connection (may be plain or SSL-wrapped)
        :param data: Raw request data (string for HTTP, bytes for potential HTTPS)
        :return: True if request was handled as HTTP/HTTPS, False otherwise
        """
        # Convert bytes to string if needed (for SSL detection)
        if isinstance(data, bytes):
            # Check if this is an SSL handshake
            if self._is_ssl_handshake(data):
                return self._handle_https_request(client)
            # Otherwise, decode as UTF-8 for HTTP
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                # If we can't decode, it's probably not HTTP
                return False
        
        # Check if this looks like an HTTP request
        if not data.strip().startswith(("GET ", "POST ", "PUT ", "DELETE ", "HEAD ", "OPTIONS ")):
            return False
        
        # Parse the request
        request = self.parse_request(data)
        if not request:
            self._send_error_response(client, 400, "Bad Request", "Invalid HTTP request format")
            return True
        
        # Find route handler
        route_key = (request.method, request.path)
        handler = self._routes.get(route_key)
        
        if handler:
            try:
                response = handler(request, client)
                if response:
                    self._send_response(client, response)
                    self._log_request(request, client, response.status_code, is_https=False)
                else:
                    self._send_error_response(client, 500, "Internal Server Error", "Handler returned no response")
            except Exception as e:
                self._send_error_response(client, 500, "Internal Server Error", f"Error handling request: {e}")
        else:
            # Route not found
            self._send_error_response(
                client, 
                404, 
                "Not Found", 
                f"Endpoint not found: {request.path}. Only /metrics is available."
            )
            self._log_request(request, client, 404, is_https=False)
        
        # Close connection after handling
        try:
            client.close()
        except Exception:
            pass
        
        return True
    
    def _handle_https_request(self, client: socket.socket) -> bool:
        """
        Handle an HTTPS request by wrapping the socket with SSL
        
        :param client: Plain socket connection
        :return: True if HTTPS request was handled, False otherwise
        """
        if not self._ssl_context:
            # SSL not configured, can't handle HTTPS
            try:
                client.close()
            except Exception:
                pass
            return False
        
        # Wrap socket with SSL (this will perform SSL handshake)
        # The handshake will consume the initial bytes from the socket buffer
        ssl_client = self._wrap_ssl_socket(client)
        if not ssl_client:
            try:
                client.close()
            except Exception:
                pass
            return False
        
        try:
            # Read HTTP request over SSL
            # Set a timeout for reading
            ssl_client.settimeout(10.0)
            # Read the HTTP request (SSL handshake already completed)
            data = ssl_client.recv(4096).decode("utf-8")
            
            # Check if this looks like an HTTP request
            if not data.strip().startswith(("GET ", "POST ", "PUT ", "DELETE ", "HEAD ", "OPTIONS ")):
                ssl_client.close()
                return False
            
            # Parse the request
            request = self.parse_request(data)
            if not request:
                self._send_error_response(ssl_client, 400, "Bad Request", "Invalid HTTP request format")
                return True
            
            # Find route handler
            route_key = (request.method, request.path)
            handler = self._routes.get(route_key)
            
            if handler:
                try:
                    response = handler(request, ssl_client)
                    if response:
                        self._send_response(ssl_client, response)
                        self._log_request(request, ssl_client, response.status_code, is_https=True)
                    else:
                        self._send_error_response(ssl_client, 500, "Internal Server Error", "Handler returned no response")
                except Exception as e:
                    self._send_error_response(ssl_client, 500, "Internal Server Error", f"Error handling request: {e}")
            else:
                # Route not found
                self._send_error_response(
                    ssl_client, 
                    404, 
                    "Not Found", 
                    f"Endpoint not found: {request.path}. Only /metrics is available."
                )
                self._log_request(request, ssl_client, 404, is_https=True)
            
            return True
        except ssl.SSLError as e:
            if self.console_lock:
                with self.console_lock:
                    print_with_datetime(f"SSL error handling HTTPS request: {e}")
            else:
                print_with_datetime(f"SSL error handling HTTPS request: {e}")
            return False
        except Exception as e:
            if self.console_lock:
                with self.console_lock:
                    print_with_datetime(f"Error handling HTTPS request: {e}")
            else:
                print_with_datetime(f"Error handling HTTPS request: {e}")
            return False
        finally:
            try:
                ssl_client.close()
            except Exception:
                pass
    
    def _send_response(self, client: Union[socket.socket, ssl.SSLSocket], response: HTTPResponse):
        """
        Send HTTP response over plain or SSL socket
        
        :param client: Client socket (plain or SSL-wrapped)
        :param response: HTTP response to send
        """
        try:
            client.send(response.to_bytes())
        except Exception as e:
            if self.console_lock:
                with self.console_lock:
                    print_with_datetime(f"Error sending response: {e}")
            else:
                print_with_datetime(f"Error sending response: {e}")
    
    def _handle_metrics(self, request: HTTPRequest, client: socket.socket) -> HTTPResponse:
        """
        Handle /metrics endpoint for Prometheus
        
        :param request: HTTP request
        :param client: Client socket (for logging)
        :return: HTTP response
        """
        try:
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            
            # Generate Prometheus metrics
            metrics_output = generate_latest()
            
            # Create response
            response = HTTPResponse(
                status_code=200,
                status_text="OK",
                headers={
                    "Content-Type": CONTENT_TYPE_LATEST
                },
                body=metrics_output
            )
            
            return response
        except Exception as e:
            # If metrics generation fails, return 500 error
            return HTTPResponse(
                status_code=500,
                status_text="Internal Server Error",
                headers={"Content-Type": "text/plain"},
                body=f"Error generating metrics: {e}\r\n".encode("utf-8")
            )
    
    def _send_error_response(self, client: Union[socket.socket, ssl.SSLSocket], status_code: int, status_text: str, message: str):
        """
        Send an error response to the client
        
        :param client: Client socket (plain or SSL-wrapped)
        :param status_code: HTTP status code
        :param status_text: HTTP status text
        :param message: Error message
        """
        try:
            response = HTTPResponse(
                status_code=status_code,
                status_text=status_text,
                headers={"Content-Type": "text/plain"},
                body=f"{message}\r\n".encode("utf-8")
            )
            self._send_response(client, response)
        except Exception:
            pass
    
    def _log_request(self, request: HTTPRequest, client: Union[socket.socket, ssl.SSLSocket], status_code: int, is_https: bool = False):
        """
        Log HTTP/HTTPS request
        
        :param request: HTTP request
        :param client: Client socket (plain or SSL-wrapped)
        :param status_code: Response status code
        :param is_https: Whether this was an HTTPS request
        """
        try:
            client_address = client.getpeername()
            protocol = "HTTPS" if is_https else "HTTP"
            if request.path == "/metrics":
                message = f"Served Prometheus metrics via {protocol} to {client_address}"
            else:
                message = f"Rejected {protocol} request {request.method} {request.path} from {client_address}"
            
            if self.console_lock:
                with self.console_lock:
                    print_with_datetime(message)
            else:
                print_with_datetime(message)
        except Exception:
            pass
