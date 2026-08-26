import asyncio
import time
from datetime import datetime,  timedelta
from typing import List
import aiohttp

import grpc
import jwt
import logging

import requests
from aiohttp import ClientError
from yandex.cloud.iam.v1.iam_token_service_pb2 import CreateIamTokenRequest, CreateIamTokenResponse
from yandex.cloud.iam.v1.iam_token_service_pb2_grpc import IamTokenServiceStub

from sdk.security.models import ServiceConfigData

logger = logging.getLogger(__name__)

class Tokens:
    """Класс для взаимодействия с токенами"""


    _iam_token: str = None
    _iam_token_expires_at: datetime = datetime.now() - timedelta(days=1) # Используется значение вчерашнего дня, чтобы избежать ошибок при работе со временем

    _api_key: str = None
    _api_key_expires_at: datetime = datetime.now() - timedelta(days=1)

    _service_account_config: ServiceConfigData = None
    _service_account_id: str = None

    _token_ttl = timedelta(hours=1)
    _token_update_weight: float = 0.8

    __chanel = None
    __stub = None

    _lock = asyncio.Lock()


    @staticmethod
    async def init(service_account_config: ServiceConfigData = None, forced: str = "auto"):
        """
        Инициализирует фоновое обновление IAM-токенов.

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
            >>>     await Tokens.init()
            >>>
            >>>     # Принудительное использование сервисного аккаунта
            >>>     await Tokens.init(service_account_config, forced="service")
        """

        if forced not in ["auto", "service", "metadata"]:
            raise ValueError(f"Неверное значение для аргумента forced: {forced}")

        time_to_update = Tokens._token_ttl.total_seconds() * Tokens._token_update_weight

        while True:
            # Проверяем, нужно ли уже обновлять токен
            if (datetime.now() - Tokens._iam_token_expires_at).total_seconds() < time_to_update:
                await asyncio.sleep(time_to_update)
                continue

            # Если удается подключится к сервису метаданных и получить оттуда данные, то возвращаемся назад в цикл
            if forced == "auto" or forced == "metadata":
                has_metadata = await Tokens._get_metadata_credentials()
                if has_metadata:
                    await asyncio.sleep(time_to_update)
                    continue
                elif not has_metadata and forced == "metadata":
                    raise RuntimeError("Ошибка при получении данных из сервиса метаданных")


            # Если нет метаданных, тогда используем аккаунт
            if service_account_config is None:
                if forced == "auto":
                    raise RuntimeError("Невозможно подключится к сервису метаданных и не были переданы данные сервисного аккаунта для подключения")
                elif forced == "service":
                    raise ValueError("Не передан сервисный аккаунт для подключения")

            if forced == "auto" or forced == "service":
                success = await Tokens._create_iam_token(config=service_account_config)
                if success:
                    await asyncio.sleep(time_to_update)
                    continue
                elif not success and forced == "service":
                    raise RuntimeError("Ошибка при получении данных c помощью сервисного аккаунта")

            await asyncio.sleep(10)





    @staticmethod
    async def _get_stub():
        """Функция гарантирует, что канал будет инициализирован в правильном event loop"""
        if Tokens.__stub is None:
            Tokens.__chanel = grpc.aio.secure_channel('iam.api.cloud.yandex.net:443', grpc.ssl_channel_credentials())
            Tokens.__stub = IamTokenServiceStub(Tokens.__chanel)
        return Tokens.__stub




    @staticmethod
    async def _create_iam_token(config: ServiceConfigData) -> bool:
        """
        Функция для получения IAM токена по JWT через gRPC.

        Args:
            config: Данные сервисного аккаунта

        Returns:
            bool: True - при успешном получении, False - при ошибке
        """

        stub = await Tokens._get_stub()

        try:
            jwt = Tokens._generate_jwt_token(config)

            request = CreateIamTokenRequest(jwt=jwt)

            response: CreateIamTokenResponse = await stub.Create(request)

            Tokens._iam_token = response.iam_token
            logger.info(f"IAM токен успешно обновлен, истекает: {response.expires_at}")
            return True

        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC ошибка при получении IAM токена: {e.code()} - {e.details()}")

        except Exception as e:
            logger.error(f"Неизвестная ошибка при обновлении токена: {e}")

        return False



    @staticmethod
    async def _get_metadata_credentials() -> bool:
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

                Tokens._iam_token = iam_token
                Tokens._service_account_id = service_account_id
                Tokens._iam_token_expires_at = datetime.now()

                return True

            except ClientError as e:
                logger.error(f"Ошибка при запросе к метаданным: {e}")
            except KeyError as e:
                logger.error(f"Ошибка парсинга JSON ответа с токеном: {e}")
            except (IndexError, AttributeError) as e:
                logger.error(f"Ошибка парсинга email сервисного аккаунта: {e}")
            except Exception as e:
                logger.error(f"Неизвестная ошибка при получении данных из метаданных: {e}")

            return False




    @staticmethod
    def _generate_jwt_token(config: ServiceConfigData):
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
    def get_iam_token() -> str | None:
        """Возвращает токен, если токен не обновился или возникли проблемы при обновлении возвращает None"""
        return Tokens._iam_token



    @staticmethod
    async def get_api_key(scopes: List[str]) -> str:
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
            >>>     print(api_key[:10] + "...")
        """

        expires_at = datetime.now() + Tokens._token_ttl
        if Tokens._api_key_expires_at > datetime.now() + Tokens._token_ttl * Tokens._token_update_weight and Tokens._api_key is not None:
            return Tokens._api_key

        async with Tokens._lock:
            iam_token = Tokens.get_iam_token()
            if not iam_token:
                raise Exception("Нет IAM-токена")

            url = "https://iam.api.cloud.yandex.net/iam/v1/apiKeys"
            headers = {
                "Authorization": f"Bearer {iam_token}",
                "Content-Type": "application/json"
            }
            body = {
                "serviceAccountId": Tokens._service_account_id,
                "scopes": scopes,
                "expiresAt": expires_at
            }

            async with session.post(url, headers=headers, json=body) as response:
                ...

            if response.status_code != 200:
                raise Exception(f"Ошибка создания API-ключа: {response.status_code} - {response.text}")

            data = response.json()
            Tokens._api_key = data.get('secret')
            Tokens._api_key_expires_at = expires_at

        return Tokens._api_key
