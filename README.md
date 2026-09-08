# Monium
This library is designed for working with Monium from Yandex Cloud. It provides a simplified way to write logs and metrics. Internally, it uses the OpenTelemetry protocol.


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
    
    # Set configuration for log collection
    Telemetry.project = "folder__*****"
    Telemetry.service = "your service"
    Telemetry.cluster = "test"
    
    # Start the background process to refresh local providers.
    # This is needed to update keys and tokens.
    Telemetry.init()
    
    # Collect logs
    Telemetry.log.info("msg")
    Telemetry.log.error("msg for error")
    
    # Collect metrics
    Telemetry.metric.add_to_counter()


if __name__ == "__main__":
    # An active event loop is required for the library to work
    asyncio.run(test())
```