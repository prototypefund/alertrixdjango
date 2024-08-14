import pkgutil
import re
import unittest

from django.core.management.base import BaseCommand

import alertrix


class Command(BaseCommand):
    help = "Test the alertrix app on a live system (make sure to create an isolated environment)"

    def handle(self, *args, **options):
        package = alertrix
        prefix = package.__name__ + "."
        test_modules = []
        for importer, modname, ispkg in pkgutil.iter_modules(package.__path__, prefix):
            short_modname = modname.removeprefix(prefix)
            if not re.match('test*', short_modname):
                continue
            test_modules.append(short_modname)
            __import__(modname, fromlist=[])
        unittest.main(
            module=alertrix,
            argv=['unittest'] + test_modules,
            exit=False,
        )
