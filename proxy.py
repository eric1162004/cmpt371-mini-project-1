"""
CMPT 371 - Mini Project 1: Multiplexed HTTP/1.1 Proxy Server
Authors: Eric Cheung, Harry Kim
MP-Group: 26
Date: October 29, 2025

Description:
This Python script implements a multithreaded HTTP/1.1 proxy server using raw sockets.
It intercepts client GET requests, forwards them to the origin server using a custom
framing protocol, and relays the framed response back. The proxy supports conditional
GETs via 'If-Modified-Since' headers and maintains an in-memory cache to reduce redundant
fetches. It parses framed responses using STREAM-ID headers to support multiplexed streams.

Framing Protocol Design:
Each request and response is encapsulated in a custom frame format to support multiplexing.
Frames are structured as:

    STREAM-ID|END-FLAG|PAYLOAD

- STREAM-ID: Unique integer identifying the logical stream (e.g., 1, 2, 3, ...)
- END-FLAG: 1 if this is the final frame for the stream, 0 otherwise
- PAYLOAD: Raw HTTP request or response content

Example:
    3|1|HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nHello

The proxy uses `STREAM-ID` to match responses to requests and supports interleaved delivery.

Key Features:
- Conditional GET support with cache validation (304 Not Modified)
- In-memory caching of static files with Last-Modified tracking
- Custom framing protocol with STREAM-ID headers for multiplexed requests
- Frame parsing and stream ID matching for response demultiplexing
- Robust error handling with detailed 500 responses
- Concurrent client handling via multithreading
- Modular response construction for HTTP status codes

Usage:
- Start the origin server: `python3 server.py`
- Start the proxy server: `python3 proxy.py`
- Default file served: test.html
- Restricted file: private.html (returns 403)

© 2025 Eric Cheung, Harry Kim. All rights reserved.
"""

# For creating TCP sockets, binding, listening, accepting, sending/receiving data
import socket

# For serving multiple clients concurrently.
import threading

# For parsing and comparing HTTP date headers (e.g., If-Modified-Since)
from datetime import datetime

# For generating Date headers in responses compliant with
# `If-Modified-Since: Wed, 18 Oct 2025 10:00:00 GMT`
from email.utils import formatdate

# For generating an infinite stream of unique stream IDs using count().
import itertools


# The proxy will bind to localhost
PROXY_HOST = "127.0.0.1"

# The port number the proxy listens on
PROXY_PORT = 8081

# The proxy will bind to localhost
SERVER_HOST = "127.0.0.1"

# The port number the proxy listens on
SERVER_PORT = 8080

# The HTTP version our proxy will use in responses
VERSION = "HTTP/1.1"

# Socket receive buffer size
SOCKET_RECV_BUFFER_SIZE = 4096

# The default file to serve when the root path "/" is requested
DEFAULT_FILE = "test.html"

# The private file that should return 403 Forbidden when accessed
PRVIATE_FILE = "private.html"

# Mapping of HTTP status codes to their titles and HTML bodies
STATUS = {
    200: {"title": "OK", "body": None},
    304: {"title": "Not Modified", "body": None},
    403: {"title": "Forbidden", "body": "<h1>403 Forbidden</h1>"},
    404: {"title": "Not Found", "body": "<h1>404 Not Found</h1>"},
    500: {
        "title": "Internal Server Error",
        "body": "<h1>500 Internal Server Error</h1>",
    },
    505: {
        "title": "HTTP Version Not Supported",
        "body": "<h1>505 HTTP Version Not Supported</h1>",
    },
}

# In-memory cache: {filename: {"last_modified": str, "content": bytes}}
cache = {}

# Used to tag each proxied request for multiplexed framing.
stream_id_gen = itertools.count(1)


