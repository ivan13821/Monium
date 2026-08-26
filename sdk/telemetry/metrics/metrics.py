import logging
from typing import Dict

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from telemetry.metrics.models import CounterType, Tags, HistogramType
import http.client as http_client

http_client.HTTPConnection.debuglevel = 1

# Настраиваем логирование для urllib3
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)
logging.getLogger("opentelemetry").setLevel(logging.DEBUG)


class MetricManager:
    """Класс для работы с метриками"""

    _meter = None
    _counters: Dict[str, Counter] = {}
    _histograms: Dict[str, Histogram] = {}



    def __init__(self, project: str, api_key: str, cluster: str, service: str):
        resource = Resource.create({
            "service.name": service,
            "cluster": cluster,
            "service.version": "1.0.0",
            "project": project
        })

        exporter = OTLPMetricExporter(
            endpoint="https://ingest.monium.yandex.cloud/otlp/v1/metrics",
            headers={
                "Authorization": f"Api-Key {api_key}",
                "x-monium-project": project,
                "x-monium-cluster": cluster,
                "x-monium-service": service,
            },
            timeout=30,
        )


        reader = PeriodicExportingMetricReader(
            exporter=exporter,
            export_interval_millis=10000
        )

        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)

        meter = metrics.get_meter(service, "1.0.0")
        self._meter = meter




    def add_to_counter(self, name: CounterType = CounterType.REQUESTS, tags: Tags = Tags(), count: int = 1):
        """Добаление значений к счетчику"""

        if name.value not in self._counters.keys():
            counter = self._meter.create_counter(
                name=name.value,
                unit=name.unit,
                description=name.description
            )
            self._counters[name.value] = counter

        counter = self._counters.get(name.value)
        counter.add(count, tags.to_dict())


    def add_to_histogram(self, duration: float, name: HistogramType = HistogramType.DURATION, tags: Tags = Tags()):
        """Добавление данных в гистограмму"""

        if name.value not in self._histograms.keys():
            histogram = self._meter.create_histogram(
                name=name.value,
                unit=name.unit,
                description=name.description
            )
            self._histograms[name.value] = histogram

        histogram = self._histograms.get(name.value)
        histogram.record(duration, tags.to_dict())
