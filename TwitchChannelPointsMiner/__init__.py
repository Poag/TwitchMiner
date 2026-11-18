# -*- coding: utf-8 -*-
__version__ = "1.1.0"

from .net import install_dns_cache  # noqa: E402

install_dns_cache()
from .TwitchChannelPointsMiner import TwitchChannelPointsMiner

__all__ = [
    "TwitchChannelPointsMiner",
]
