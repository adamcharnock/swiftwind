from django.contrib import admin

from swiftwind.transactions.models import TransactionImportColumn
from .models import TransactionImport


class TransactionImportColumnInline(admin.TabularInline):
    model = TransactionImportColumn


@admin.register(TransactionImport)
class TaskMetaAdmin(admin.ModelAdmin):
    list_display = ['id', 'uuid', 'state', 'timestamp', 'has_headings']
    inlines = [
        TransactionImportColumnInline,
    ]
