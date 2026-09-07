from src.monium_sdk.security import Tokens, ApiKey
from src.monium_sdk.telemetry.logs import LogManager
from src.monium_sdk.telemetry.metrics import MetricManager




class Telemetry:
    """
    Класс для работы с данными мониторинга:
        Отправляет данные в Monium
        Предоставляет Singleton для каждого класса мониторинга
        Осуществляет автоматическую ротацию API-ключей
    """

    _log: LogManager
    _metric: MetricManager
    
    _api_key: ApiKey = None

    project: str = None
    cluster: str = None
    service: str = None

    @classmethod
    async def _check_configs(cls):
        """Синхронная инициализация"""

        if None in [cls.service, cls.project, cls.cluster]:
            raise ValueError("""
                Не заданы конфигурационные данные для Telemetry:
                Telemetry.project = "your project"
                Telemetry.cluster = "your cluster"
                Telemetry.service = "your service"
            """)

        key = await Tokens.get_api_key(["yc.monium.telemetry.write"])

        if cls._api_key is not None:
            if cls._api_key.secret == key.secret:
                return None

        cls._api_key = key

        cls._log = LogManager(
            project=cls.project,
            service=cls.service,
            cluster=cls.cluster,
            api_key=key
        )

        cls._metric = MetricManager(
            project=cls.project,
            service=cls.service,
            cluster=cls.cluster,
            api_key=key.secret if hasattr(key, 'secret') else key
        )

    @staticmethod
    async def get_log_manager():
        """"""
        await Telemetry._check_configs()
        return Telemetry._log

    @staticmethod
    async def get_metric_manager():
        """"""
        await Telemetry._check_configs()
        return Telemetry._metric