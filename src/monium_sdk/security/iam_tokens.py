# import asyncio
# import logging
# from datetime import datetime, timezone, timedelta
# from typing import Optional
# import time
# import aiohttp
# import grpc
# import jwt
# from aiohttp import ClientError
# from yandex.cloud.iam.v1.iam_token_service_pb2 import CreateIamTokenRequest, CreateIamTokenResponse
# from yandex.cloud.iam.v1.iam_token_service_pb2_grpc import IamTokenServiceStub
#
# from monium_sdk.security import IAMToken, ServiceAccountConfigData
#
# logger = logging.getLogger(__name__)
#
# class IAMTokenManager:
#
#     _iam_token = IAMToken(
#         created_at=datetime.now(timezone.utc) - timedelta(days=2),
#         expires_at=datetime.now(timezone.utc) - timedelta(days=1),
#         secret=""
#     )
#
#     service_account_config: ServiceAccountConfigData = None
#
#     _token_ttl = timedelta(minutes=60)
#     _token_update_weight: float = 0.8
#
#     __stub = None
#     __chanel = None
#
#     _create_iam_token_lock = asyncio.Lock()
#     _get_iam_token_lock = asyncio.Lock()
#
#
#
#     @classmethod
#     async def _get_stub(cls):
#         """Функция гарантирует, что канал будет инициализирован в правильном event loop"""
#         if cls.__stub is None:
#             cls.__chanel = grpc.aio.secure_channel('iam.api.cloud.yandex.net:443', grpc.ssl_channel_credentials())
#             cls.__stub = IamTokenServiceStub(cls.__chanel)
#         return cls.__stub
#
#
#
#     @classmethod
#     async def get_iam_token(cls, service_account_config: ServiceAccountConfigData = None) -> IAMToken:
#         """
#         Возвращает IAM-токен.
#
#         Определяет источник аутентификации в зависимости от параметра `forced` и окружения.
#         При успешной инициализации запускается периодическая задача по обновлению токенов.
#
#         Args:
#             service_account_config: Данные для подключения по сервисному аккаунту.
#
#         Raises:
#             ValueError: Если передан неизвестный режим `forced` или
#                 не передан `service_account_config` при `forced` = service или auto (если не получилось подключится к мета данным)
#             RuntimeError: Если не удалось получить токен из выбранного источника.
#
#         Example:
#             >>> async def example():
#             >>>     # Автоматический выбор источника
#             >>>     await IAMTokenManager.get_iam_token()
#             >>>
#             >>>     # Принудительное использование сервисного аккаунта
#             >>>     await IAMTokenManager.get_iam_token(service_account_config, forced="service")
#         """
#
#         if service_account_config is None and cls.service_account_config is not None:
#             service_account_config = cls.service_account_config
#
#
#         # Проверяем, нужно ли уже обновлять токен
#         if cls._iam_token.is_current():
#             return cls._iam_token
#
#         async with cls._get_iam_token_lock:
#
#             if cls._iam_token.is_current():
#                 return cls._iam_token
#
#             # Если удается подключится к сервису метаданных и получить оттуда данные, то возвращаемся назад в цикл
#             token = await cls._get_metadata_credentials()
#             if token is not None:
#                 cls._iam_token = token
#                 return token
#
#
#             # Если нет метаданных, тогда используем аккаунт
#             if service_account_config is None:
#                 raise RuntimeError("Невозможно подключится к сервису метаданных и не были переданы данные сервисного аккаунта для подключения")
#
#             token = await cls._create_iam_token(config=service_account_config)
#             if token is not None:
#                 cls._iam_token = token
#                 return token
#             elif token is None:
#                 raise RuntimeError("Ошибка при получении данных c помощью сервисного аккаунта")
#
#             raise RuntimeError("Неизвестная ошибка")
#
#
#
#
#     @classmethod
#     async def _create_iam_token(cls, config: ServiceAccountConfigData) -> Optional[IAMToken]:
#         """
#         Функция для получения IAM токена по JWT через gRPC.
#
#         Args:
#             config: Данные сервисного аккаунта
#
#         Returns:
#             IAMToken: Данные по полученному IAM токену
#         """
#
#
#         if cls._iam_token.is_current():
#             return cls._iam_token
#
#         async with cls._create_iam_token_lock:
#
#             if cls._iam_token.is_current():
#                 return cls._iam_token
#
#             stub = await cls._get_stub()
#
#             try:
#
#                 expires_at = datetime.now(timezone.utc) + cls._token_ttl
#                 jwt = cls._generate_jwt_token(config)
#
#                 request = CreateIamTokenRequest(jwt=jwt)
#
#                 response: CreateIamTokenResponse = await stub.Create(request)
#
#                 iam_token = IAMToken(
#                     secret=response.iam_token,
#                     created_at=datetime.now(timezone.utc),
#                     expires_at=expires_at
#                 )
#                 logger.info(f"IAM токен успешно обновлен, истекает: {response.expires_at}")
#                 return iam_token
#
#             except grpc.aio.AioRpcError as e:
#                 logger.error(f"gRPC ошибка при получении IAM токена: {e.code()} - {e.details()}")
#
#             except Exception as e:
#                 logger.error(f"Неизвестная ошибка при обновлении токена: {e}")
#
#             return None
#
#
#
#     @classmethod
#     async def _get_metadata_credentials(cls, log: bool = False) -> Optional[IAMToken]:
#         """Получает IAM токен и ID сервисного аккаунта из метаданных
#
#         Returns:
#             bool: True - при успешном получении, False - при ошибке
#         """
#         headers = {'Metadata-Flavor': 'Google'}
#         timeout = aiohttp.ClientTimeout(total=5)
#
#         async with aiohttp.ClientSession() as session:
#             token_url = 'http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token'
#             id_url = 'http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/email'
#
#             try:
#                 token_coro = session.get(token_url, headers=headers, timeout=timeout)
#                 id_coro = session.get(id_url, headers=headers, timeout=timeout)
#
#                 # Выполняем их параллельно
#                 token_resp, id_resp = await asyncio.gather(token_coro, id_coro)
#
#                 token_resp.raise_for_status()
#                 id_resp.raise_for_status()
#
#                 token_data = await token_resp.json()
#                 iam_token = token_data['access_token']
#
#                 service_account_email = await id_resp.text()
#                 service_account_id = service_account_email.split('@')[0]
#
#                 cls._service_account_id = service_account_id
#
#                 return IAMToken(
#                     created_at=datetime.now(timezone.utc),
#                     expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
#                     secret=iam_token
#                 )
#
#             except ClientError as e:
#                 if log:
#                     logger.error(f"Ошибка при запросе к метаданным: {e}")
#             except KeyError as e:
#                 if log:
#                     logger.error(f"Ошибка парсинга JSON ответа с токеном: {e}")
#             except (IndexError, AttributeError) as e:
#                 if log:
#                     logger.error(f"Ошибка парсинга email сервисного аккаунта: {e}")
#             except Exception as e:
#                 if log:
#                     logger.error(f"Неизвестная ошибка при получении данных из метаданных: {e}")
#
#             return None
#
#
#
#
#     @classmethod
#     def _generate_jwt_token(cls, config: ServiceAccountConfigData):
#         """Функция для получения JWT токена"""
#
#         now = int(time.time())
#         payload = {
#             'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
#             'iss': config.service_account_id,
#             'iat': now,
#             'exp': now + cls._token_ttl.total_seconds()
#         }
#
#         encoded_jwt = jwt.encode(
#             payload,
#             config.private_key,
#             algorithm='PS256',
#             headers={'kid': config.key_id}
#         )
#
#         return encoded_jwt
#
#
#
#
