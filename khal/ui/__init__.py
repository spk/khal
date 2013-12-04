#!/usr/bin/env python2
# coding: utf-8
# vim: set ts=4 sw=4 expandtab sts=4:
# Copyright (c) 2011-2013 Christian Geier & contributors
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

import calendar
from datetime import date
from datetime import time
from datetime import datetime

import urwid

from .. import aux, backend, model

from base import Pane, Window


class DateConversionError(Exception):
    pass


class Date(urwid.Text):
    """used in the main calendar for dates"""

    def __init__(self, date, view):
        self.date = date
        self.view = view
        if date.today == date:
            urwid.AttrMap(super(Date, self).__init__(str(date.day).rjust(2)),
                          None,
                          'reveal focus')
        else:
            super(Date, self).__init__(str(date.day).rjust(2))

    @classmethod
    def selectable(cls):
        return True

    def keypress(self, _, key):
        if key in ['n']:
            self.view.new_event(self.date)
            return 'tab'  # TODO return next
        else:
            return key


def week_list(count=3):
    month = date.today().month
    year = date.today().year
    cal = list()
    for _ in range(count):
        for week in calendar.Calendar(0).monthdatescalendar(year, month):
            if week not in cal:
                cal.append(week)
        month = month + 1
        if month > 12:
            month = 1
            year = year + 1
    return cal


class DateColumns(urwid.Columns):
    """container for one week worth of dates

    focus can only move away by pressing 'TAB',
    calls 'call' on every focus change
    """
    def __init__(self, widget_list, view=None, **kwargs):
        self.view = view
        super(DateColumns, self).__init__(widget_list, **kwargs)

    def _set_focus_position(self, position):
        """calls view.show_date before calling super()._set_focus_position"""

        super(DateColumns, self)._set_focus_position(position)

        # since first Column is month name, focus should only be 0 during
        # construction
        if not self.contents.focus == 0:
            self.view.show_date(self.contents[position][0].original_widget.date)

    focus_position = property(urwid.Columns._get_focus_position,
                              _set_focus_position, doc="""
index of child widget in focus. Raises IndexError if read when
Columns is empty, or when set to an invalid index.
""")

    def keypress(self, size, key):
        """only leave calendar area on pressing 'TAB'"""

        old_pos = self.focus_position
        key = super(DateColumns, self).keypress(size, key)
        if key in ['up', 'down']:  # don't know why this is needed...
            return key
        elif key in ['tab', 'enter']:
            return 'right'
        elif old_pos == 7 and key == 'right':
            self.focus_position = 1
            return 'down'
        elif old_pos == 1 and key == 'left':
            self.focus_position = 7
            return 'up'
        elif key not in ['right']:
            return key


def construct_week(week, view):
    """
    :param week: list of datetime.date objects
    :param view: passed along for back calling
    :type view: a View (ClassicView) object
    returns urwid.Columns
    """
    if 1 in [day.day for day in week]:
        month_name = calendar.month_abbr[week[-1].month].ljust(4)
    else:
        month_name = '    '

    this_week = [(4, urwid.Text(month_name))]
    today = None
    for number, day in enumerate(week):
        if day == date.today():
            this_week.append((2, urwid.AttrMap(Date(day, view),
                                               'today', 'today_focus')))
            today = number + 1
        else:
            this_week.append((2, urwid.AttrMap(Date(day, view),
                                               None, 'reveal focus')))
    week = DateColumns(this_week, view=view, dividechars=1,
                       focus_column=today)
    return week, bool(today)


def calendar_walker(view):
    """hopefully this will soon become a real "walker",
    loading new weeks as nedded"""
    lines = list()
    daynames = 'Mo Tu We Th Fr Sa Su'.split(' ')
    daynames = urwid.Columns([(4, urwid.Text('    '))] + [(2, urwid.Text(name)) for name in daynames],
                             dividechars=1)
    lines = [daynames]
    focus_item = None
    for number, week in enumerate(week_list()):
        week, contains_today = construct_week(week, view)
        if contains_today:
            focus_item = number + 1
        lines.append(week)

    weeks = urwid.Pile(lines, focus_item=focus_item)
    return weeks


