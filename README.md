#### Group 26 - Eric Cheung & Harry Kim

# CMPT 371 – Mini Project 1: HTTP Server & Multiplexed Proxy

This repository contains two Python programs developed for CMPT 371:

- `server.py`: A multithreaded HTTP/1.1 web server built from scratch using raw sockets.
- `proxy.py`: A multiplexed HTTP/1.1 proxy server that forwards client requests to the origin server using a custom framing protocol.

Both components are designed to demonstrate core networking principles, including socket programming, status code handling, concurrency, and head-of-line (HOL) blocking mitigation.

## Status Code Coverage

| Code | Meaning                    | Trigger Condition                     |
| ---- | -------------------------- | ------------------------------------- |
| 200  | OK                         | Valid GET for existing file           |
| 304  | Not Modified               | Conditional GET with unchanged file   |
| 403  | Forbidden                  | Access to `private.html`              |
| 404  | Not Found                  | File not found in base directory      |
| 505  | HTTP Version Not Supported | Request uses unsupported HTTP version |

## Project Structure

| File           | Description                                                  |
| -------------- | ------------------------------------------------------------ |
| `server.py`    | Minimal HTTP server supporting GET requests and status codes |
| `proxy.py`     | Multiplexed proxy server with framing and caching            |
| `test.html`    | Sample file for successful GET requests                      |
| `private.html` | Restricted file to trigger 403 Forbidden                     |
| `README.md`    | Project documentation                                        |
| `Report.pdf`   | Detailed design and testing report (see OneDrive link below) |

## How to Run

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

## Testing Instructions

Please refer to the [Mini Project Report](./CMPT%20371%20Mini%20Project%201%20-%20Report(V1).md).
