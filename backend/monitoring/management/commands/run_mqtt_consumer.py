from django.conf import settings
from django.core.management.base import BaseCommand

from monitoring.mqtt_consumer import MqttIngestor


class Command(BaseCommand):
    help = "Startar MQTT-konsumenten som sparar sensordata i databasen."

    def handle(self, *args, **options):
        ingestor = MqttIngestor(settings.MQTT_HOST, settings.MQTT_PORT, settings.MQTT_SUBSCRIBE_TOPIC)
        try:
            ingestor.run()
        except KeyboardInterrupt:
            self.stdout.write("Stoppad.")
