from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from i18n import Language

ServiceKey = Literal["annotations", "vehicle_registration", "certificate_pickup"]

SERVICE_ORDER: tuple[ServiceKey, ...] = (
    "annotations",
    "vehicle_registration",
    "certificate_pickup",
)

SERVICE_BUTTON_I18N: dict[ServiceKey, str] = {
    "annotations": "btn_service_annotations",
    "vehicle_registration": "btn_service_vehicle",
    "certificate_pickup": "btn_service_certificate",
}

BRANCH_ID = "82431f5aac5af7c75a3be70c3de3d449396d10d39a51f95899011243f7a23097"
BRANCH_NAME = "Gronowa 22a, Poznań"


@dataclass(frozen=True)
class ServiceDefinition:
    key: ServiceKey
    service_id: str
    duration_minutes: int
    additional_duration_minutes: int
    max_cases: int
    names: dict[Language, str]


SERVICES: dict[ServiceKey, ServiceDefinition] = {
    "annotations": ServiceDefinition(
        key="annotations",
        service_id="f1ac89933015e86541b2c33bae1a8525e6c9efef0ebb185a2d71295a323ec78f",
        duration_minutes=15,
        additional_duration_minutes=15,
        max_cases=3,
        names={
            "en": "Annotations in registration certificates",
            "uk": "Анотації в реєстраційних документах",
        },
    ),
    "vehicle_registration": ServiceDefinition(
        key="vehicle_registration",
        service_id="9b49308b28e0581530e3f65bbb67f164dbbde78895cd55a6902930900faa6570",
        duration_minutes=15,
        additional_duration_minutes=15,
        max_cases=3,
        names={
            "en": "Vehicle registration",
            "uk": "Реєстрація транспортного засобу",
        },
    ),
    "certificate_pickup": ServiceDefinition(
        key="certificate_pickup",
        service_id="d533101758ced4a7d791ebd125459c7e9a1db503d84458b2f522e5bcd9c8f2d3",
        duration_minutes=15,
        additional_duration_minutes=15,
        max_cases=3,
        names={
            "en": "Permanent registration certificate pickup",
            "uk": "Отримання постійного реєстраційного документа",
        },
    ),
}


def get_service(key: str) -> ServiceDefinition:
    if key not in SERVICES:
        return SERVICES["annotations"]
    return SERVICES[key]  # type: ignore[index]


def get_service_by_id(service_id: str) -> ServiceDefinition | None:
    for service in SERVICES.values():
        if service.service_id == service_id:
            return service
    return None


def service_label(service: ServiceDefinition, lang: Language) -> str:
    return service.names.get(lang, service.names["en"])


def slot_duration_for_cases(service: ServiceDefinition, num_cases: int) -> int:
    return service.duration_minutes * num_cases
