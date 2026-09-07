import inspect
import os
import sys
from typing import Dict, Any

from opentelemetry import _logs
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
import logging

from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

from src.monium_sdk.security import ApiKey


class LogManager:
    """Класс для работы с логами и интеграцией с Monium"""
    __MONIUM_LOGS_ENDPOINT = "https://ingest.monium.yandex.cloud/otlp/v1/logs"
    logger_provider = None
    loggers: Dict[str, Any] = {}

    api_key: ApiKey = None

    project: str = None
    cluster: str = None
    service: str = None
    level: int = None


    def __init__(
            self,
            project: str,
            cluster: str,
            service: str,
            api_key: ApiKey,
            level: int=logging.NOTSET
    ):
        self.project = project
        self.cluster = cluster
        self.service = service
        self.level = level
        self.api_key = api_key
        self.init_provider()



    def init_provider(self) -> None:

        log_exporter = OTLPLogExporter(
            endpoint=self.__MONIUM_LOGS_ENDPOINT,
            headers={
                "Authorization": f"Api-Key {self.api_key.secret}",
                "x-monium-project": self.project,
                "x-monium-cluster": self.cluster,
                "x-monium-service": self.service,
            },
            timeout=30,
        )

        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: self.service,
            "project": self.project
        })

        # Настройка провайдера логов
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        _logs.set_logger_provider(logger_provider)

        self.logger_provider = logger_provider



    def get_logger(self, name: str, level: int, has_console_handler: bool = False):
        """Получение логгера, который будет отправлять данные в Monium"""

        key = f"{name}|{level}|{has_console_handler}"

        if key in self.loggers.keys():
            return self.loggers.get(key)


        logger = logging.getLogger(key)
        logger.setLevel(level)

        handler = LoggingHandler(level=level, logger_provider=self.logger_provider)
        logger.addHandler(handler)

        # Хандлер для консоли
        if has_console_handler:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)

            logger.addHandler(console_handler)

        self.loggers[key] = logger

        return logger



    def log(self, name: str, level: int, msg: str, *args, **kwargs):
        try:
            logger = self.get_logger(name, level)
            logger.log(
                level=level,
                msg=msg,
                *args,
                **kwargs
            )

        except Exception as e:
            print(f"Ошибка отправки лога в Monium: {e}")


    def info(self, msg: str, *args, **kwargs):
        frame = inspect.currentframe().f_back
        caller_file = frame.f_code.co_filename
        name = os.path.abspath(caller_file)
        self.log(name, logging.INFO, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        frame = inspect.currentframe().f_back
        caller_file = frame.f_code.co_filename
        name = os.path.abspath(caller_file)
        self.log(name, logging.DEBUG, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        frame = inspect.currentframe().f_back
        caller_file = frame.f_code.co_filename
        name = os.path.abspath(caller_file)
        self.log(name, logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        frame = inspect.currentframe().f_back
        caller_file = frame.f_code.co_filename
        name = os.path.abspath(caller_file)
        self.log(name, logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        frame = inspect.currentframe().f_back
        caller_file = frame.f_code.co_filename
        name = os.path.abspath(caller_file)
        self.log(name, logging.CRITICAL, msg, *args, **kwargs)
