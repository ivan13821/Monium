import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from monium_sdk.security import ApiKey
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
    
    api_key: ApiKey = ApiKey(
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        secret="",
        key_id="",
        scopes=set()
    )
    force_api_key: bool = False

    project: str = None
    cluster: str = None
    service: str = None

    _is_init: bool = False

    # @classmethod
    # def init(cls, forced: bool = False):
    #     """Включает обновление классов с токенами и метриками"""
    #
    #     if Telemetry._is_init and not forced:
    #         raise RuntimeError("You cannot enable background updates more than once.")
    #
    #     asyncio.create_task(Telemetry._update_tokens())


    # @classmethod
    # async def shutdown(cls):
    #     """Удаляет API-ключ и подчищает остальные зависимости"""
    #     await ApiKeysManager.delete_all_keys_async()


    @classmethod
    def _update_tokens(cls):

        # while True:
            # if not Telemetry.api_key.is_current():
            #     key = await ApiKeysManager.get_api_key(["yc.monium.telemetry.write"])

        cls.log = LogManager(
            project=cls.project,
            service=cls.service,
            cluster=cls.cluster,
            api_key=cls.api_key
        )

        cls.metric = MetricManager(
            project=cls.project,
            service=cls.service,
            cluster=cls.cluster,
            api_key=cls.api_key
        )
            #
            # await asyncio.sleep(30)

    @classmethod
    @asynccontextmanager
    async def logging_start(
            cls,
            api_key: ApiKey,
            service: str,
            project: str,
            cluster: str
    ):
        try:
            Telemetry.api_key = api_key

            Telemetry.service = service
            Telemetry.project = project
            Telemetry.cluster = cluster
            Telemetry._update_tokens()
            await asyncio.sleep(3)
            yield
        finally:
            Telemetry.log.force_flush()
            Telemetry.metric.force_flush()
            # await Telemetry.shutdown()