class Event(urwid.Text):
    def __init__(self, event, this_date=None, conf=None, dbtool=None,
                 eventcolumn=None):
        """
        representation of an event in EventList

        :param event: the encapsulated event
        :tpye event: khal.model.event
        """

        self.event = event
        self.this_date = this_date
        self.dbtool = dbtool
        self.conf = conf
        self.eventcolumn = eventcolumn
        self.view = False
        super(Event, self).__init__(self.event.compact(self.this_date))

    @classmethod
    def selectable(cls):
        return True

    def toggle_delete(self):
        if self.event.readonly is False:
            if self.event.status == backend.OK:
                toggle = backend.DELETED
            elif self.event.status == backend.DELETED:
                toggle = backend.OK
            elif self.event.status == backend.NEW:
                toggle = backend.NEWDELETE
            elif self.event.status == backend.NEWDELETE:
                toggle = backend.NEW
            self.event.status = toggle
            self.set_text(self.event.compact(self.this_date))
            self.dbtool.set_status(self.event.href, toggle, self.event.account)
        else:
            self.set_text('RO' + self.event.compact(self.this_date))

    def keypress(self, _, key):
        if key == 'enter' and self.view is False:
            self.view = True
            self.eventcolumn.view(self.event)
        elif (key == 'enter' and self.view is True) or key == 'e':
            self.eventcolumn.edit(self.event)
        elif key == 'd':
            self.toggle_delete()
        elif key in ['left', 'up', 'down'] and self.view:
            self.eventcolumn.destroy()
        return key


class EventList(urwid.WidgetWrap):
    """list of events"""
    def __init__(self, conf=None, dbtool=None, eventcolumn=None):
        self.conf = conf
        self.dbtool = dbtool
        self.eventcolumn = eventcolumn
        pile = urwid.Pile([])
        urwid.WidgetWrap.__init__(self, pile)
        self.update()

    def update(self, this_date=date.today()):

        start = datetime.combine(this_date, time.min)
        end = datetime.combine(this_date, time.max)

        date_text = urwid.Text(
            this_date.strftime(self.conf.default.longdateformat))
        event_column = list()
        all_day_events = list()
        events = list()
        for account in self.conf.sync.accounts:
            color = self.conf.accounts[account]['color']
            readonly = self.conf.accounts[account]['readonly']
            all_day_events += self.dbtool.get_allday_range(
                this_date,
                account_name=account,
                color=color,
                readonly=readonly)
            events += self.dbtool.get_time_range(start, end, account,
                                                 color=color,
                                                 readonly=readonly)

        for event in all_day_events:
            event_column.append(
                urwid.AttrMap(Event(event,
                                    conf=self.conf,
                                    dbtool=self.dbtool,
                                    this_date=this_date,
                                    eventcolumn=self.eventcolumn),
                              event.color, 'reveal focus'))
        events.sort(key=lambda e: e.start)
        for event in events:
            event_column.append(
                urwid.AttrMap(Event(event,
                                    conf=self.conf,
                                    dbtool=self.dbtool,
                                    this_date=this_date,
                                    eventcolumn=self.eventcolumn),
                              event.color, 'reveal focus'))
        event_list = [urwid.AttrMap(event, None, 'reveal focus') for event in event_column]
        pile = urwid.Pile([date_text] + event_list)
        self._w = pile


class EventColumn(urwid.WidgetWrap):
    """contains the eventlist as well as the event viewer/editor"""
    def __init__(self, conf=None, dbtool=None):
        self.conf = conf
        self.dbtool = dbtool
        self.divider = urwid.Divider('-')
        self.editor = False

    def update(self, date):
        """create an EventList populated with Events for `date` and display it
        """

        # TODO make this switch from pile to columns depending on terminal size
        events = EventList(conf=self.conf, dbtool=self.dbtool,
                           eventcolumn=self)
        events.update(date)
        self.container = urwid.Pile([events])
        self._w = self.container

    def view(self, event):
        """
        show an event's details

        :param event: event to view
        :type event: khal.model.Event
        """
        self.destroy()
        self.container.contents.append((self.divider,
                                        self.container.options()))
        self.container.contents.append(
            (EventDisplay(self.conf, self.dbtool, event),
             self.container.options()))

    def edit(self, event):
        """create an EventEditor and display it

        :param event: event to edit
        :type event: khal.model.Event
        """
        self.destroy()
        self.editor = True
        self.container.contents.append((self.divider,
                                        self.container.options()))
        self.container.contents.append(
            (EventEditor(self.conf, self.dbtool, event, cancel=self.destroy),
             self.container.options()))
        self.container.set_focus(2)

    def destroy(self, _=None):
        """
        if an EventViewer or EventEditor is displayed, remove it
        """
        self.editor = False
        if (len(self.container.contents) > 2 and
                isinstance(self.container.contents[2][0], EventViewer)):
            self.container.contents.pop()
            self.container.contents.pop()

    def new(self, date):
        """create a new event on date

        :param date: default date for new event
        :type date: datetime.date
        """
        event = aux.new_event(dtstart=date,
                              timezone=self.conf.default.default_timezone)
        event = model.Event(ical=event.to_ical(), status=backend.NEW,
                            account=list(self.conf.sync.accounts)[-1])
        self.edit(event)



    @classmethod
    def selectable(cls):
        return True


