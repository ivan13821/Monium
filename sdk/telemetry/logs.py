import asyncio
import sys
from enum import Enum

from opentelemetry import _logs
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
import logging

from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes



class LogManager:
    """Класс для работы с логами и интеграцией с Monium"""
    __MONIUM_LOGS_ENDPOINT = "https://ingest.monium.yandex.cloud/otlp/v1/logs"
    logger_provider = None

    def __init__(self, project: str, api_key: str, cluster: str, service: str):

        log_exporter = OTLPLogExporter(
            endpoint=self.__MONIUM_LOGS_ENDPOINT,
            headers={
                "Authorization": f"Api-Key {api_key}",
                "x-monium-project": project,
                "x-monium-cluster": cluster,
                "x-monium-service": service,
            },
            timeout=30,
        )

        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: service,
            "project": project
        })

        # Настройка провайдера логов
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        _logs.set_logger_provider(logger_provider)

        self.logger_provider = logger_provider


    def get_logger(self, name: str, level: int, has_console_handler: bool = False):
        """Получение логгера, который будет отправлять данные в Monium"""

        logger = logging.getLogger(name)
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

        return logger