def createResponse(statusCode, body=b""):
    """
    Constructs a raw HTTP/1.1 response in bytes.

    Args:
        statusCode (int): HTTP status code.
        body (bytes): Optional HTML body content.

    Returns:
        bytes: Complete HTTP response.
    """
    # Build the HTTP status line
    statusLine = f"{VERSION} {statusCode} {STATUS[statusCode]['title']}"

    headers = {}
    headers["Date"] = formatdate(timeval=None, localtime=False, usegmt=True)
    headers["Server"] = "TestServer/1.0"

    if body:
        headers["Content-Length"] = str(len(body))
        headers["Content-Type"] = "text/html"

    # Convert headers dict into properly formatted HTTP header lines
    headerLines = "".join(f"{k}: {v}\r\n" for k, v in headers.items())

    # Combine status line + headers + CRLF separator
    head = f"{statusLine}\r\n{headerLines}\r\n"

    return head.encode("utf-8") + body


def handle200(filename, response):
    """
    Updates cache with new content and returns a 200 OK response.

    Args:
        filename (str): Name of the requested file.
        response (bytes): Raw HTTP response from origin server.

    Returns:
        bytes: HTTP response with updated content.
    """
    headers, body = response.split(b"\r\n\r\n", 1)

    lastModified = None

    # Search through headers for a "Last-Modified" field
    for line in headers.split(b"\r\n"):
        if line.lower().startswith(b"last-modified:"):
            # Extract the timestamp value and decode from bytes to string
            lastModified = line.split(b": ", 1)[1].decode()
            break

    lastModified = lastModified or formatdate(timeval=None, usegmt=True)

    # Update the cache with the new content and last modified time
    cache[filename] = {"last_modified": lastModified, "content": body}

    return createResponse(200, body)


def handle304(filename):
    """
    Serves cached content for a 304 Not Modified response.

    Args:
        filename (str): Name of the requested file.

    Returns:
        bytes: HTTP response with cached content.
    """
    cached = cache[filename]
    return createResponse(200, cached["content"])


def handle505():
    """
    Returns a 505 HTTP Version Not Supported response.

    Returns:
        bytes: HTTP response with predefined 505 HTML body.
    """
    msg = STATUS[505]["body"].encode()
    return createResponse(505, msg)


def handle500(error):
    """
    Returns a 500 Internal Server Error response with error details.

    Args:
        error (Exception): Exception object to include in response.

    Returns:
        bytes: HTTP response with embedded error message.
    """
    msg = STATUS[500]["body"]
    msg += f"<p>{error}</p>"
    msg = msg.encode()
    return createResponse(500, msg)


def createRequest(headers, cached=None):
    """
    Builds a proxy request string with optional 'If-Modified-Since' header.

    Args:
        headers (list): List of HTTP header lines.
        cached (dict, optional): Cached metadata with 'last_modified' timestamp.

    Returns:
        str: Complete HTTP request string.
    """
    if cached:
        headers.append(f"If-Modified-Since: {cached['last_modified']}")
    return "\r\n".join(headers) + "\r\n\r\n"


def hasCompleteFrame(buffer):
    """
    Checks if the buffer contains a complete frame (two '|' delimiters).

    Args:
        buffer (str): Incoming data buffer.

    Returns:
        bool: True if a complete frame is present.
    """
    return buffer.count("|") >= 2


def extractFrame(buffer):
    """
    Extracts a single frame from the buffer.

    Args:
        buffer (str): Incoming data buffer.

    Returns:
        tuple: (frame: str or None, updated_buffer: str)
    """
    try:
        sidStr, endStr, rest = buffer.split("|", 2)
        return f"{sidStr}|{endStr}|{rest}", ""  # Frame isolated, buffer cleared
    except ValueError:
        return None, buffer  # Malformed — preserve buffer


def parseFrame(frame):
    """
    Parses a frame into stream ID, end flag, and payload.

    Args:
        frame (str): Raw frame string.

    Returns:
        tuple: (stream_id: int or None, end_flag: int or None, payload: str)
    """
    try:
        sidStr, endStr, payload = frame.split("|", 2)
        return int(sidStr), int(endStr), payload
    except ValueError:
        return None, None, None  # Malformed frame


