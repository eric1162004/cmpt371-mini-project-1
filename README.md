## CMPT 371 Mini Project 1: Simple Web Server 

This repository contains the implementation of a minimal HTTP web server written in Python for CMPT 371. The server is built from scratch using socket programming (no http.server or other high-level HTTP libraries).

## Key features:

- Handles basic HTTP/1.1 GET requests.
- Generates correct responses for the following status codes:

|Status Code|Title|
|-----------|-----|
|200|OK|
|304|Not Modified|
|403|forbidden|
|404|Not Found|
|505|HTTP Version Not Supported|

## How to Run the Server

1. Clone or download this repository.
2. Navigate into the project directory: 

```
cd CMPT371-MP1
```

3. Start the server:

```
python3 server.py
```

By default, the server listens on `127.0.0.1:8080`. You can change the host/port in `server.py` if needed.

## How to Test the Server

### Using a Web Browser

1. Place `test.html` in the same directory as `server.py`.

2. Open your browser and visit:

```
http://127.0.0.1:8080/test.html
```
If successful, you should see the contents of test.html.

### Using Terminal Commands

You can simulate different requests and verify status codes:

```
# 200 OK
curl -v http://127.0.0.1:8080/test.html

# 404 Not Found
curl -v http://127.0.0.1:8080/missing.html

# 403 Forbidden
curl -v http://127.0.0.1:8080/private.html

# 304 Not Modified
curl -v -H "If-Modified-Since: Wed, 18 Oct 2025 10:00:00 GMT" http://127.0.0.1:8080/test.html

# 505 HTTP Version Not Supported
printf "GET /test.html HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n" | nc 127.0.0.1 8080
```

### Accessing Documentation
All project documentation (requirements, design notes, and reports) is stored in our shared OneDrive folder.

> [!WARNING]  
> DO NOT SHARE REPO LINK:
> https://1sfu-my.sharepoint.com/:f:/g/personal/hccheung_sfu_ca/EhXuUQntbspIpA6dXq50MMgBR2rVAXpNZdv7SmHtdBoSvg?e=pMD6lD

## Contributors
Eric Cheung, Harry Kim
