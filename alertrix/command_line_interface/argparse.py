import argparse as _argparse
import os as _os
from gettext import gettext as _

import sys as _sys


class _HelpAction(_argparse._HelpAction):

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()


class Parser(
    _argparse.ArgumentParser,
):

    def __init__(
            self,
            prog=None,
            usage=None,
            description=None,
            epilog=None,
            parents=[],
            formatter_class=_argparse.HelpFormatter,
            prefix_chars='-',
            fromfile_prefix_chars=None,
            argument_default=None,
            conflict_handler='error',
            add_help=True,
            allow_abbrev=True,
            exit_on_error=False,
    ):
        super(_argparse.ArgumentParser, self).__init__(
            description=description,
            prefix_chars=prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
        )

        # default setting for prog
        if prog is None:
            prog = _os.path.basename(_sys.argv[0])

        self.prog = prog
        self.usage = usage
        self.epilog = epilog
        self.formatter_class = formatter_class
        self.fromfile_prefix_chars = fromfile_prefix_chars
        self.add_help = add_help
        self.allow_abbrev = allow_abbrev
        self.exit_on_error = exit_on_error

        add_group = self.add_argument_group
        self._positionals = add_group(_('positional arguments'))
        self._optionals = add_group(_('options'))
        self._subparsers = None

        # register types
        def identity(string):
            return string
        self.register('type', None, identity)

        # add help argument if necessary
        # (using explicit default to override global argument_default)
        default_prefix = '-' if '-' in prefix_chars else prefix_chars[0]
        if self.add_help:
            self.add_argument(
                default_prefix+'h', default_prefix*2+'help',
                action='help', default=_argparse.SUPPRESS,
                help=_('show this help message and exit'))

        # add parent arguments and defaults
        for parent in parents:
            self._add_container_actions(parent)
            try:
                defaults = parent._defaults
            except AttributeError:
                pass
            else:
                self._defaults.update(defaults)
