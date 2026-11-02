from typing import Dict

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

from monium_sdk.security import ApiKey
from monium_sdk.telemetry.metrics.models import CounterType, Tags, HistogramType


class MetricManager:
    """Класс для работы с метриками"""

    _meter = None
    _counters: Dict[str, Counter] = {}
    _histograms: Dict[str, Histogram] = {}
    provider: MeterProvider = None

    api_key: ApiKey = None

    project: str = None
    cluster: str = None
    service: str = None



    def __init__(self, project: str, key: ApiKey, cluster: str, service: str):

        self.project = project
        self.cluster = cluster
        self.service = service
        self.key = key

        resource = Resource.create({
            "service.name": service,
            "cluster": cluster,
            "service.version": "1.0.0",
            "project": project
        })

        exporter = OTLPMetricExporter(
            endpoint="https://ingest.monium.yandex.cloud/otlp/v1/metrics",
            headers={
                "Authorization": key.metadata,
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

        if self.provider is not None:
            self.provider.shutdown()
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        self.provider = provider

        meter = provider.get_meter(service, "1.0.0")
        self._meter = meter



    def force_flush(self):
        self.provider.force_flush()



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
