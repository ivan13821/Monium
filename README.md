# Monium
This library is designed for working with Monium from Yandex Cloud. It provides a simplified way to write logs and metrics. Internally, it uses the OpenTelemetry protocol.
This is not the official Monium library from Yandex Cloud.

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

To update the key, use the update_key function from the Telemetry class.

```python
from monium_sdk.security import ApiKey
from monium_sdk import Telemetry

def test():
    key = ApiKey(
        secret="secret"
    )
    
    Telemetry.update_key(key)
```