class RecursionEditor(urwid.WidgetWrap):
    def __init__(self, rrule):
        self.recursive = False if rrule is None else True
        self.checkRecursion = urwid.CheckBox('repeat', state=self.recursive,
                                             on_state_change=self.toggle)
        self.columns = urwid.Columns([self.checkRecursion])
        urwid.WidgetWrap.__init__(self, self.columns)

    def toggle(self, checkbox, state):
        if len(self.columns.contents) < 2:
            text = 'Editing repitition rules is not supported yet'
            self.columns.contents.append((urwid.Text(text),
                                          self.columns.options()))


class StartEndEditor(urwid.WidgetWrap):
    """
    editing start and nd times of the event

    we cannot change timezones ATM  # TODO
    pop up on strings not matching timeformat # TODO
    """

    def __init__(self, start, end, conf):
        self.conf = conf
        self.startdt = start
        self.enddt = end
        # TODO cleanup
        self.startdate = self.startdt.strftime(self.conf.default.longdateformat)
        self.starttime = self.startdt.strftime(self.conf.default.timeformat)
        self.enddate = self.enddt.strftime(self.conf.default.longdateformat)
        self.endtime = self.enddt.strftime(self.conf.default.timeformat)
        self.startdate_bg = 'edit'
        self.starttime_bg = 'edit'
        self.enddate_bg = 'edit'
        self.endtime_bg = 'edit'
        self.startdatewidget = None
        self.starttimewidget = None
        self.enddatewidget = None
        self.endtimewidget = None
        self.allday = False
        if not isinstance(start, datetime):
            self.allday = True

        self.checkallday = urwid.CheckBox('Allday', state=self.allday,
                                          on_state_change=self.toggle)
        self.toggle(None, self.allday)

    def toggle(self, checkbox, state):
        self.allday = state
        datewidth = len(self.startdate) + 7

        edit = urwid.Edit(caption=('', 'From: '), edit_text=self.startdate, wrap='any')
        edit = urwid.AttrMap(edit, self.startdate_bg, 'editcp', )
        edit = urwid.Padding(edit, align='left', width=datewidth, left=0, right=1)
        self.startdatewidget = edit

        edit = urwid.Edit(caption=('', 'To:   '), edit_text=self.enddate, wrap='any')
        edit = urwid.AttrMap(edit, self.enddate_bg, 'editcp', )
        edit = urwid.Padding(edit, align='left', width=datewidth, left=0, right=1)
        self.enddatewidget = edit
        if state is True:
            timewidth = 1
            self.starttimewidget = urwid.Text('')
            self.endtimewidget = urwid.Text('')
        elif state is False:
            timewidth = len(self.starttime) + 1
            edit = urwid.Edit(edit_text=self.starttime, wrap='any')
            edit = urwid.AttrMap(edit, self.starttime_bg, 'editcp', )
            edit = urwid.Padding(edit, align='left', width=len(self.starttime) + 1, left=1)
            self.starttimewidget = edit

            edit = urwid.Edit(edit_text=self.endtime, wrap='any')
            edit = urwid.AttrMap(edit, self.endtime_bg, 'editcp', )
            edit = urwid.Padding(edit, align='left', width=len(self.endtime) + 1, left=1)
            self.endtimewidget = edit

        columns = urwid.Pile([
            urwid.Columns([(datewidth, self.startdatewidget), (timewidth, self.starttimewidget)], dividechars=1),
            urwid.Columns([(datewidth, self.enddatewidget), (timewidth, self.endtimewidget)], dividechars=1),
            self.checkallday], focus_item=2)
        urwid.WidgetWrap.__init__(self, columns)

    @property
    def changed(self):
        """
        returns True if content has been edited, False otherwise
        """
        return ((self.startdt != self.newstart) or
                (self.enddt != self.newend))

    @property
    def newstart(self):
        newstartdatetime = self._newstartdate
        if not self.checkallday.state:
            if self.startdt.tzinfo is None:
                tzinfo = self.conf.default_timezone
            else:
                tzinfo = self.startdt.tzinfo
            try:
                newstarttime = self._newstarttime
                newstartdatetime = datetime.combine(newstartdatetime, newstarttime)
                newstartdatetime = tzinfo.localize(newstartdatetime)
            except TypeError:
                return None
        return newstartdatetime

    @property
    def _newstartdate(self):
        try:
            self.startdate = self.startdatewidget.original_widget.original_widget.get_edit_text()
            newstartdate = datetime.strptime(
                self.startdate,
                self.conf.default.longdateformat).date()
            self.startdate_bg = 'edit'
            return newstartdate
        except ValueError:
            self.startdate_bg = 'alert'
            return None

    @property
    def _newstarttime(self):
        try:
            self.starttime = self.starttimewidget.original_widget.original_widget.get_edit_text()
            newstarttime = datetime.strptime(
                self.starttime,
                self.conf.default.timeformat).time()
            self.starttime_bg = 'edit'
            return newstarttime
        except ValueError:
            self.starttime_bg = 'alert'
            return None

    @property
    def newend(self):
        newenddatetime = self._newenddate
        if not self.checkallday.state:
            if self.enddt.tzinfo is None:
                tzinfo = self.conf.default.default_timezone
            else:
                tzinfo = self.enddt.tzinfo
            try:
                newendtime = self._newendtime
                newenddatetime = datetime.combine(newenddatetime, newendtime)
                newenddatetime = tzinfo.localize(newenddatetime)
            except TypeError:
                return None
        return newenddatetime

    @property
    def _newenddate(self):
        try:
            self.enddate = self.enddatewidget.original_widget.original_widget.get_edit_text()
            newenddate = datetime.strptime(
                self.enddate,
                self.conf.default.longdateformat).date()
            self.enddate_bg = 'edit'
            return newenddate
        except ValueError:
            self.enddate_bg = 'alert'
            return None

    @property
    def _newendtime(self):
        try:
            self.endtime = self.endtimewidget.original_widget.original_widget.get_edit_text()
            newendtime = datetime.strptime(
                self.endtime,
                self.conf.default.timeformat).time()
            self.endtime_bg = 'edit'
            return newendtime
        except ValueError:
            self.endtime_bg = 'alert'
            return None


