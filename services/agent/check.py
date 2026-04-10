"""Health check helper.

Small async utility to test TCP reachability of a host:port.
"""

from __future__ import annotations

import asyncio
import socket

DEFAULT_FAMILY = socket.AF_UNSPEC


async def is_port_open(host: str, port: int) -> bool:
    """Return True if a TCP connection to ``host:port`` can be opened.

    Args:
        host: Hostname or IP address to check.
        port: Port number to check.

    Returns:
        True if a connection was established within the timeout window,
        False otherwise.

    Raises:
        ValueError: If ``port`` is not a valid TCP port number.
    """
    if not isinstance(port, int) or not (0 < port < 65536):
        raise ValueError("port must be an integer in range 1..65535")

    try:
        loop = asyncio.get_running_loop()
        await loop.getaddrinfo(host, port, family=DEFAULT_FAMILY)

        conn = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(conn, timeout=1)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False
