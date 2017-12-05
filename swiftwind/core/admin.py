# -*- coding: utf-8 -*-
from django.contrib import admin

import swiftwind.settings.models
from . import models


@admin.register(swiftwind.settings.models.Settings)
class SettingsAdmin(admin.ModelAdmin):
    pass