class EventViewer(urwid.WidgetWrap):
    """
    Base Class for EventEditor and EventDisplay
    """
    def __init__(self, conf, dbtool):
        self.conf = conf
        self.dbtool = dbtool
        pile = urwid.Pile([])
        urwid.WidgetWrap.__init__(self, pile)


class EventDisplay(EventViewer):
    """showing events

    widget for displaying one event's details
    """
    def __init__(self, conf, dbtool, event):
        super(EventDisplay, self).__init__(conf, dbtool)
        lines = []
        lines.append(urwid.Text(event.vevent['SUMMARY']))
        if event.allday:
            startstr = event.start.strftime(self.conf.default.dateformat)
            if event.start == event.end:
                lines.append(urwid.Text('On: ' + startstr))
            else:
                endstr = event.end.strftime(self.conf.default.dateformat)
                lines.append(
                    urwid.Text('From: ' + startstr + ' to: ' + endstr))

        else:
            startstr = event.start.strftime(self.conf.default.dateformat +
                                            ' ' + self.conf.default.timeformat)
            if event.start.date == event.end.date:
                endstr = event.end.strftime(self.conf.default.timeformat)
            else:
                endstr = event.end.strftime(self.conf.default.dateformat +
                                            ' ' +
                                            self.conf.default.timeformat)
                lines.append(urwid.Text('From: ' + startstr +
                                        ' To: ' + endstr))

        for key, desc in [('DESCRIPTION', 'Desc'), ('LOCATION', 'Loc')]:
            try:
                lines.append(urwid.Text(
                    desc + ': ' + str(event.vevent[key].encode('utf-8'))))
            except KeyError:
                pass
        pile = urwid.Pile(lines)
        self._w = pile


