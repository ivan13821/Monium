from dataclasses import dataclass



@dataclass
class ServiceConfigData:
    """Описывает данные сервисного аккаунта, которые используются для подключения к Monium"""
    service_account_id: str
    key_id: str
    private_key: str