"""
CMPT 371 - Mini Project 1: Multiplexed HTTP/1.1 Web Server
Authors: Eric Cheung, Harry Kim
MP-Group: 26
Date: October 29, 2025

Description:
This Python script implements a multithreaded HTTP/1.1 web server using raw sockets.
It supports both regular and multiplexed request handling via a custom framing protocol
using STREAM-ID headers. The server handles basic GET requests and conditional requests
via the 'If-Modified-Since' header, returning appropriate status codes:
200 OK, 304 Not Modified, 403 Forbidden, 404 Not Found, 500 Internal Server Error,
and 505 HTTP Version Not Supported.

Framing Protocol (used for multiplexed responses):
Each response is split into frames of the form:

    STREAM-ID|END-FLAG|PAYLOAD

- STREAM-ID: Unique identifier for the logical stream
- END-FLAG: 1 if final frame, 0 otherwise
- PAYLOAD: Chunk of HTTP response

Example:
    2|0|HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nHe
    2|1|llo

See proxy.py for full framing protocol documentation.

Key Features:
- Modular response handlers for each HTTP status code
- Conditional GET support using file modification timestamps
- Framed response delivery for multiplexed streams
- Thread-safe socket communication using locks
- Concurrent client handling via multithreading
- Static file serving from a local directory with access control

Usage:
- Run the server: `python3 server.py`
- Default file served: test.html
- Restricted file: private.html (returns 403)

© 2025 Eric Cheung, Harry Kim. All rights reserved.
"""

# For creating TCP sockets, binding, listening, accepting, sending/receiving data
import socket

# For filesystem operations (e.g., joining paths, checking file existence, getting modification times)
import os

# For serving multiple clients concurrently.
import threading

# For parsing and comparing HTTP date headers (e.g., If-Modified-Since)
from datetime import datetime

# For generating Date headers in responses compliant with
# `If-Modified-Since: Wed, 18 Oct 2025 10:00:00 GMT`
from email.utils import formatdate

# The server will bind to localhost
HOST = "127.0.0.1"

# The port number the server listens on
PORT = 8080

# The base directory for serving files (e.g., test.html should be in this folder)
BASE_DIR = "./"

# The HTTP version our server will use in responses
VERSION = "HTTP/1.1"

# The default file to serve when the root path "/" is requested
DEFAULT_FILE = "test.html"

# The private file that should return 403 Forbidden when accessed
PRVIATE_FILE = "private.html"

# The maximum chunk size for framed responses
MAX_CHUNK_SIZE = 1024

# Socket receive buffer size (Buffer size must be grerater than MAX_CHUNK_SIZE)
SOCKET_RECV_BUFFER_SIZE = 4096

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


def createResponse(statusCode, body=""):
    """
    Constructs a raw HTTP/1.1 response string.

    Args:
        statusCode (int): HTTP status code (e.g., 200, 404).
        body (str): Optional HTML body content.

    Returns:
        str: Complete HTTP response including headers and body.
    """
    # Build the HTTP status line: e.g. "HTTP/1.1 200 OK"
    statusLine = f"{VERSION} {statusCode} {STATUS[statusCode]['title']}\r\n"

    headers = {}
    headers.setdefault("Date", formatdate(timeval=None, localtime=False, usegmt=True))
    headers.setdefault("Server", "TestServer/1.0")

    if body:
        headers["Content-Length"] = str(len(body))
        headers["Content-Type"] = "text/html"

    headerLines = "".join(f"{k}: {v}\r\n" for k, v in headers.items())

    # Final response: status line + headers + blank line + body
    return f"{statusLine}{headerLines}\r\n{body}"


def handle200(filePath):
    """
    Reads the requested file and returns a 200 OK HTTP response.

    Args:
        filePath (str): Absolute path to the requested file.

    Returns:
        str: HTTP response with file contents as the body.
    """
    with open(filePath, "r") as f:
        body = f.read()
    return createResponse(200, body)


