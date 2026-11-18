"""Network helpers: a DNS cache and a shared HTTP session.

The miner talks to the same handful of Twitch hosts every few seconds. With
plain ``requests.get`` every call opens a new connection and does a fresh DNS
lookup, which adds up to thousands of queries an hour on a home DNS server.
"""
import socket
import threading
import time

import requests
from requests.adapters import HTTPAdapter

DNS_TTL = 300  # seconds

_real_getaddrinfo = socket.getaddrinfo
_cache = {}
_lock = threading.Lock()


def _cached_getaddrinfo(host, port, *args, **kwargs):
    key = (host, port, args, tuple(sorted(kwargs.items())))
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < DNS_TTL:
            return hit[1]
    result = _real_getaddrinfo(host, port, *args, **kwargs)
    with _lock:
        _cache[key] = (now, result)
    return result


def install_dns_cache():
    if socket.getaddrinfo is not _cached_getaddrinfo:
        socket.getaddrinfo = _cached_getaddrinfo


def _make_session():
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


http = _make_session()
