# Generated by Django 5.0.7 on 2024-08-27 12:06

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('alertrix', '0005_widget_activation_secret'),
        ('matrixappservice', '0006_alter_event_origin_server_ts'),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('matrixappservice.room',),
        ),
    ]