def handle304(filePath, headerLine):
    """
    Handles conditional GET requests using 'If-Modified-Since'.

    Args:
        filePath (str): Path to the requested file.
        headerLine (str): Raw header line containing the timestamp.

    Returns:
        str or None: 304 response if not modified, else None.
    """
    # Parse the "If-Modified-Since" header value into a datetime object~
    clientTime = datetime.strptime(
        headerLine.split(": ", 1)[1], "%a, %d %b %Y %H:%M:%S GMT"
    )

    # Get the file's last modification time (UTC)
    fileLastModifiedTime = datetime.utcfromtimestamp(os.path.getmtime(filePath))

    # If the file has not been modified since the client's cached version,
    # return a 304 Not Modified response
    # NOTE: Else ther server will continue to serve the file with 200 OK
    if fileLastModifiedTime <= clientTime:
        return createResponse(304)

    # print("File has been modified since client's cached version.")


def handle403():
    """
    Returns a 403 Forbidden HTTP response.

    Returns:
        str: HTTP response with predefined 403 HTML body.
    """
    return createResponse(403, STATUS[403]["body"])


def handle404():
    """
    Returns a 404 Not Found HTTP response.

    Returns:
        str: HTTP response with predefined 404 HTML body.
    """
    return createResponse(404, STATUS[404]["body"])


def handle505():
    """
    Returns a 505 HTTP Version Not Supported response.

    Returns:
        str: HTTP response with predefined 505 HTML body.
    """
    return createResponse(505, STATUS[505]["body"])


def handle500(error):
    """
    Returns a 500 Internal Server Error response with error details.

    Args:
        error (Exception): Exception object to include in response.

    Returns:
        str: HTTP response with embedded error message.
    """
    msg = STATUS[500]["body"]
    msg += f"<p>{error}</p>"
    return createResponse(500, msg)


def handleRequest(request):
    try:
        lines = request.split("\r\n")

        # The first line of an HTTP request is the request line: METHOD PATH VERSION
        # Example: "GET /index.html HTTP/1.1"
        method, path, version = lines[0].split()

        # handle "/" by serving DEAULT_FILE
        if path == "/" or path == "":
            path = DEFAULT_FILE

        # If the HTTP version in the request does not match the server's supported version,
        # return a 505 HTTP Version Not Supported response
        if version != VERSION:
            return createResponse(505)

        # Construct the absolute file path by joining with the server's base directory
        fileName = path.lstrip("/")
        filePath = os.path.join(BASE_DIR, fileName)
        print(f"Requested file path: {filePath}")

        # If the client is trying to access a restricted file, deny access with 403 Forbidden
        if fileName == PRVIATE_FILE:
            return handle403()

        # If the requested file does not exist on the server, return 404 Not Found
        if not os.path.exists(filePath):
            return handle404()

        # Check for conditional GET requests using the "If-Modified-Since" header
        # If present, delegate to handle304() to determine if the file has changed
        for line in lines[1:]:
            if line.startswith("If-Modified-Since:"):
                response = handle304(filePath, line)
                if response:
                    return response

        # If none of the above conditions triggered, serve the file with a 200 OK response
        return handle200(filePath)

    except Exception as e:
        # If any unexpected error occurs during request handling,
        # return a 500 Internal Server Error with the exception details
        return handle500(e)


def extractStreamIdAndCleanRequest(request):
    """
    Extracts STREAM-ID from framed request and returns cleaned HTTP request.

    Args:
        request (str): Raw framed request string.

    Returns:
        tuple: (stream_id: int or None, cleaned_request: str)
    """
    lines = request.split("\r\n")
    stream_id = None

    # Check if the first line contains a STREAM-ID header
    if lines[0].startswith("STREAM-ID:"):
        try:
            # Attempt to parse the numeric stream ID from the header
            stream_id = int(lines[0].split(":")[1].strip())
            # Remove the STREAM-ID line so the rest of the request is clean
            lines = lines[1:]
        except ValueError:
            # If parsing fails (non-integer value), treat as no stream ID
            stream_id = None

    # Reconstruct the request without the STREAM-ID line
    request_clean = "\r\n".join(lines)

    return stream_id, request_clean


