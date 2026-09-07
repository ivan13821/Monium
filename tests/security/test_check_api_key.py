import unittest
from datetime import datetime, timedelta, timezone
from typing import Set
from src.monium_sdk.security import ApiKey, Tokens


class TestCheckApiKey(unittest.IsolatedAsyncioTestCase):
    """Тесты для метода Tokens._check_api_key"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        Tokens._api_keys = []

        # Создаем тестовые ключи
        self.valid_key = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=11),
            secret="valid-key",
            scopes={"read", "write", "admin"},
            key_id="iddddd"
        )

        self.expired_key = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=13),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            secret="expired-key",
            scopes={"read", "write"},
            key_id="iddddd"
        )

        self.partial_key = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=11),
            secret="partial-key",
            scopes={"read"},
            key_id="iddddd"
        )

    def create_need_key(self, scopes: Set[str] = None) -> ApiKey:
        """Создает ключ-шаблон для поиска"""
        if scopes is None:
            scopes = {"read", "write", "admin"}

        return ApiKey(
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
            secret="need-key-template",
            scopes=scopes,
            key_id="iddddd"
        )

    async def test_check_api_key_with_need_key_success(self):
        """Тест: ключ найден по need_key (точное совпадение)"""
        Tokens._api_keys = [self.valid_key]
        need_key = self.create_need_key(scopes={"read", "write", "admin"})

        result = await Tokens._check_api_key(need_key=need_key)

        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "valid-key")
        self.assertTrue(result.is_current())

    async def test_check_api_key_with_need_key_superset(self):
        """Тест: ключ найден, если его scopes являются надмножеством"""
        # Ключ с дополнительными scopes
        super_key = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=11),
            secret="super-key",
            scopes={"read", "write", "admin", "delete"},
            key_id="iddddd"
        )
        Tokens._api_keys = [super_key]

        # Ищем ключ с меньшим набором scopes
        need_key = self.create_need_key(scopes={"read", "write"})

        result = await Tokens._check_api_key(need_key=need_key)

        # Должен найти, так как super_key.scopes > need_key.scopes
        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "super-key")

    async def test_check_api_key_with_scopes_success(self):
        """Тест: ключ найден по scopes"""
        Tokens._api_keys = [self.valid_key]
        scopes = {"read", "write", "admin"}

        result = await Tokens._check_api_key(scopes=scopes)

        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "valid-key")

    async def test_check_api_key_with_scopes_superset(self):
        """Тест: ключ найден, если его scopes содержат запрошенные"""
        super_key = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=11),
            secret="super-key",
            scopes={"read", "write", "admin", "delete"},
            key_id="iddddd"
        )
        Tokens._api_keys = [super_key]
        scopes = {"read", "write"}  # Запрашиваем меньше

        result = await Tokens._check_api_key(scopes=scopes)

        # Должен найти, так как super_key.scopes содержит {"read", "write"}
        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "super-key")

    async def test_check_api_key_no_matching_key(self):
        """Тест: ключ с подходящими scopes не найден"""
        Tokens._api_keys = [self.partial_key]  # Только "read"
        scopes = {"read", "write", "admin"}  # Нужны все

        result = await Tokens._check_api_key(scopes=scopes)

        self.assertIsNone(result)
        self.assertEqual(len(Tokens._api_keys), 1)

    async def test_check_api_key_expired_key_removed(self):
        """Тест: истекший ключ с подходящими scopes удаляется"""
        Tokens._api_keys = [self.expired_key]  # Истекший ключ
        scopes = {"read", "write"}

        result = await Tokens._check_api_key(scopes=scopes)

        self.assertIsNone(result)
        self.assertEqual(len(Tokens._api_keys), 0)
        self.assertNotIn(self.expired_key, Tokens._api_keys)

    async def test_check_api_key_remove_only_expired_keys(self):
        """Тест: удаляются только истекшие ключи, валидные остаются"""
        Tokens._api_keys = [self.expired_key, self.valid_key]
        scopes = {"read", "write"}

        result = await Tokens._check_api_key(scopes=scopes)

        # Должен вернуть валидный ключ
        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "valid-key")

        # Истекший должен быть удален
        self.assertEqual(len(Tokens._api_keys), 1)
        self.assertIn(self.valid_key, Tokens._api_keys)
        self.assertNotIn(self.expired_key, Tokens._api_keys)

    async def test_check_api_key_multiple_valid_keys(self):
        """Тест: несколько валидных ключей, возвращается первый подходящий"""
        valid_key1 = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=10),
            secret="valid-key-1",
            scopes={"read", "write", "admin"},
            key_id="iddddd"
        )
        valid_key2 = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=11),
            secret="valid-key-2",
            scopes={"read", "write", "admin"},
            key_id="iddddd"
        )
        Tokens._api_keys = [valid_key1, valid_key2]

        result = await Tokens._check_api_key(scopes={"read", "write", "admin"})

        # Должен вернуть первый подходящий
        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "valid-key-1")
        self.assertEqual(len(Tokens._api_keys), 2)

    async def test_check_api_key_with_both_params_raises_error(self):
        """Тест: передача обоих параметров вызывает ошибку"""
        need_key = self.create_need_key()
        scopes = {"read", "write"}

        with self.assertRaises(RuntimeError) as context:
            await Tokens._check_api_key(need_key=need_key, scopes=scopes)

        self.assertIn("Нужно установить одно из двух значений", str(context.exception))

    async def test_check_api_key_without_params_raises_error(self):
        """Тест: вызов без параметров вызывает ошибку"""
        with self.assertRaises(RuntimeError) as context:
            await Tokens._check_api_key()

        self.assertIn("Нужно установить одно из двух значений", str(context.exception))

    async def test_check_api_key_with_scopes_list(self):
        """Тест: передача scopes как list (не set)"""
        Tokens._api_keys = [self.valid_key]
        scopes = ["read", "write", "admin"]

        result = await Tokens._check_api_key(scopes=scopes)

        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "valid-key")

    async def test_check_api_key_empty_scopes(self):
        """Тест: поиск ключа с пустыми scopes"""
        # Ключ с пустыми scopes
        empty_key = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=11),
            secret="empty-key",
            scopes=set(),
            key_id="iddddd"
        )
        Tokens._api_keys = [empty_key]

        # Ищем ключ с пустыми scopes
        result = await Tokens._check_api_key(scopes=set())

        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "empty-key")
        self.assertNotEqual(result.scopes, set())

    async def test_check_api_key_partial_scopes_match(self):
        """Тест: ключ с частью scopes не подходит"""
        Tokens._api_keys = [self.partial_key]  # Только "read"
        scopes = {"read", "write"}  # Нужны оба

        result = await Tokens._check_api_key(scopes=scopes)

        self.assertIsNone(result)
        self.assertEqual(len(Tokens._api_keys), 1)

    async def test_check_api_key_with_need_key_scopes_priority(self):
        """Тест: поиск ключа с расширенными scopes"""
        key1 = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=11),
            secret="key-with-write",
            scopes={"read", "write"},
            key_id="iddddd"
        )
        key2 = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=11),
            secret="key-with-admin",
            scopes={"read", "write", "admin"},
            key_id="iddddd"
        )
        Tokens._api_keys = [key1, key2]

        # Ищем ключ с admin
        need_key = self.create_need_key(scopes={"read", "write", "admin"})

        result = await Tokens._check_api_key(need_key=need_key)

        # Должен найти ключ с admin (точное совпадение или надмножество)
        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "key-with-admin")

    async def test_check_api_key_remove_multiple_expired_keys(self):
        """Тест: удаление нескольких истекших ключей"""
        expired1 = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=13),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            secret="expired-1",
            scopes={"read"},
            key_id="iddddd"
        )
        expired2 = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=14),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=2),
            secret="expired-2",
            scopes={"read"},
            key_id="iddddd"
        )
        Tokens._api_keys = [expired1, expired2]

        result = await Tokens._check_api_key(scopes={"read"})

        self.assertIsNone(result)
        self.assertEqual(len(Tokens._api_keys), 0)

    async def test_check_api_key_uses_ge_not_gt(self):
        """Тест: используется >= (нестрогое сравнение), а не > (строгое)"""
        # Ключ с теми же scopes
        exact_key = ApiKey(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=11),
            secret="exact-key",
            scopes={"read", "write"},
            key_id="iddddd"
        )
        Tokens._api_keys = [exact_key]

        # Ищем ключ с теми же scopes
        result = await Tokens._check_api_key(scopes={"read", "write"})

        # Должен найти (используется >=, а не >)
        self.assertIsNotNone(result)
        self.assertEqual(result.secret, "exact-key")


if __name__ == '__main__':
    unittest.main()