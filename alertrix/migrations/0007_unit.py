# Generated by Django 5.0.7 on 2024-08-28 13:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('alertrix', '0006_company'),
        ('matrixappservice', '0007_alter_user_user_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='Unit',
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
