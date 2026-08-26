from datetime import datetime, timedelta
from typing import Dict

from security import Tokens
from telemetry.logs import LogManager
from telemetry.metrics import MetricManager
from config import Config
import logging




class Telemetry:
    """
    Класс для работы с данными мониторинга:
        Отправляет данные в Monium
        Предоставляет Singleton для каждого класса мониторинга
        Осуществляет автоматическую ротацию API-ключей
    """

    _log_manager: LogManager = None
    _log_manager_created_at: datetime = datetime.now() # Не None, чтобы не было проблем при вычеслениях
    _loggers: Dict[str, logging.Logger] = {}

    _metric_manager: MetricManager = None
    _metric_manager_created_at: datetime = datetime.now()



    @staticmethod
    async def log(name: str, level: int, message: str, handler_level: int = logging.INFO, has_console_handler: bool = True) -> None:
        """
        Функция для записи логов

        Args:
            name: имя модуля откуда пришел лог
            level: уровень логирования. Например logging.INFO или 20
            message: Сообщение, которое нужно передать с помощью логгера
            handler_level: Уровень логирования для хендлера
            has_console_handler: Нужно писать логи в терминал или нет
        """

        log_manager = await Telemetry._get_log_manager()

        key = f"{name}{handler_level}{has_console_handler}"
        if key in Telemetry._loggers.keys():
            logger = Telemetry._loggers.get(key)
        else:
            logger = log_manager.get_logger(name, level=handler_level, has_console_handler=has_console_handler)
            Telemetry._loggers[key] = logger

        logger.log(level, message)




    @staticmethod
    async def _get_log_manager():
        """Создает логгер"""
        if Telemetry._log_manager is None or Telemetry._log_manager_created_at + timedelta(hours=1) < datetime.now():
            Telemetry._log_manager = LogManager(
                project=f"folder__{Config.folder_id}",
                api_key=await Tokens.get_api_key([
                    "yc.monium.telemetry.write",
                    "yc.monium.logs.write",
                    "yc.monium.metrics.write",
                    "yc.monium.traces.write"
                ]),
                cluster=Config.cluster,
                service=Config.service
            )
            Telemetry._loggers = {}
        return Telemetry._log_manager



    @staticmethod
    async def get_metric_manager():
        if Telemetry._metric_manager is None or Telemetry._metric_manager_created_at + timedelta(hours=1) < datetime.now():
            Telemetry._metric_manager = MetricManager(
                project=f"folder__{Config.folder_id}",
                api_key=await Tokens.get_api_key([
                    "yc.monium.telemetry.write",
                    "yc.monium.logs.write",
                    "yc.monium.metrics.write",
                    "yc.monium.traces.write"
                ]),
                cluster=Config.cluster,
                service=Config.service
            )

        return Telemetry._metric_manager