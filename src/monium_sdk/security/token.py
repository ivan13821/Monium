import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import aiohttp

import grpc
import jwt
import logging

from aiohttp import ClientError
from yandex.cloud.iam.v1.iam_token_service_pb2 import CreateIamTokenRequest, CreateIamTokenResponse
from yandex.cloud.iam.v1.iam_token_service_pb2_grpc import IamTokenServiceStub

from monium_sdk.security.models import ServiceAccountConfigData, ApiKey, IAMToken

logger = logging.getLogger(__name__)

class Tokens:
    """Класс для взаимодействия с токенами"""

    _iam_token = IAMToken(
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        secret=""
    )

    _api_keys: List[ApiKey] = []

    service_account_config: ServiceAccountConfigData = None

    _token_ttl = timedelta(minutes=60)
    _token_update_weight: float = 0.8

    __chanel = None
    __stub = None

    _api_key_lock = asyncio.Lock()
    _iam_token_lock = asyncio.Lock()
    _check_api_key_lock = asyncio.Lock()


    @staticmethod
    async def get_iam_token(service_account_config: ServiceAccountConfigData = None, forced: str = "auto") -> IAMToken:
        """
        Возвращает IAM-токен.

        Определяет источник аутентификации в зависимости от параметра `forced` и окружения.
        При успешной инициализации запускается периодическая задача по обновлению токенов.

        Args:
            service_account_config: Данные для подключения по сервисному аккаунту.
            forced (str): Режим определения источника аутентификации.
                Возможные значения:
                    - "service": Использовать только данные сервисного аккаунта.
                    - "metadata": Использовать только метаданные ВМ (работает только внутри Yandex Cloud).
                    - "auto": Автоматический режим. Если код запущен внутри Yandex Cloud,
                        используются метаданные, иначе — данные сервисного аккаунта.
                        Это значение используется по умолчанию.

        Raises:
            ValueError: Если передан неизвестный режим `forced` или
                не передан `service_account_config` при `forced` = service или auto (если не получилось подключится к мета данным)
            RuntimeError: Если не удалось получить токен из выбранного источника.

        Example:
            >>> async def example():
            >>>     # Автоматический выбор источника
            >>>     await Tokens.get_iam_token()
            >>>
            >>>     # Принудительное использование сервисного аккаунта
            >>>     await Tokens.get_iam_token(service_account_config, forced="service")
        """

        if service_account_config is None and Tokens.service_account_config is not None:
            service_account_config = Tokens.service_account_config


        if forced not in ["auto", "service", "metadata"]:
            raise ValueError(f"Неверное значение для аргумента forced: {forced}")


        # Проверяем, нужно ли уже обновлять токен
        if Tokens._iam_token.is_current():
            return Tokens._iam_token

        # Если удается подключится к сервису метаданных и получить оттуда данные, то возвращаемся назад в цикл
        if forced == "auto" or forced == "metadata":
            token = await Tokens._get_metadata_credentials()
            if token is not None:
                Tokens._iam_token = token
                return token
            elif token is None and forced == "metadata":
                raise RuntimeError("Ошибка при получении данных из сервиса метаданных")


        # Если нет метаданных, тогда используем аккаунт
        if service_account_config is None:
            if forced == "auto":
                raise RuntimeError("Невозможно подключится к сервису метаданных и не были переданы данные сервисного аккаунта для подключения")
            elif forced == "service":
                raise ValueError("Не передан сервисный аккаунт для подключения")

        if forced == "auto" or forced == "service":
            token = await Tokens._create_iam_token(config=service_account_config)
            if token is not None:
                Tokens._iam_token = token
                return token
            elif token is None:
                raise RuntimeError("Ошибка при получении данных c помощью сервисного аккаунта")

        raise RuntimeError("Неизвестная ошибка")





    @staticmethod
    async def _get_stub():
        """Функция гарантирует, что канал будет инициализирован в правильном event loop"""
        if Tokens.__stub is None:
            Tokens.__chanel = grpc.aio.secure_channel('iam.api.cloud.yandex.net:443', grpc.ssl_channel_credentials())
            Tokens.__stub = IamTokenServiceStub(Tokens.__chanel)
        return Tokens.__stub




    @staticmethod
    async def _create_iam_token(config: ServiceAccountConfigData) -> Optional[IAMToken]:
        """
        Функция для получения IAM токена по JWT через gRPC.

        Args:
            config: Данные сервисного аккаунта

        Returns:
            IAMToken: Данные по полученному IAM токену
        """


        if Tokens._iam_token.is_current():
            return Tokens._iam_token

        async with Tokens._iam_token_lock:

            if Tokens._iam_token.is_current():
                return Tokens._iam_token

            stub = await Tokens._get_stub()

            try:

                expires_at = datetime.now(timezone.utc) + Tokens._token_ttl
                jwt = Tokens._generate_jwt_token(config)

                request = CreateIamTokenRequest(jwt=jwt)

                response: CreateIamTokenResponse = await stub.Create(request)

                iam_token = IAMToken(
                    secret=response.iam_token,
                    created_at=datetime.now(timezone.utc),
                    expires_at=expires_at
                )
                logger.info(f"IAM токен успешно обновлен, истекает: {response.expires_at}")
                return iam_token

            except grpc.aio.AioRpcError as e:
                logger.error(f"gRPC ошибка при получении IAM токена: {e.code()} - {e.details()}")

            except Exception as e:
                logger.error(f"Неизвестная ошибка при обновлении токена: {e}")

            return None



    @staticmethod
    async def _get_metadata_credentials(log: bool = False) -> Optional[IAMToken]:
        """Получает IAM токен и ID сервисного аккаунта из метаданных

        Returns:
            bool: True - при успешном получении, False - при ошибке
        """
        headers = {'Metadata-Flavor': 'Google'}
        timeout = aiohttp.ClientTimeout(total=5)

        async with aiohttp.ClientSession() as session:
            token_url = 'http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token'
            id_url = 'http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/email'

            try:
                token_coro = session.get(token_url, headers=headers, timeout=timeout)
                id_coro = session.get(id_url, headers=headers, timeout=timeout)

                # Выполняем их параллельно
                token_resp, id_resp = await asyncio.gather(token_coro, id_coro)

                token_resp.raise_for_status()
                id_resp.raise_for_status()

                token_data = await token_resp.json()
                iam_token = token_data['access_token']

                service_account_email = await id_resp.text()
                service_account_id = service_account_email.split('@')[0]

                Tokens._service_account_id = service_account_id

                return IAMToken(
                    created_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    secret=iam_token
                )

            except ClientError as e:
                if log:
                    logger.error(f"Ошибка при запросе к метаданным: {e}")
            except KeyError as e:
                if log:
                    logger.error(f"Ошибка парсинга JSON ответа с токеном: {e}")
            except (IndexError, AttributeError) as e:
                if log:
                    logger.error(f"Ошибка парсинга email сервисного аккаунта: {e}")
            except Exception as e:
                if log:
                    logger.error(f"Неизвестная ошибка при получении данных из метаданных: {e}")

            return None




    @staticmethod
    def _generate_jwt_token(config: ServiceAccountConfigData):
        """Функция для получения JWT токена"""

        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': config.service_account_id,
            'iat': now,
            'exp': now + Tokens._token_ttl.total_seconds()
        }

        encoded_jwt = jwt.encode(
            payload,
            config.private_key,
            algorithm='PS256',
            headers={'kid': config.key_id}
        )

        return encoded_jwt




    @staticmethod
    async def _check_api_key(need_key: ApiKey = None, scopes: set|list = None):
        """Проверяет, существует ли ключ с нужными ролями сейчас"""

        if (need_key is None and scopes is None) or (need_key is not None and scopes is not None):
            raise RuntimeError("Нужно установить одно из двух значений: need_key или scopes")

        if scopes is not None:
            need_key = ApiKey(
                expires_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                scopes=scopes,
                secret="",
                key_id=""
            )
        not_current_keys = []
        result = None
        for key in Tokens._api_keys:
            if key.is_current():
                if key >= need_key:
                    result = key
                    break
            else:
                not_current_keys.append(key)

        async with Tokens._check_api_key_lock:
            for key in not_current_keys:
                await Tokens.delete_api_key(key.key_id)
                if key in Tokens._api_keys:
                    Tokens._api_keys.remove(key)

        return result



    @staticmethod
    async def get_api_key(scopes: List[str]) -> ApiKey:
        """
        Возвращает API-ключ, полученный через HTTPS-запрос.

        Ключ кешируется и обновляется автоматически при приближении к истечению срока действия.
        Это повышает безопасность и защищает от утечек данных.

        Important:
            Не рекомендуется сохранять результат работы этой функции статически,
            так как ключ имеет ограниченное время жизни. Функция возвращает
            актуальный ключ, но он может быть обновлен при следующем вызове.

        Args:
            scopes (list[str]): Список областей действия (scopes) для API-ключа.
                Определяет, какие операции разрешено выполнять с этим ключом.
                Примеры: "yc.monium.logs.write", "yc.monium.metrics.write"

        Returns:
            str: Актуальный API-ключ для аутентификации.

        Raises:
            RuntimeError: Если не удалось получить или обновить API-ключ.
            ValueError: Если передан пустой список scopes.

        Example:
            >>> async def example():
            >>>     scopes = [
            ...         "yc.monium.logs.write",
            ...         "yc.monium.metrics.write",
            ...         "yc.monium.traces.write"
            ...     ]
            >>>     api_key = await Tokens.get_api_key(scopes)
            >>>     print(api_key.secret[:10] + "...")
        """

        expires_at: datetime = datetime.now(timezone.utc) + Tokens._token_ttl
        expires_at_utc = expires_at.astimezone(timezone.utc)
        expires_at_str = expires_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        async with Tokens._api_key_lock:

            key = await Tokens._check_api_key(scopes=scopes)

            if key is not None:
                return key


            iam_token = await Tokens.get_iam_token()
            if not iam_token:
                raise Exception("Нет IAM-токена")

            url = "https://iam.api.cloud.yandex.net/iam/v1/apiKeys"
            headers = {
                "Authorization": f"Bearer {iam_token.secret}",
                "Content-Type": "application/json"
            }
            body = {
                "serviceAccountId": Tokens.service_account_config.service_account_id,
                "scopes": scopes,
                "expiresAt": expires_at_str
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=body) as response:

                    if response.status != 200:
                        raise Exception(f"Ошибка создания API-ключа: {response.status} - {response.text}")

                    data = await response.json()
                    key = ApiKey(
                        created_at=datetime.now(timezone.utc),
                        expires_at=expires_at,
                        scopes=scopes,
                        secret=data.get('secret'),
                        key_id=data.get('apiKey', {}).get('id')
                    )
                    Tokens._api_keys.append(key)

            return key


    @staticmethod
    async def delete_api_key(key_id: str) -> bool:
        """
        Удаляет API-ключ по его идентификатору.

        Args:
            key_id (str): Идентификатор API-ключа

        Returns:
            bool: True при успешном удалении
        """
        iam_token = await Tokens.get_iam_token()
        if not iam_token:
            raise Exception("Нет IAM-токена")

        url = f"https://iam.api.cloud.yandex.net/iam/v1/apiKeys/{key_id}"
        headers = {
            "Authorization": f"Bearer {iam_token.secret}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as response:
                if response.status in [200, 202, 204]:
                    return True
                else:
                    raise Exception(f"Ошибка удаления ключа: {response.status}")