def receiveFramedResponse(serverSocket, expectedStreamId):
    """
    Receives and assembles framed response from origin server.

    Args:
        serverSocket (socket.socket): Connected socket to origin server.
        expectedStreamId (int): Stream ID to match frames.

    Returns:
        bytes: Reconstructed HTTP response payload.
    """
    buffer = ""
    responseChunks = []

    while True:
        chunk = serverSocket.recv(SOCKET_RECV_BUFFER_SIZE)
        if not chunk:
            break
        buffer += chunk.decode()

        while hasCompleteFrame(buffer):
            frame, buffer = extractFrame(buffer)
            if not frame:
                break  # Malformed frame or incomplete — wait for more data

            stream_id, end_flag, payload = parseFrame(frame)
            if stream_id is None:
                continue  # Skip malformed frame

            if stream_id != expectedStreamId:
                continue  # Ignore unrelated stream

            responseChunks.append(payload)

            if end_flag == 1:
                return "".join(responseChunks).encode()

    return "".join(responseChunks).encode()


def sendRequest(request):
    """
    Sends a framed request to the origin server and receives the response.

    Args:
        request (str): Raw HTTP request string.

    Returns:
        bytes: Framed response from origin server.
    """
    # Generate a unique stream ID
    streamId = next(stream_id_gen)

    # Frame the request by prepending the stream ID header.
    framedRequest = f"STREAM-ID: {streamId}\r\n{request}"

    # Open a TCP socket to the server, send the framed request,
    # and wait for the corresponding framed response.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVER_HOST, SERVER_PORT))

        s.sendall(framedRequest.encode())

        return receiveFramedResponse(s, streamId)


def handleRequest(request):
    """
    Parses client request, applies caching logic, and returns appropriate response.

    Args:
        request (str): Raw HTTP request from client.

    Returns:
        bytes: HTTP response to send back to client.
    """
    try:
        lines = request.split("\r\n")

        # The first line of an HTTP request is the request line: METHOD PATH VERSION
        # Example: "GET /index.html HTTP/1.1"
        method, path, version = lines[0].split()

        if version != VERSION:
            return handle505()

        # Only handle GET requests
        headers = [
            f"GET {path} {VERSION}",
        ]

        # handle "/" by serving DEAULT_FILE
        if path == "/" or path == "":
            path = DEFAULT_FILE

        # Remove leading "/" from path to get the filename
        fileName = path.lstrip("/")
        cached = cache.get(fileName)

        # Create the request to send to the origin server
        proxyRequest = createRequest(headers, cached)
        response = sendRequest(proxyRequest)

        # Parse the status code from the response
        statusLine = response.split(b"\r\n")[0].decode()
        statusCode = int(statusLine.split()[1])  # split at space

        if statusCode == 200:
            return handle200(fileName, response)
        elif statusCode == 304 and cached:
            return handle304(fileName)
        else:
            return response

    except Exception as e:
        return handle500(e)


def handleClient(conn, addr):
    """
    Handles a client connection and sends back the appropriate response.

    Args:
        conn (socket.socket): Client connection socket.
        addr (tuple): Client address.

    Returns:
        None
    """
    with conn:
        try:
            request = conn.recv(SOCKET_RECV_BUFFER_SIZE).decode()
            print(f"[{addr}] Client Request:\n{request}")

            response = handleRequest(request)
            conn.sendall(response)

        except Exception as e:
            conn.sendall(handle500(e))


def startProxy():
    """
    Starts the proxy server, listens for incoming connections, and spawns threads to handle clients.

    Returns:
        None
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Allow quickly restart the proxy on the same port
        # without waiting for the OS to release it.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind the proxy to the specified host and port
        s.bind((PROXY_HOST, PROXY_PORT))

        # Start listening for incoming connections
        s.listen()

        print(f"Proxy started at http://{PROXY_HOST}:{PROXY_PORT}\n")

        while True:
            # Accept a new client connection
            conn, addr = s.accept()
            # Handle the client connection in a new thread
            threading.Thread(target=handleClient, args=(conn, addr)).start()


if __name__ == "__main__":
    startProxy()
