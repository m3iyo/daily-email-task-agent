from dataclasses import dataclass

from services.safety import MonitoringService
from services.scheduler import EmailProcessingScheduler


@dataclass
class AppServices:
    scheduler: EmailProcessingScheduler
    monitoring: MonitoringService


def build_app_services() -> AppServices:
    return AppServices(
        scheduler=EmailProcessingScheduler(),
        monitoring=MonitoringService(),
    )
