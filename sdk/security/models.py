from dataclasses import dataclass



@dataclass
class UpdateToken:
    token_ttl: int # в секундах
    service_account_id: str
    key_id: str
    private_key: str