class EventEditor(EventViewer):
    """
    Widget for event Editing
    """
    def __init__(self, conf, dbtool, event, cancel=None):
        super(EventEditor, self).__init__(conf, dbtool)
        self.event = event
        self.cancel = cancel
        try:
            self.description = event.vevent['DESCRIPTION'].encode('utf-8')
        except KeyError:
            self.description = ''
        try:
            self.location = event.vevent['LOCATION'].encode('utf-8')
        except KeyError:
            self.location = ''

        self.startendeditor = StartEndEditor(event.start, event.end, self.conf)
        try:
            rrule = self.event.vevent['RRULE']
        except KeyError:
            rrule = None
        self.recursioneditor = RecursionEditor(rrule)
        self.summary = urwid.Edit(
            edit_text=event.vevent['SUMMARY'].encode('utf-8'))
        self.description = urwid.Edit(caption='Description: ',
                                      edit_text=self.description)
        self.location = urwid.Edit(caption='Location: ',
                                   edit_text=self.location)
        cancel = urwid.Button('Cancel', on_press=self.cancel)
        save = urwid.Button('Save', on_press=self.save)
        buttons = urwid.Columns([cancel, save])

        self.pile = urwid.Pile([self.summary, self.startendeditor,
                                self.recursioneditor, self.description,
                                self.location, urwid.Text(''), buttons])
        self._w = self.pile

    @classmethod
    def selectable(cls):
        return True

    @property
    def changed(self):
        changed = False
        if self.summary.get_edit_text() != self.event.vevent['SUMMARY']:
            self.event.vevent['SUMMARY'] = self.summary.get_edit_text()
            changed = True
        if self.description.get_edit_text() != self.description:
            self.event.vevent['DESCRIPTION'] = self.description.get_edit_text()
            changed = True
        if self.location.get_edit_text() != self.location:
            self.event.vevent['LOCATION'] = self.location.get_edit_text()
            changed = True
        if self.startendeditor.changed:
            self.event.vevent['DTSTART'].dt = self.startendeditor.newstart
            self.event.vevent['DTEND'].dt = self.startendeditor.newend
            changed = True
        return changed

    def save(self, button):
        changed = self.changed  # need to call this to set startdate_bg etc. to False
        if 'alert' in [self.startendeditor.startdate_bg,
                       self.startendeditor.starttime_bg,
                       self.startendeditor.enddate_bg,
                       self.startendeditor.endtime_bg]:
            self.startendeditor.toggle(None, state=self.startendeditor.allday)
            self.pile.set_focus(1)  # the startendeditor
            return
        if changed is True:
            try:
                self.event.vevent['SEQUENCE'] += 1
            except KeyError:
                self.event.vevent['SEQUNCE'] = 0
            if self.event.status == backend.NEW:
                status = backend.NEW
            else:
                status = backend.CHANGED
            self.dbtool.update(self.event.vevent.to_ical(),
                               self.event.account,
                               self.event.href,
                               status=status)
        self.cancel()

    def keypress(self, size, key):
        key = super(EventEditor, self).keypress(size, key)
        if key in ['left', 'up']:
            return
        elif key in ['esc'] and not self.changed:
            self.cancel()
        else:
            return key


class ClassicView(Pane):
    """default Pane for khal

    showing a CalendarWalker on the left and the eventList + eventviewer/editor
    on the right
    """
    def __init__(self, conf=None, dbtool=None, title=u'', description=u''):
        self.eventscolumn = EventColumn(conf=conf, dbtool=dbtool)
        weeks = calendar_walker(view=self)
        columns = urwid.Columns([(25, weeks), self.eventscolumn],
                                dividechars=2)

        fill = urwid.Filler(columns)
        self.eventscolumn.update(date.today())  # showing with today's events
        Pane.__init__(self, fill, title=title, description=description)

    def get_keys(self):
        return [(['arrows'], 'navigate through the calendar'),
                (['enter'], 'select a date'),
                (['q'], 'quit')
                ]

    def show_date(self, date):
        self.eventscolumn.update(date)

    def new_event(self, date):
        self.eventscolumn.new(date)


def start_pane(pane, header=''):
    """Open the user interface with the given initial pane."""
    frame = Window(header=header,
                   footer='arrows: navigate, enter: select, q: quit, ?: help')
    frame.open(pane)
    loop = urwid.MainLoop(frame, Window.PALETTE,
                          unhandled_input=frame.on_key_press)
    loop.run()