from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

from monium_sdk.security import ApiKey, IAMToken
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
    
    key: ApiKey | IAMToken = ApiKey(
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        secret="",
        scopes=set()
    )
    force_api_key: bool = False

    project: str = None
    cluster: str = None
    service: str = None

    _is_init: bool = False


    @classmethod
    def update_key(cls, key: ApiKey | IAMToken = None):

        if key is not None:
            cls.key = key

        if cls.log is not None:
            cls.log.force_flush()

        if cls.metric is not None:
            cls.metric.force_flush()

        cls.log = LogManager(
            project=cls.project,
            service=cls.service,
            cluster=cls.cluster,
            key=cls.key
        )

        cls.metric = MetricManager(
            project=cls.project,
            service=cls.service,
            cluster=cls.cluster,
            key=cls.key
        )


    @classmethod
    @contextmanager
    def logging_start(
            cls,
            key: ApiKey | IAMToken,
            service: str,
            project: str,
            cluster: str
    ):
        try:
            Telemetry.key = key

            Telemetry.service = service
            Telemetry.project = project
            Telemetry.cluster = cluster
            Telemetry.update_key()
            yield
        finally:
            Telemetry.log.force_flush()
            Telemetry.metric.force_flush()



