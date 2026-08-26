from telemetry.main import Telemetry

log = Telemetry.log
get_metric_manager = Telemetry.get_metric_manager

__all__ = ["log", "get_metric_manager"]