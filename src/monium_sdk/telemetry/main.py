import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from monium_sdk.security import ApiKey, IAMToken, ApiKeysManager, ServiceAccountConfigData, IAMTokenManager
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
    async def shutdown(cls):
        """Удаляет API-ключ и подчищает остальные зависимости"""
        await ApiKeysManager.delete_all_keys_async()


    @classmethod
    async def _update_tokens(cls):

        while True:
            if not Telemetry._api_key.is_current():
                key = await ApiKeysManager.get_api_key(["yc.monium.telemetry.write"])

                cls.log = LogManager(
                    project=cls.project,
                    service=cls.service,
                    cluster=cls.cluster,
                    api_key=key
                )

                cls.metric = MetricManager(
                    project=cls.project,
                    service=cls.service,
                    cluster=cls.cluster,
                    api_key=key
                )
                cls._api_key = key
            await asyncio.sleep(30)

    @classmethod
    @asynccontextmanager
    async def logging_start(
            cls,
            config: ServiceAccountConfigData,
            service: str,
            project: str,
            cluster: str
    ):
        try:
            IAMTokenManager.service_account_config = config

            Telemetry.service = service
            Telemetry.project = project
            Telemetry.cluster = cluster
            token = await IAMTokenManager.get_iam_token()
            Telemetry.init()
            await asyncio.sleep(3)
            yield
        finally:
            Telemetry.log.force_flush()
            Telemetry.metric.force_flush()
            await Telemetry.shutdown()



