import asyncio
import time
from datetime import datetime,  timedelta
from utils import DateTime
from typing import List, Optional
import pytz

import grpc
import jwt
import logging

import requests
from yandex.cloud.iam.v1.iam_token_service_pb2 import CreateIamTokenRequest, CreateIamTokenResponse
from yandex.cloud.iam.v1.iam_token_service_pb2_grpc import IamTokenServiceStub

from config import Config
from security.models import UpdateToken

logger = logging.getLogger(__name__)

class Tokens:
    """Класс для взаимодействия с токенами"""

    _update_time: timedelta = timedelta(hours=12)

    _iam_token: str = None
    _api_key: str = None
    _api_key_expires_at: datetime = datetime.now()

    __chanel = None
    __stub = None

    @staticmethod
    async def _get_stub():
        """Функция гарантирует, что канал будет инициализирован в правильном event loop"""
        if Tokens.__stub is None:
            Tokens.__chanel = grpc.aio.secure_channel('iam.api.cloud.yandex.net:443', grpc.ssl_channel_credentials())
            Tokens.__stub = IamTokenServiceStub(Tokens.__chanel)
        return Tokens.__stub


    @staticmethod
    async def update_token(config: UpdateToken):
        """
        Функция для получения IAM токена по JWT в фоне через gRPC.
        """

        stub = await Tokens._get_stub()

        while True:
            try:
                jwt = Tokens._generate_jwt_token(config)

                request = CreateIamTokenRequest(jwt=jwt)

                response: CreateIamTokenResponse = await stub.Create(request)

                Tokens._iam_token = response.iam_token
                logger.info(f"IAM токен успешно обновлен, истекает: {response.expires_at}")

                await asyncio.sleep(int(config.token_ttl * 0.8))

            except grpc.aio.AioRpcError as e:
                logger.error(f"gRPC ошибка при получении IAM токена: {e.code()} - {e.details()}")
                Tokens._iam_token = None
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Неизвестная ошибка при обновлении токена: {e}")
                Tokens._iam_token = None
                await asyncio.sleep(10)




    @staticmethod
    def _generate_jwt_token(config: UpdateToken):
        """Функция для получения JWT токена"""

        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': config.service_account_id,
            'iat': now,
            'exp': now + config.token_ttl
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
    async def get_api_key(scopes: List[str], expires_at: Optional[datetime] = None) -> str:
        """Возвращает API ключ через HTTP запрос"""

        if expires_at is None: expires_at = datetime.now() + Tokens._update_time


        if Tokens._api_key_expires_at <= datetime.now() + Tokens._update_time * 0.5 or Tokens._api_key is None:
            iam_token = Tokens.get_iam_token()
            if not iam_token:
                raise Exception("Нет IAM-токена")

            url = "https://iam.api.cloud.yandex.net/iam/v1/apiKeys"
            headers = {
                "Authorization": f"Bearer {iam_token}",
                "Content-Type": "application/json"
            }
            body = {
                "serviceAccountId": Config.service_account_id,
                "scopes": scopes
            }

            if expires_at:
                moscow_tz = pytz.timezone('Europe/Moscow')

                if expires_at.tzinfo is None:
                    expires_at = moscow_tz.localize(expires_at)

                expires_at_utc = expires_at.astimezone(pytz.UTC)
                body["expiresAt"] = expires_at_utc.isoformat(timespec='seconds')

            response = requests.post(url, headers=headers, json=body)

            if response.status_code != 200:
                raise Exception(f"Ошибка создания API-ключа: {response.status_code} - {response.text}")

            data = response.json()
            Tokens._api_key = data.get('secret')

        return Tokens._api_key





