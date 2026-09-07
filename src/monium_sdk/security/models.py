import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import total_ordering
from typing import List, Set


@dataclass
class ServiceAccountConfigData:
    """Описывает данные сервисного аккаунта, которые используются для подключения к Monium"""
    service_account_id: str = None
    key_id: str = None
    private_key: str = None
    patch: str = None

    def __post_init__(self):
        if (None in [self.private_key, self.key_id, self.service_account_id]) and (self.patch is None):
            raise ValueError("""Нужно указать либо конфигурационные данные 
            (private_key, key_id, service_account_id) для сервисного аккаунта, 
            либо путь до файла с ними (patch) в формате: 
            {
              "id": "",
              "service_account_id": "",
              "created_at": "",
              "key_algorithm": "",
              "public_key": "",
              "private_key": ""
            }
            """)

        if self.patch is not None:
            self._parse_conf_file(self.patch)


    def _parse_conf_file(self, patch: str):
        """Получает данные из конфигурационного файла"""
        with open(patch, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.service_account_id = data.get("service_account_id")
            self.key_id = data.get('id')
            self.private_key = data.get('private_key')

            if None in [self.private_key, self.key_id, self.service_account_id]:
                raise ValueError("Неверный формат json файла")


@dataclass
class DefaultSecret:
    """Класс для описания базового поведения секретов"""
    created_at: datetime
    expires_at: datetime
    secret: str

    def is_current(self, weight: float = 0.7, strict: bool = True) -> bool:
        """
        Определяет, актуальный ли ключ

        Args:
            weight: Коэффициент обновления (0-1).
                   0 - обновлять сразу, 1 - обновлять в момент истечения
            strict: True - считать неактуальным ровно в момент порога,
                    False - считать актуальным до порога включительно

        Returns:
            True - актуальный
            False - просроченный
        """
        # 1. Проверка на валидность данных
        if self.expires_at <= self.created_at:
            return False

        # 2. Приводим все даты к одному часовому поясу (UTC)
        now = datetime.now(timezone.utc)
        created_at = self.created_at
        expires_at = self.expires_at

        # Если даты naive - добавляем UTC
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        # 3. Абсолютная проверка (токен физически истёк)
        if now >= expires_at:
            return False

        # 4. Проверка по весу
        total_lifetime = (expires_at - created_at).total_seconds()
        weighted_lifetime = total_lifetime * weight

        # Ограничиваем максимальное значение (не больше абсолютного срока)
        max_lifetime = min(weighted_lifetime, total_lifetime)

        past_time = (now - created_at).total_seconds()

        # 5. Учёт strict режима
        if strict:
            return past_time < max_lifetime
        else:
            return past_time <= max_lifetime


    def time_to_expires(self) -> float:
        """
        Возвращает кол-во секунд до того момента как ключ будет просрочен

        Returns:
            float - кол-во секунд до окончания ключа
        """

        return (datetime.now(timezone.utc) - self.expires_at).total_seconds()


@dataclass
class IAMToken(DefaultSecret):
    """Модель для описания IAM токена"""


@dataclass
@total_ordering
class ApiKey(DefaultSecret):
    """Модель для описания API ключа"""
    scopes: Set[str] | List[str]
    key_id: str

    def __post_init__(self):

        if self.scopes is None:
            raise TypeError("scopes cannot be None")

        if not self.scopes:
            self.scopes = {"yc.ai.imageGeneration.execute", "yc.ai.languageModels.execute",
                           "yc.ai.speechkitStt.execute", "yc.ai.speechkitTts.execute", "yc.ai.translate.execute",
                           "yc.ai.vision.execute", "yc.monitoring.manage", "yc.search-api.execute",
                           "yc.serverless.containers.invoke", "yc.serverless.functions.invoke"}

        else:
            # Преобразуем в множество (удаляем дубликаты и приводим к правильному типу)
            self.scopes = set(self.scopes)

    @property
    def key(self) -> str:
        """
        Ключ для идентификации ключа среди других ключей.
        Содержит в себе роли.
        """
        return "|".join(sorted(list(self.scopes)))

    def __eq__(self, other):
        if not isinstance(other, ApiKey):
            return NotImplemented
        return self.scopes == other.scopes

    def __lt__(self, other):
        """self < other если self.scopes строгое подмножество other.scopes"""
        if not isinstance(other, ApiKey):
            return NotImplemented
        return self.scopes < other.scopes

    def __le__(self, other):
        """self <= other если self.scopes подмножество other.scopes"""
        if not isinstance(other, ApiKey):
            return NotImplemented
        return self.scopes <= other.scopes

    def __gt__(self, other):
        """self > other если self.scopes строгое надмножество other.scopes"""
        if not isinstance(other, ApiKey):
            return NotImplemented
        return self.scopes > other.scopes

    def __ge__(self, other):
        """self >= other если self.scopes надмножество other.scopes"""
        if not isinstance(other, ApiKey):
            return NotImplemented
        return self.scopes >= other.scopes


    def info(self):
        return f"Идентификатор: {self.key_id} | Роли: {self.scopes}"

