# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import RecurringCost, RecurringCostSplit


class RecurringCostSplitInline(admin.TabularInline):
    model = RecurringCostSplit


@admin.register(RecurringCost)
class RecurringCostAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'to_account', 'disabled']
    inlines = [
        RecurringCostSplitInline,
    ]
