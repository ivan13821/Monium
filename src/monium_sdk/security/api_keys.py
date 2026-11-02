#
# import asyncio
# import atexit
#
# from datetime import datetime, timedelta, timezone
# from typing import List
# import aiohttp
#
# import logging
#
# from monium_sdk.security.models import ApiKey
# from monium_sdk.security.iam_tokens import IAMTokenManager
#
# logger = logging.getLogger(__name__)
#
#
#
# class ApiKeysManager:
#
#
#     _api_keys: List[ApiKey] = []
#
#     _token_ttl = timedelta(minutes=60)
#     _token_update_weight: float = 0.8
#
#     _api_key_lock = asyncio.Lock()
#     _check_api_key_lock = asyncio.Lock()
#
#
#     @classmethod
#     async def _check_api_key(cls, need_key: ApiKey = None, scopes: set|list = None):
#         """Проверяет, существует ли ключ с нужными ролями сейчас"""
#
#         if (need_key is None and scopes is None) or (need_key is not None and scopes is not None):
#             raise RuntimeError("Нужно установить одно из двух значений: need_key или scopes")
#
#         if scopes is not None:
#             need_key = ApiKey(
#                 expires_at=datetime.now(timezone.utc),
#                 created_at=datetime.now(timezone.utc),
#                 scopes=scopes,
#                 secret="",
#                 key_id=""
#             )
#         not_current_keys = []
#         result = None
#         for key in cls._api_keys:
#             if key.is_current():
#                 if key >= need_key:
#                     result = key
#                     break
#             else:
#                 not_current_keys.append(key)
#
#         async with cls._check_api_key_lock:
#             for key in not_current_keys:
#                 await cls.delete_api_key(key.key_id)
#                 if key in cls._api_keys:
#                     cls._api_keys.remove(key)
#
#         return result
#
#
#
#     @classmethod
#     async def get_api_key(cls, scopes: List[str]) -> ApiKey:
#         """
#         Возвращает API-ключ, полученный через HTTPS-запрос.
#
#         Ключ кешируется и обновляется автоматически при приближении к истечению срока действия.
#         Это повышает безопасность и защищает от утечек данных.
#
#         Important:
#             Не рекомендуется сохранять результат работы этой функции статически,
#             так как ключ имеет ограниченное время жизни. Функция возвращает
#             актуальный ключ, но он может быть обновлен при следующем вызове.
#
#         Args:
#             scopes (list[str]): Список областей действия (scopes) для API-ключа.
#                 Определяет, какие операции разрешено выполнять с этим ключом.
#                 Примеры: "yc.monium.logs.write", "yc.monium.metrics.write"
#
#         Returns:
#             str: Актуальный API-ключ для аутентификации.
#
#         Raises:
#             RuntimeError: Если не удалось получить или обновить API-ключ.
#             ValueError: Если передан пустой список scopes.
#
#         Example:
#             >>> async def example():
#             >>>     scopes = [
#             ...         "yc.monium.logs.write",
#             ...         "yc.monium.metrics.write",
#             ...         "yc.monium.traces.write"
#             ...     ]
#             >>>     api_key = await ApiKeysManager.get_api_key(scopes)
#             >>>     print(api_key.secret[:10] + "...")
#         """
#
#         expires_at: datetime = datetime.now(timezone.utc) + cls._token_ttl
#         expires_at_utc = expires_at.astimezone(timezone.utc)
#         expires_at_str = expires_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
#         async with cls._api_key_lock:
#
#             key = await cls._check_api_key(scopes=scopes)
#
#             if key is not None:
#                 return key
#
#             iam_token = await IAMTokenManager.get_iam_token()
#             if not iam_token:
#                 raise Exception("Нет IAM-токена")
#
#             url = "https://iam.api.cloud.yandex.net/iam/v1/apiKeys"
#             headers = {
#                 "Authorization": f"Bearer {iam_token.secret}",
#                 "Content-Type": "application/json"
#             }
#             body = {
#                 "serviceAccountId": IAMTokenManager.service_account_config.service_account_id,
#                 "scopes": scopes,
#                 "expiresAt": expires_at_str
#             }
#             async with aiohttp.ClientSession() as session:
#                 async with session.post(url, headers=headers, json=body) as response:
#
#                     if response.status != 200:
#                         raise Exception(f"Ошибка создания API-ключа: {response.status} - {response.text}")
#
#                     data = await response.json()
#                     key = ApiKey(
#                         created_at=datetime.now(timezone.utc),
#                         expires_at=expires_at,
#                         scopes=scopes,
#                         secret=data.get('secret'),
#                         key_id=data.get('apiKey', {}).get('id')
#                     )
#                     cls._api_keys.append(key)
#
#             return key
#
#
#     @classmethod
#     async def delete_api_key(cls, key_id: str) -> bool:
#         """
#         Удаляет API-ключ по его идентификатору.
#
#         Args:
#             key_id (str): Идентификатор API-ключа
#
#         Returns:
#             bool: True при успешном удалении
#         """
#         iam_token = await IAMTokenManager.get_iam_token()
#         if not iam_token:
#             raise Exception("Нет IAM-токена")
#
#         url = f"https://iam.api.cloud.yandex.net/iam/v1/apiKeys/{key_id}"
#         headers = {
#             "Authorization": f"Bearer {iam_token.secret}",
#             "Content-Type": "application/json"
#         }
#
#         async with aiohttp.ClientSession() as session:
#             async with session.delete(url, headers=headers) as response:
#                 if response.status in [200, 202, 204]:
#                     for i in range(len(cls._api_keys)):
#                         if cls._api_keys[i].key_id == key_id:
#                             cls._api_keys.pop(i)
#                             break
#                     return True
#                 else:
#                     raise Exception(f"Ошибка удаления ключа: {response.status}")
#
#
#
#     @staticmethod
#     def shutdown():
#         """Удаляет все API ключи"""
#         try:
#             print("Начинаем удаление ключей...")
#             loop = asyncio.get_running_loop()
#             task = loop.create_task(ApiKeysManager.delete_all_keys_async())
#             loop.run_until_complete(task)
#         except RuntimeError:
#             asyncio.run(ApiKeysManager.delete_all_keys_async())
#         finally:
#             print(f"Ключи удалены: {ApiKeysManager._api_keys}")
#
#     @classmethod
#     async def delete_all_keys_async(cls):
#         tasks = [cls.delete_api_key(key.key_id) for key in cls._api_keys]
#         await asyncio.gather(*tasks)
#
