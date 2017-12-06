# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-12-06 23:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0003_auto_20171206_0145'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='smtp_host',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='settings',
            name='smtp_password',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='settings',
            name='smtp_port',
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='settings',
            name='smtp_use_ssl',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='settings',
            name='smtp_user',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
