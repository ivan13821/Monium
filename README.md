# Monium
This library is designed for working with Monium from Yandex Cloud. It provides a simplified way to write logs and metrics. Internally, it uses the OpenTelemetry protocol.

## Performance
The library uses asynchronous calls for obtaining IAM tokens and API keys. Key renewal and deletion also happen asynchronously.
API keys are cached: if any existing key contains the required set of roles, that key is returned instead of creating a new one. In other words, the role set of an existing key must include the role set of the requested key.

## Security
Several security measures are implemented:
1. IAM token rotation. Tokens have a short lifespan — 1 hour by default — after which they become invalid and are automatically renewed.
2. API key rotation. Each API key is created with the minimum required permissions requested by the user. When the key expires, it is deleted from the cloud and a new one is created.
3. Automatic metadata detection. If the program is running on a Yandex Cloud VM, the library automatically obtains the IAM token from the VM metadata.

## Usage
First, configure the class for token management:

```python
from monium_sdk.security import ServiceAccountConfigData, Tokens

config = ServiceAccountConfigData(
    service_account_id="Service account ID",
    private_key="Private key for the service account",
    key_id="Key ID"
)

# If you are using a file downloaded from Yandex Cloud, you can specify it:

config_path = ServiceAccountConfigData(
    patch="path/to/file"
)

Tokens.service_account_config = config_path
```

After that, you can use all the library's functionality:
```python
import asyncio
from monium_sdk import Telemetry


async def test():
    log = await Telemetry.get_log_manager()
    log.info("First message")


if __name__ == "__main__":
    asyncio.run(test())
```