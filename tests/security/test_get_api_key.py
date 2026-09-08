import unittest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta, timezone
import asyncio

from monium_sdk.security import IAMToken, ServiceAccountConfigData
from monium_sdk.security import Tokens, ApiKey


class TestTokensGetApiKey(unittest.IsolatedAsyncioTestCase):
    """Тесты для метода Tokens.get_api_key"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        # Очищаем список ключей
        Tokens._api_keys = []
        Tokens._token_ttl = timedelta(hours=1)
        Tokens.service_account_config = ServiceAccountConfigData(
            service_account_id="service_account_id",
            key_id="key_id",
            private_key="private_key"
        )
        Tokens._lock = asyncio.Lock()

        test_scopes = ["yc.monium.logs.write", "yc.monium.metrics.write"]
        self.default_keys = [
            ApiKey(
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
                secret="last secret",
                scopes=["yc.compute.editor", "yc.ai.admin", "yc.monium.logs.write"],
                key_id="iddddd"
            ),
            ApiKey(
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
                secret="last secret",
                scopes=["yc.compute.editor", "yc.ai.admin", "yc.monium.metrics.write"],
                key_id="iddddd"
            ),
            ApiKey(
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
                secret="last secret",
                scopes=["yc.compute.editor", "yc.ai.admin", "yc.monium.logs.write"],
                key_id="iddddd"
            )
        ]
        self.default_keys_ex = [
            *self.default_keys,
            ApiKey(
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) - timedelta(hours=12),
                secret="last secret",
                scopes=["yc.compute.editor", "yc.datalens.admin", "yc.monium.logs.write"],
                key_id="iddddd"
            )
        ]

    def create_mock_response(self, status=200, data=None):
        """Создает мок HTTP-ответа"""
        mock_response = AsyncMock()
        mock_response.status = status
        mock_response.json = AsyncMock(return_value=data or {"secret": "tests-secret-key"})
        mock_response.text = AsyncMock(return_value="")

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        return mock_context

    @patch('monium_sdk.security.Tokens.get_iam_token')
    @patch('aiohttp.ClientSession.post')
    async def test_get_api_key_no_existing_key(self, mock_post, mock_get_iam_token):
        """Тест: ключа нет, создается новый"""
        test_scopes = ["yc.monium.logs.write", "yc.monium.metrics.write"]
        
        # 1. Убеждаемся, что ключей нет
        self.assertEqual(len(Tokens._api_keys), 0)

        # 2. Настраиваем моки
        mock_context = self.create_mock_response(
            status=200,
            data={"secret": "brand-new-secret-key"}
        )
        mock_post.return_value = mock_context

        mock_get_iam_token.return_value = IAMToken(
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            secret="tests-iam-token"
        )

        # 3. Вызываем функцию
        result = await Tokens.get_api_key(test_scopes)

        # 4. Проверяем результат
        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "brand-new-secret-key")
        self.assertEqual(result.scopes, set(test_scopes))

        # 5. Проверяем, что ключ добавлен в список
        self.assertEqual(len(Tokens._api_keys), 1)
        self.assertIn(result, Tokens._api_keys)

        # 6. Проверяем, что HTTP-запрос был сделан
        mock_post.assert_called_once()
        mock_get_iam_token.assert_called_once()

        # 7. Проверяем правильность URL
        call_args = mock_post.call_args
        self.assertEqual(
            call_args[0][0],
            "https://iam.api.cloud.yandex.net/iam/v1/apiKeys"
        )

        # 8. Проверяем правильность заголовков
        headers = call_args[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer tests-iam-token")

        # 9. Проверяем правильность тела запроса
        json_body = call_args[1]["json"]
        self.assertEqual(json_body["serviceAccountId"], Tokens.service_account_config.service_account_id)
        self.assertEqual(json_body["scopes"], test_scopes)
        self.assertIsNotNone(json_body["expiresAt"])



    @patch('monium_sdk.security.Tokens.get_iam_token')
    @patch('aiohttp.ClientSession.post')
    async def test_get_api_key_has_another_keys(self, mock_post, mock_get_iam_token):
        """Тест ключи есть, но у них нет нужных ролей, создается новый ключ"""

        test_scopes = ["yc.monium.logs.write", "yc.monium.metrics.write"]

        # Создаем массив ключей массив
        Tokens._api_keys = self.default_keys.copy()

        # Проверяем длину массива с ключами
        self.assertEqual(len(Tokens._api_keys), len(self.default_keys))

        # 2. Настраиваем моки
        mock_get_iam_token.return_value = IAMToken(
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            secret="tests-iam-token"
        )

        mock_context = self.create_mock_response(
            status=200,
            data={"secret": "brand-new-secret-key"}
        )
        mock_post.return_value = mock_context

        # 3. Вызываем функцию
        result = await Tokens.get_api_key(test_scopes)

        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "brand-new-secret-key")
        self.assertEqual(result.scopes, set(test_scopes))

        # 5. Проверяем, что ключ добавлен в список
        self.assertEqual(len(Tokens._api_keys), len(self.default_keys) + 1)
        self.assertIn(result, Tokens._api_keys)

        # 6. Проверяем, что HTTP-запрос был сделан
        mock_post.assert_called_once()
        mock_get_iam_token.assert_called_once()

        # 7. Проверяем правильность URL
        call_args = mock_post.call_args
        self.assertEqual(
            call_args[0][0],
            "https://iam.api.cloud.yandex.net/iam/v1/apiKeys"
        )

        # 8. Проверяем правильность заголовков
        headers = call_args[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer tests-iam-token")

        # 9. Проверяем правильность тела запроса
        json_body = call_args[1]["json"]
        self.assertEqual(json_body["serviceAccountId"], Tokens.service_account_config.service_account_id)
        self.assertEqual(json_body["scopes"], test_scopes)
        self.assertIsNotNone(json_body["expiresAt"])


    @patch('monium_sdk.security.Tokens.get_iam_token')
    @patch('aiohttp.ClientSession.post')
    async def test_get_api_key_has_need_key(self, mock_post, mock_get_iam_token):
        """Тест ключ есть, и у него есть нужные роли, новы ключ не создается, а используется старый"""

        test_scopes = ["yc.ai.admin", "yc.monium.metrics.write"]

        # Создаем массив ключей
        Tokens._api_keys = self.default_keys

        # Проверяем длину массива с ключами
        self.assertEqual(len(Tokens._api_keys), len(self.default_keys))

        # 2. Настраиваем моки
        mock_get_iam_token.return_value = IAMToken(
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            secret="tests-iam-token"
        )

        mock_context = self.create_mock_response(
            status=200,
            data={"secret": "brand-new-secret-key"}
        )
        mock_post.return_value = mock_context

        # 3. Вызываем функцию
        result = await Tokens.get_api_key(test_scopes)

        # Ключ который должен был вернуться
        existed_key = self.default_keys[1]

        self.assertIsNotNone(result)
        self.assertEqual(result.secret, existed_key.secret)
        self.assertEqual(result.scopes, existed_key.scopes)

        # 5. Проверяем, что ключ не добавлен в список
        self.assertEqual(len(Tokens._api_keys), len(self.default_keys))
        self.assertIn(result, Tokens._api_keys)

        # 6. Проверяем, что HTTP-запрос не был сделан
        mock_post.assert_not_called()
        mock_get_iam_token.assert_not_called()



    @patch('monium_sdk.security.Tokens.get_iam_token')
    @patch('aiohttp.ClientSession.post')
    async def test_get_api_key_has_existed_key(self, mock_post, mock_get_iam_token):
        """Тест нужный ключ есть, но у него истек срок годности. Функция должна удалить старый ключ, а также добавить новый"""

        test_scopes = ["yc.compute.editor", "yc.datalens.admin"]

        # Создаем массив ключей массив
        Tokens._api_keys = self.default_keys_ex.copy()

        # Проверяем длину массива с ключами
        self.assertEqual(len(Tokens._api_keys), len(self.default_keys_ex))

        # 2. Настраиваем моки
        mock_get_iam_token.return_value = IAMToken(
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            secret="tests-iam-token"
        )

        mock_context = self.create_mock_response(
            status=200,
            data={"secret": "brand-new-secret-key"}
        )
        mock_post.return_value = mock_context

        # 3. Вызываем функцию
        result = await Tokens.get_api_key(test_scopes)

        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "brand-new-secret-key")
        self.assertEqual(result.scopes, set(test_scopes))

        # 5. Проверяем, что ключ добавлен в список
        self.assertEqual(len(Tokens._api_keys), len(self.default_keys_ex)) # Потому что один ключ должен быть удален
        self.assertIn(result, Tokens._api_keys)

        # Проверяем что старый ключ был удален
        self.assertNotIn(self.default_keys_ex[-1], Tokens._api_keys)

        # 6. Проверяем, что HTTP-запрос был сделан
        mock_post.assert_called_once()
        mock_get_iam_token.assert_called_once()

        # 7. Проверяем правильность URL
        call_args = mock_post.call_args
        self.assertEqual(
            call_args[0][0],
            "https://iam.api.cloud.yandex.net/iam/v1/apiKeys"
        )

        # 8. Проверяем правильность заголовков
        headers = call_args[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer tests-iam-token")

        # 9. Проверяем правильность тела запроса
        json_body = call_args[1]["json"]
        self.assertEqual(json_body["serviceAccountId"], Tokens.service_account_config.service_account_id)
        self.assertEqual(json_body["scopes"], test_scopes)
        self.assertIsNotNone(json_body["expiresAt"])



if __name__ == '__main__':
    unittest.main()