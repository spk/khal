# vim: set ts=4 sw=4 expandtab sts=4 fileencoding=utf-8:
# Copyright (c) 2013-2014 Christian Geier et al.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
"""khal

Usage:
  khal calendar [-vc CONF] [ (-a CAL ... | -d CAL ... ) ] [--days=N| --events=N] [DATE ...]
  khal agenda   [-vc CONF] [ (-a CAL ... | -d CAL ... ) ] [--days=N| --events=N] [DATE ...]
  khal interactive [-vc CONF] [ (-a CAL ... | -d CAL ... ) ]
  khal new [-vc CONF] [-a cal] DESCRIPTION...
  khal printcalendars [-vc CONF]
  khal [-vc CONF] [ (-a CAL ... | -d CAL ... ) ] [DATE ...]
  khal (-h | --help)
  khal --version


Options:
  -h --help    Show this help.
  --version    Print version information.
  -a CAL       Use this calendars (can be used several times)
  -d CAL       Do not use this calendar (can be used several times)
  -v           Be extra verbose.
  -c CONF      Use this config file.

"""
import logging
import signal
import StringIO
import sys

try:
    from setproctitle import setproctitle
except ImportError:
    setproctitle = lambda x: None

from docopt import docopt

from khal import controllers
from khal import khalendar
from khal import __version__, __productname__
from khal.log import logger
from khal.settings import get_config


def capture_user_interruption():
    """
    Tries to hide to the user the ugly python backtraces generated by
    pressing Ctrl-C.
    """
    signal.signal(signal.SIGINT, lambda x, y: sys.exit(0))


def main_khal():
    capture_user_interruption()

    # setting the process title so it looks nicer in ps
    # shows up as 'khal' under linux and as 'python: khal (python2.7)'
    # under FreeBSD, which is still nicer than the default
    setproctitle('khal')

    arguments = docopt(__doc__, version=__productname__ + ' ' + __version__,
                       options_first=False)

    if arguments['-v']:
        logger.setLevel(logging.DEBUG)
    logger.debug('this is {} version {}'.format(__productname__, __version__))

    conf = get_config(arguments['-c'])

    out = StringIO.StringIO()
    conf.write(out)
    logger.debug('using config:')
    logger.debug(out.getvalue())

    collection = khalendar.CalendarCollection()

    for name, cal in conf['calendars'].items():
        if (name in arguments['-a'] and arguments['-d'] == list()) or \
           (name not in arguments['-d'] and arguments['-a'] == list()):
            collection.append(khalendar.Calendar(
                name=name,
                dbpath=conf['sqlite']['path'],
                path=cal['path'],
                readonly=cal['readonly'],
                color=cal['color'],
                unicode_symbols=conf['locale']['unicode_symbols'],
                local_tz=conf['locale']['local_timezone'],
                default_tz=conf['locale']['default_timezone']
            ))
    collection._default_calendar_name = conf['default']['default_calendar']
    commands = ['agenda', 'calendar', 'new', 'interactive', 'printcalendars']

    if not any([arguments[com] for com in commands]):
        arguments = docopt(__doc__,
                           version=__productname__ + ' ' + __version__,
                           argv=[conf['default']['default_command']] + sys.argv[1:])

    days = int(arguments['--days']) if arguments['--days'] else None
    events = int(arguments['--events']) if arguments['--events'] else None

    if arguments['calendar']:
        controllers.Calendar(collection,
                             date=arguments['DATE'],
                             firstweekday=conf['locale']['firstweekday'],
                             encoding=conf['locale']['encoding'],
                             dateformat=conf['locale']['dateformat'],
                             longdateformat=conf['locale']['longdateformat'],
                             )
    elif arguments['agenda']:
        controllers.Agenda(collection,
                           date=arguments['DATE'],
                           firstweekday=conf['locale']['firstweekday'],
                           encoding=conf['locale']['encoding'],
                           dateformat=conf['locale']['dateformat'],
                           longdateformat=conf['locale']['longdateformat'],
                           )
    elif arguments['new']:
        controllers.NewFromString(collection, conf, arguments['DESCRIPTION'])
    elif arguments['interactive']:
        controllers.Interactive(collection, conf)
    elif arguments['printcalendars']:
        print('\n'.join(collection.names))


def main_ikhal():
    sys.argv = [sys.argv[0], 'interactive'] + sys.argv[1:]
    main_khal()