def sendFramedResponse(conn, stream_id, response, lock):
    """
    Sends a framed HTTP response over the socket using STREAM-ID protocol.

    Args:
        conn (socket.socket): Client connection socket.
        stream_id (int): Logical stream identifier.
        response (str): Raw HTTP response string.
        lock (threading.Lock): Lock for thread-safe socket access.

    Returns:
        None
    """
    # Iterate over the response in increments of chunk size
    for i in range(0, len(response), MAX_CHUNK_SIZE):
        # Extract the current chunk of data
        chunk = response[i : i + MAX_CHUNK_SIZE]

        # Determine if this is the final chunk (1 = end, 0 = more to come)
        end_stream = int(i + MAX_CHUNK_SIZE >= len(response))

        # Construct the frame with stream ID, end flag, and chunk payload
        frame = f"{stream_id}|{end_stream}|{chunk}"

        # Send the encoded frame over the socket
        try:
            with lock:
                conn.sendall(frame.encode())
        except (BrokenPipeError, OSError) as e:
            print(f"[Thread {threading.get_ident()}] Failed to send response: {e}")


def sendRegularResponse(conn, response, lock):
    """
    Sends a standard HTTP response over the socket.

    Args:
        conn (socket.socket): Client connection socket.
        response (str): Raw HTTP response string.
        lock (threading.Lock): Lock for thread-safe socket access.

    Returns:
        None
    """
    with lock:
        conn.sendall(response.encode())


def handleRequestThread(conn, request, lock):
    """
    Processes a single HTTP request in a dedicated thread.

    Args:
        conn (socket.socket): Client connection socket.
        request (str): Raw HTTP request string.
        lock (threading.Lock): Lock for synchronized socket access.

    Returns:
        None
    """
    print(request)

    # Extract stream ID (if present) and clean the request for processing
    streamId, requestClean = extractStreamIdAndCleanRequest(request)

    # Generate an appropriate response based on the cleaned request
    response = handleRequest(requestClean)

    # Send response back to client:
    # If stream ID exists, use framed response (for multiplexed streams)
    # Otherwise, send a regular HTTP response
    if streamId is not None:
        sendFramedResponse(conn, streamId, response, lock)
    else:
        sendRegularResponse(conn, response, lock)


def handleClient(conn, addr):
    """
    Handles a client connection, dispatching each request to a separate thread.

    Args:
        conn (socket.socket): Client connection socket.
        addr (tuple): Client address (IP, port).

    Returns:
        None
    """
    # Get the current thread ID for logging purposes
    thread_id = threading.get_ident()
    print(f"[Thread {thread_id}] Handling connection from {addr}")

    # Create a lock to synchronize access to the shared connection socket.
    # This prevents race conditions when multiple request-handling threads
    # attempt to send responses over the same socket concurrently.
    conn_lock = threading.Lock()
    threads = []  # Track all spawned request threads

    # The socket is automatically closed when the block exits.
    with conn:
        buffer = ""  # Accumulate partial data

        while True:
            # Receive up to SOCKET_RECV_BUFFER_SIZE bytes from the client
            data = conn.recv(SOCKET_RECV_BUFFER_SIZE)
            if not data:
                # Exit loop if client closes the connection
                break
            buffer += data.decode()

            # Process all complete requests currently in the buffer
            # HTTP requests are separated by a blank line (CRLF CRLF)
            while "\r\n\r\n" in buffer:
                # Split off one complete request, leaving the rest in buffer
                request, buffer = buffer.split("\r\n\r\n", 1)

                # Dispatch the request to a new thread for independent handling
                t = threading.Thread(
                    target=handleRequestThread, args=(conn, request, conn_lock)
                )
                t.start()
                threads.append(t)

        # Wait for all request threads to finish before closing the socket
        for t in threads:
            t.join()
            
        print(f"[Thread {thread_id}] Connection from {addr} closed.\n")


def startServer():
    """
    Starts the HTTP server, listens for incoming connections, and spawns threads to handle clients.

    Returns:
        None
    """
    # Create a TCP/IP socket using IPv4 addressing
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Allow quickly restart the proxy on the same port
        # without waiting for the OS to release it.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind the socket to a specific host and port
        s.bind((HOST, PORT))

        # Put the socket into listening mode
        # so it can accept incoming connections
        s.listen()

        print(f"Server started at http://{HOST}:{PORT}\n")

        # Continuously accept and handle client requests
        while True:
            conn, addr = s.accept()

            # Spawn threads to handle multiple clients concurrently
            thread = threading.Thread(target=handleClient, args=(conn, addr))
            thread.start()


# Ensures that code only runs when the file is executed directly
if __name__ == "__main__":
    startServer()
