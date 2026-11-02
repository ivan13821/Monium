# Monium
This library is designed for working with Monium from Yandex Cloud. It provides a simplified way to write logs and metrics. Internally, it uses the OpenTelemetry protocol.
This is not the official Monium library from Yandex Cloud.

## Performance
- The library uses asynchronous calls to obtain IAM tokens and API keys. Renewal and deletion are also performed asynchronously.
- API keys are cached. If any existing key contains the required set of roles, that key is returned. In other words, the role set of an existing key must include the role set of the requested key.
- Token validation runs as a background process, so it does not block the main execution flow.

## Security
Several security measures are implemented:
1. IAM token rotation. Tokens have a short lifespan — 1 hour by default — after which they become invalid and are automatically renewed.
2. API key rotation. Each API key is created with the minimum required permissions requested by the user. When the key expires, it is deleted from the cloud and a new one is created.
3. Automatic metadata detection. If the program is running on a Yandex Cloud VM, the library automatically obtains the IAM token from the VM metadata.

## Usage
First, you need to provide the data for connection.:

```python
from monium_sdk.security import ApiKey, IAMToken

key = ApiKey(
    secret="secret"
)

# or

key = IAMToken(
    secret="secret"
)


```

After that, you can use all the library's functionality:
```python
import asyncio
from monium_sdk import Telemetry
from monium_sdk.security import ApiKey

def test():
    
    key = ApiKey(
        secret="secret"
    )
    
    with Telemetry.logging_start(
        key=key,
        project="folder__<folder_id>",
        service="<service>",
        cluster="<cluster>"
    ) as res:
        Telemetry.log.info("first message")
        Telemetry.log.error("error")
        Telemetry.metric.add_to_counter(count=5)


if __name__ == "__main__":
    test()
```