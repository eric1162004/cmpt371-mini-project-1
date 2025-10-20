"""
CMPT 371 - Mini Project 1: HTTP Proxy Server
Authors: Eric Cheung, Harry Kim
MP-Group: 26
Date: October 29, 2025

Description:
This Python script implements a minimal HTTP/1.1 proxy server using raw sockets and in-memory caching.
It intercepts client GET requests, forwards them to the origin server, and relays the response back.
If the requested file (e.g., test.html) is cached, the proxy sends a conditional GET using the
'If-Modified-Since' header. If the origin server returns 304 Not Modified, the proxy serves the cached version.
Otherwise, it updates the cache with the new content and forwards the updated response.

Multithreading is used to handle concurrent client connections.

Usage:
- Run the server: `python3 server.py`
- Run the proxy: `python3 proxy.py`

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

def createResponse(statusCode, body=b""):
    # Build the HTTP status line
    statusLine = f"{VERSION} {statusCode} {STATUS[statusCode]['title']}\r\n"

    # Initialize headers dictionary
    headers = {}
    headers["Date"] = formatdate(timeval=None, localtime=False, usegmt=True)
    headers["Server"] = "TestServer/1.0"

    # If there is a body, include Content-Length and Content-Type
    if body:
        headers["Content-Length"] = str(len(body))
        headers["Content-Type"] = "text/html"

    # Convert headers dict into properly formatted HTTP header lines
    headerLines = "".join(f"{k}: {v}\r\n" for k, v in headers.items())

    # Combine status line + headers + CRLF separator
    head = f"{statusLine}{headerLines}\r\n".encode("utf-8")

    # Return as bytes: headers + body
    return head + body

def handle200(filename, response):
    headers, body = response.split(b"\r\n\r\n", 1)
    lastModified = None
    for line in headers.split(b"\r\n"):
        if line.lower().startswith(b"last-modified:"):
            lastModified = line.split(b": ", 1)[1].decode()
            break
    lastModified = lastModified or formatdate(timeval=None, usegmt=True)
    cache[filename] = {"last_modified": lastModified, "content": body}
    return createResponse(200, body)

def handle304(filename):
    cached = cache[filename]
    return createResponse(200, cached["content"])

def handle505():
    # Return a 505 HTTP Version Not Supported response with the predefined HTML body
    msg = STATUS[505]["body"].encode()
    return createResponse(505, msg)

def handle500(error):
    msg = STATUS[500]["body"]

    # Append the error details inside a <p> tag for debugging
    msg += f"<p>{error}</p>"
    msg = msg.encode()

    # Return a 500 Internal Server Error response with details
    return createResponse(500, msg)

def createRequest(headers, cached=None):
    # Builds the proxy request string with optional cache headers.
    if cached:
        headers.append(f"If-Modified-Since: {cached['last_modified']}")
    return "\r\n".join(headers) + "\r\n"

def receiveResponse(serverSocket):
    # Receives the full response from the server socket.
    response = b""
    while True:
        chunk = serverSocket.recv(4096)
        if not chunk:
            break
        response += chunk
    return response

def sendRequest(request):
    # Sends the request to the server and returns the raw response.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serverSocket:
        serverSocket.connect((SERVER_HOST, SERVER_PORT))
        serverSocket.sendall(request.encode())
        return receiveResponse(serverSocket)

def handleRequest(request):
    try:
        # Split the raw HTTP request into lines using CRLF
        lines = request.split("\r\n")
        print(f"Request lines: {lines}")

        # The first line of an HTTP request is the request line: METHOD PATH VERSION
        # Example: "GET /index.html HTTP/1.1"
        method, path, version = lines[0].split()
        
        if version != VERSION:
            return handle505()
        
        headers = [
            f"GET {path} {VERSION}",
        ]
        
        # handle "/" by serving DEAULT_FILE
        if path == "/" or path == "":
            path = DEFAULT_FILE
            
        # Remove leading "/" from path to get the filename
        fileName = path.lstrip("/")
        cached = cache.get(fileName)

        proxyRequest = createRequest(headers, cached)
        response = sendRequest(proxyRequest)
            
        statusLine = response.split(b"\r\n")[0].decode()
        statusCode = int(statusLine.split()[1]) # split at space

        if statusCode == 200:
            return handle200(fileName, response)
        elif statusCode == 304 and cached:
            return handle304(fileName)
        else:
            return response
        
    except Exception as e:
        return handle500(e)


def handleClient(conn, addr):
    with conn:
        try:
            request = conn.recv(4096).decode()

            print(f"[{addr}] Request:\n{request}")

            response = handleRequest(request)
            conn.sendall(response)

        except Exception as e:
            conn.sendall(handle500(e))


def startProxy():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as p:
        # Allow quickly restart the proxy on the same port
        # without waiting for the OS to release it.
        p.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        p.bind((PROXY_HOST, PROXY_PORT))
        p.listen()

        print(f"Proxy started at http://{PROXY_HOST}:{PROXY_PORT}")

        while True:
            conn, addr = p.accept()
            threading.Thread(target=handleClient, args=(conn, addr)).start()


if __name__ == "__main__":
    startProxy()
