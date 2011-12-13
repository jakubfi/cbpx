from threading import _Event, Event, Timer

# Various thread-related helper classes and functions

# --------------------------------------------------------------------
# Descriptive event. Event with description
class DescEvent(_Event):

    # ----------------------------------------------------------------
    def __init__(self):
        _Event.__init__(self)
        self.reason = "[no reason]"

    # ----------------------------------------------------------------
    def set(self, reason):
        _Event.set(self)
        self.reason = reason

    # ----------------------------------------------------------------
    def clear(self, reason):
        _Event.clear(self)
        self.reason = reason

    # ----------------------------------------------------------------
    def get_reason(self):
        reason = self.reason
        self.reason = "[no reason]"
        return reason


# --------------------------------------------------------------------
# threaded version of time.sleep()
def th_sleep(time):
    e = Event()
    Timer(time, e.set).start()
    e.wait()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
