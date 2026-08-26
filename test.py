import asyncio
from sdk.security import ServiceConfigData, Tokens


asyncio.run(Tokens.init(forced="auto"))