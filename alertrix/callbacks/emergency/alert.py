import argparse
from importlib import import_module
import nio
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.constants import DEFAULT_TAGS as DEFAULT_MESSAGE_TAGS
from django.contrib.messages.storage import default_storage
from django.http import HttpRequest
