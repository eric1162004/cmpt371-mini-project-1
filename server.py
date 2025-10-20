"""
CMPT 371 - Mini Project 1: HTTP Web Server
Authors: Eric Cheung, Harry Kim
MP-Group: 26
Date: October 29, 2025

Description:
This Python script implements a minimal HTTP/1.1 web server using raw sockets.
It handles basic GET requests and returns appropriate HTTP status codes:
200 OK, 304 Not Modified, 403 Forbidden, 404 Not Found, and 505 HTTP Version Not Supported.

Modular handler functions are used to encapsulate response logic for each status code.
The server reads static files from the local directory and supports conditional requests
via the 'If-Modified-Since' header.

Usage:
- Place HTML files (e.g., test.html, private.html) in the same directory.
- Run the server: `python server.py`
- Test using curl, browser, or telnet.

© 2025 Eric Cheung, Harry Kim. All rights reserved.
"""

# For creating TCP sockets, binding, listening, accepting, sending/receiving data
import socket

# For filesystem operations (e.g., joining paths, checking file existence, getting modification times)
import os

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
    # Build the HTTP status line: e.g. "HTTP/1.1 200 OK"
    statusLine = f"{VERSION} {statusCode} {STATUS[statusCode]['title']}\r\n"

    # Initialize headers dictionary
    headers = {}

    # Add headers
    headers.setdefault("Date", formatdate(timeval=None, localtime=False, usegmt=True))
    headers.setdefault("Server", "TestServer/1.0")

    # If there is a body, include Content-Length and Content-Type
    if body:
        headers["Content-Length"] = str(len(body))
        headers["Content-Type"] = "text/html"

    # Convert headers dict into properly formatted HTTP header lines
    # Each header must end with CRLF
    headerLines = "".join(f"{k}: {v}\r\n" for k, v in headers.items())

    # Final response: status line + headers + blank line + body
    return f"{statusLine}{headerLines}\r\n{body}"


def handle200(filePath):
    # Open the requested file in read mode
    # Read its entire contents into 'body'
    with open(filePath, "r") as f:
        body = f.read()
    return createResponse(200, body)


def handle304(filePath, headerLine):
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
    # Return a 403 Forbidden response with the predefined HTML body
    return createResponse(403, STATUS[403]["body"])


def handle404():
    # Return a 404 Not Found response with the predefined HTML body
    return createResponse(404, STATUS[404]["body"])


def handle505():
    # Return a 505 HTTP Version Not Supported response with the predefined HTML body
    return createResponse(505, STATUS[505]["body"])


def handle500(error):
    msg = STATUS[500]["body"]

    # Append the error details inside a <p> tag for debugging
    msg += f"<p>{error}</p>"

    # Return a 500 Internal Server Error response with details
    return createResponse(500, msg)


def handleRequest(request):
    try:
        # Split the raw HTTP request into lines using CRLF
        lines = request.split("\r\n")
        print(f"Request lines: {lines}")

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


def startServer():
    # Create a TCP/IP socket using IPv4 addressing
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

        # Bind the socket to a specific host and port
        s.bind((HOST, PORT))

        # Put the socket into listening mode
        # so it can accept incoming connections
        s.listen()

        print(f"Server started at http://{HOST}:{PORT}")

        # Continuously accept and handle client requests
        while 1:
            conn, addr = s.accept()
            with conn:
                # Receive up to 1024 bytes of data from the client
                # Decode from bytes to string (assuming UTF-8 by default)
                request = conn.recv(1024).decode()

                print(f"Request from {addr}:\n{request}")

                # Pass the request string to a handler function
                # handleRequest() should return a response string
                response = handleRequest(request)

                # Send the response back to the client, encoded as bytes
                conn.sendall(response.encode())


# Ensures that code only runs when the file is executed directly
if __name__ == "__main__":
    startServer()
