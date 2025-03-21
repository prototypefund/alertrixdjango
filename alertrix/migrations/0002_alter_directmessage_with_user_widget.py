# Generated by Django 5.0.6 on 2024-06-25 11:33

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alertrix', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='directmessage',
            name='with_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='Widget',
            fields=[
                ('id', models.TextField(primary_key=True, serialize=False)),
                ('user_id', models.TextField()),
                ('created_timestamp', models.DateTimeField(auto_now=True)),
                ('first_use_timestamp', models.DateTimeField(blank=True, default=None, null=True)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='alertrix.matrixroom')),
            ],
        ),
    ]
