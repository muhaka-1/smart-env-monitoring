import os
from dataclasses import dataclass
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    transport: str = "mqtt"  # "mqtt" | "http"
    interval: float = 5.0  # sekunder mellan meddelanden
    api_url: str = "http://localhost:8000/api/readings/"
    api_key: str = ""
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic_template: str = "beach/{sensor_id}/readings"
    # Chicago Park District - Beach Water Quality Automated Sensors (Socrata)
    dataset_url: str = (
        "https://data.cityofchicago.org/resource/qmqz-2xku.json"
        "?$limit=500&$order=measurement_timestamp DESC"
    )
    sample_path: Path = PKG_ROOT / "data" / "sample_readings.json"
    max_retries: int = 5
    retry_base_delay: float = 1.0
    request_timeout: float = 5.0

    @classmethod
    def from_env(cls) -> "Config":
        e = os.environ.get
        return cls(
            transport=e("SENSOR_TRANSPORT", cls.transport),
            interval=float(e("SENSOR_INTERVAL", cls.interval)),
            api_url=e("SENSOR_API_URL", cls.api_url),
            api_key=e("INGEST_API_KEY", cls.api_key),
            mqtt_host=e("MQTT_HOST", cls.mqtt_host),
            mqtt_port=int(e("MQTT_PORT", cls.mqtt_port)),
            dataset_url=e("SENSOR_DATASET_URL", cls.dataset_url),
            max_retries=int(e("SENSOR_MAX_RETRIES", cls.max_retries)),
        )
