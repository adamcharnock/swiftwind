# -*- coding: utf-8 -*-
from django.contrib import admin

from . import models


@admin.register(models.Settings)
class SettingsAdmin(admin.ModelAdmin):
    pass
