# -*- coding: utf-8 -*-
from django.contrib import admin
from djcelery.models import TaskMeta


@admin.register(TaskMeta)
class TaskMetaAdmin(admin.ModelAdmin):
    readonly_fields = ('traceback', 'result',)
