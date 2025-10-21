# CMPT 371 – Mini Project 1: HTTP Server & Multiplexed Proxy

This repository contains two Python programs developed for CMPT 371:

- `server.py`: A multithreaded HTTP/1.1 web server built from scratch using raw sockets.
- `proxy.py`: A multiplexed HTTP/1.1 proxy server that forwards client requests to the origin server using a custom framing protocol.

Both components are designed to demonstrate core networking principles, including socket programming, status code handling, concurrency, and head-of-line (HOL) blocking mitigation.

All design specfication and testing evidence are available in the [Project Documentation Repository](https://1sfu-my.sharepoint.com/:f:/g/personal/hccheung_sfu_ca/EhXuUQntbspIpA6dXq50MMgBR2rVAXpNZdv7SmHtdBoSvg).


## Project Structure

| File          | Description                                                  |
|---------------|--------------------------------------------------------------|
| `server.py`   | Minimal HTTP server supporting GET requests and status codes |
| `proxy.py`    | Multiplexed proxy server with framing and caching            |
| `test.html`   | Sample file for successful GET requests                      |
| `private.html`| Restricted file to trigger 403 Forbidden                     |
| `README.md`   | Project documentation                                        |
| `Report.pdf`  | Detailed design and testing report (see OneDrive link below) |

##  How to Run

### 1. Start the Origin Server

```
python3 server.py
```
- Default host: `127.0.0.1`
    
- Default port: `8080`
    

### 2. Start the Proxy Server

```
python3 proxy.py
```

- Proxy listens on `127.0.0.1:8081`
    
- Forwards requests to origin server at `127.0.0.1:8080`

##  Testing Instructions

###  Browser Testing

- Place `test.html` in the same directory.
    
- Navigate to: `http://127.0.0.1:8080/test.html` (direct) or configure browser to use proxy at `127.0.0.1:8081` and visit same URL.
    

###  Terminal Testing

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

To test via proxy, add `--proxy 127.0.0.1:8081` to each `curl` command.

## Status Code Coverage

|Code|Meaning|Trigger Condition|
|---|---|---|
|200|OK|Valid GET for existing file|
|304|Not Modified|Conditional GET with unchanged file|
|403|Forbidden|Access to `private.html`|
|404|Not Found|File not found in base directory|
|505|HTTP Version Not Supported|Request uses unsupported HTTP version|

## Authors

- Eric Cheung  
- Harry Kim  
_Group 26 – October 2025_
