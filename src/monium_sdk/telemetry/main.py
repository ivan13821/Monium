import asyncio
from datetime import datetime, timezone, timedelta

from monium_sdk.security import Tokens, ApiKey
from monium_sdk.telemetry.logs import LogManager
from monium_sdk.telemetry.metrics import MetricManager




class Telemetry:
    """
    Класс для работы с данными мониторинга:
        Отправляет данные в Monium
        Предоставляет Singleton для каждого класса мониторинга
        Осуществляет автоматическую ротацию API-ключей
    """

    log: LogManager
    metric: MetricManager
    
    _api_key: ApiKey = ApiKey(
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        secret="",
        key_id="",
        scopes=set()
    )

    project: str = None
    cluster: str = None
    service: str = None

    _is_init: bool = False

    @classmethod
    def init(cls, forced: bool = False):
        """Включает обновление классов с токенами и метриками"""

        if Telemetry._is_init and not forced:
            raise RuntimeError("You cannot enable background updates more than once.")

        asyncio.create_task(Telemetry._update_tokens())


    @classmethod
    async def _update_tokens(cls):

        while True:
            print("Проверяем токен...")
            if not Telemetry._api_key.is_current():
                key = await Tokens.get_api_key(["yc.monium.telemetry.write"])
                print("Обновляю классы...")
                if hasattr(cls, "log"):
                    print(f"last log: \n{cls.log.api_key}")
                cls.log = LogManager(
                    project=cls.project,
                    service=cls.service,
                    cluster=cls.cluster,
                    api_key=key
                )
                print(f'New log: \n{cls.log.api_key}')

                if hasattr(cls, "metric"):
                    print(f"last metric: \n{cls.metric.api_key}")
                cls.metric = MetricManager(
                    project=cls.project,
                    service=cls.service,
                    cluster=cls.cluster,
                    api_key=key
                )
                print(f'New metric: \n{cls.metric.api_key}')
                cls._api_key = key

            await asyncio.sleep(30)



