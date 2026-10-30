from django.contrib import admin

from .models import Reading


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("sensor_id", "metric", "timestamp", "value", "unit", "quality", "status")
    list_filter = ("metric", "status", "quality", "sensor_id")
    date_hierarchy = "timestamp"
