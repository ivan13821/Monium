
import unittest
from datetime import datetime, timedelta, timezone
from src.monium_sdk.security.models import ApiKey

class TestApiKey(unittest.TestCase):
    """Тесты для ApiKey"""

    def setUp(self):
        """Выполняется перед каждым тестом"""
        self.created_at = datetime.now(timezone.utc)
        self.expires_at = self.created_at + timedelta(days=30)
        self.scopes = ["yc.ai.languageModels.execute", "yc.ai.vision.execute"]

        self.api_key = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="test_secret",
            scopes=self.scopes,
            key_id="idddd"
        )

    def tearDown(self):
        """Выполняется после каждого теста"""
        pass

    def test_created_at(self):
        """Тест: проверка created_at"""
        self.assertEqual(self.api_key.created_at, self.created_at)
        self.assertIsNotNone(self.api_key.created_at)

    def test_expires_at(self):
        """Тест: проверка expires_at"""
        self.assertEqual(self.api_key.expires_at, self.expires_at)

    def test_scopes_initialization(self):
        """Тест: инициализация scopes"""
        expected = list(set(self.scopes))  # Уникальные scopes
        self.assertEqual(self.api_key.scopes, expected)

    def test_default_scopes(self):
        """Тест: scopes по умолчанию"""
        key = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="test_secret",
            scopes=[],
            key_id="iddddd"
        )
        self.assertIsNotNone(key.scopes)
        self.assertGreater(len(key.scopes), 0)

    def test_is_current(self):
        """Тест: проверка актуальности ключа"""
        self.assertTrue(self.api_key.is_current())

        now_utc = datetime.now(timezone.utc)
        old_key = ApiKey(
            created_at=now_utc - timedelta(minutes=60),
            expires_at=now_utc - timedelta(minutes=5),
            secret="old_secret",
            scopes=[],
            key_id="iddddd"
        )
        self.assertFalse(old_key.is_current())

    def test_key_property(self):
        """Тест: генерация ключа"""
        expected_key = "|".join(sorted(self.scopes))
        self.assertEqual(self.api_key.key, expected_key)

    def test_equality(self):
        """Тест: сравнение ключей"""
        key1 = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="secret1",
            scopes=["scope2", "scope1"],
            key_id="iddddd"
        )
        key2 = ApiKey(
            created_at=self.created_at + timedelta(days=1),
            expires_at=self.expires_at + timedelta(days=1),
            secret="secret2",
            scopes=["scope1", "scope2"],
            key_id="iddddd"
        )

        # Должны быть равны, так как scopes одинаковые
        self.assertEqual(key1, key2)

    def test_comparison(self):
        """Тест: сравнение > и <"""
        # Создаем ключи с разными наборами scopes
        key_small = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="small",
            scopes={"yc.ai.languageModels.execute"},
            key_id="iddddd"
        )
        other_key = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="other",
            scopes={"yc.ai.languageModels.execute", "yc.monitoring.manage"},
            key_id="iddddd"
        )
        key_large = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="large",
            scopes={"yc.ai.languageModels.execute", "yc.ai.vision.execute", "yc.search-api.execute"},
            key_id="iddddd"
        )
        key_equal = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="equal",
            scopes={"yc.ai.languageModels.execute", "yc.ai.vision.execute", "yc.search-api.execute"},
            key_id="iddddd"
        )
        key_incomparable = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="incomparable",
            scopes={"yc.ai.imageGeneration.execute", "yc.monitoring.manage"},
            key_id="iddddd"
        )
        key_partial_overlap = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="partial",
            scopes={"yc.ai.languageModels.execute", "yc.ai.imageGeneration.execute"},
            key_id="iddddd"
        )

        # 1. Проверка: key_small < key_large
        self.assertLess(key_small, key_large)
        self.assertGreater(key_large, key_small)
        self.assertNotEqual(key_small, key_large)

        # 2. Проверка: key_small < other_key
        self.assertLess(key_small, other_key)
        self.assertGreater(other_key, key_small)
        self.assertNotEqual(key_small, other_key)

        # 3. Проверка: other_key и key_large несравнимы
        # other_key имеет: languageModels, monitoring
        # key_large имеет: languageModels, vision, search-api
        self.assertFalse(other_key < key_large)
        self.assertFalse(other_key > key_large)
        self.assertFalse(key_large < other_key)
        self.assertFalse(key_large > other_key)
        self.assertNotEqual(other_key, key_large)

        # 4. Проверка: key_large == key_equal
        self.assertEqual(key_large, key_equal)
        self.assertFalse(key_large < key_equal)
        self.assertFalse(key_large > key_equal)
        self.assertTrue(key_large <= key_equal)
        self.assertTrue(key_large >= key_equal)

        # 5. Проверка: key_small и key_incomparable несравнимы
        self.assertFalse(key_small < key_incomparable)
        self.assertFalse(key_small > key_incomparable)
        self.assertFalse(key_incomparable < key_small)
        self.assertFalse(key_incomparable > key_small)
        self.assertNotEqual(key_small, key_incomparable)

        # 6. Проверка: key_small < key_partial_overlap
        self.assertLess(key_small, key_partial_overlap)
        self.assertGreater(key_partial_overlap, key_small)
        self.assertNotEqual(key_small, key_partial_overlap)

        # 7. Проверка: сравнение с None и другими типами
        self.assertIsNotNone(key_small)
        self.assertNotEqual(key_small, None)
        self.assertNotEqual(key_small, "not_a_key")
        self.assertNotEqual(key_small, 123)

        # 8. Проверка: key_small <= other_key
        self.assertTrue(key_small <= other_key)
        self.assertTrue(key_small <= key_large)
        self.assertTrue(key_large <= key_equal)
        self.assertTrue(key_large >= key_equal)

        # 9. Проверка: key_large >= key_small
        self.assertTrue(key_large >= key_small)
        self.assertTrue(other_key >= key_small)

        # 10. Проверка: сравнение с самим собой
        self.assertFalse(key_small > key_small)
        self.assertTrue(key_small >= key_small)
        self.assertTrue(key_small <= key_small)
        self.assertEqual(key_small, key_small)

        # 11. Проверка: ключ со стандартными scopes
        key_with_defaults = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="defaults",
            scopes=set(),
            key_id="iddddd"
        )
        self.assertGreater(key_with_defaults, key_small)
        self.assertGreater(key_with_defaults, other_key)
        self.assertGreater(key_with_defaults, key_large)
        self.assertGreater(key_with_defaults, key_incomparable)
        self.assertGreater(key_with_defaults, key_partial_overlap)

        # 12. Проверка транзитивности
        key_tiny = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="tiny",
            scopes={"yc.ai.languageModels.execute", "yc.ai.vision.execute"},
            key_id="iddddd"
        )
        self.assertLess(key_small, key_tiny)  # languageModels ⊂ languageModels + vision
        self.assertLess(key_tiny, key_large)  # languageModels + vision ⊂ languageModels + vision + search-api
        self.assertLess(key_small, key_large)  # Транзитивность

        # 13. Проверка: сравнение с перемешанными scopes
        key_shuffled = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="shuffled",
            scopes={"yc.search-api.execute", "yc.ai.languageModels.execute", "yc.ai.vision.execute"},
            key_id="iddddd"
        )
        self.assertEqual(key_large, key_shuffled)

        # 14. Проверка: удаление дубликатов (автоматически в set)
        key_with_duplicates = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="duplicates",
            scopes=["yc.ai.languageModels.execute", "yc.ai.languageModels.execute", "yc.ai.vision.execute"],
            key_id="iddddd"
        )
        key_unique = ApiKey(
            created_at=self.created_at,
            expires_at=self.expires_at,
            secret="unique",
            scopes={"yc.ai.languageModels.execute", "yc.ai.vision.execute"},
            key_id="iddddd"
        )
        self.assertEqual(key_with_duplicates, key_unique)

        # 15. Дополнительная проверка: None в scopes недопустим
        with self.assertRaises(TypeError):
            ApiKey(
                created_at=self.created_at,
                expires_at=self.expires_at,
                secret="invalid",
                scopes=None,
                key_id="iddddd"
            )



if __name__ == '__main__':
    unittest.main()