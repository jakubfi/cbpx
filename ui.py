import time
import readline
import logging

from socket import *

from utils import params, l
from utils import __version__

# ------------------------------------------------------------------------
class ui:

    # --------------------------------------------------------------------
    def __init__(self):
        pass

    # --------------------------------------------------------------------
    def shutdown(self):
        pass

    # --------------------------------------------------------------------
    def read(self):
        time.sleep(1)
        return "hello"

    # --------------------------------------------------------------------
    def write(self, text):
        pass

    # --------------------------------------------------------------------
    def finish(self):
        pass


# ------------------------------------------------------------------------
class ui_readline(ui):

    # --------------------------------------------------------------------
    def print_logo(self):
        print """        __
 .----.|  |--..-----..--.--.
 |  __||  _  ||  _  ||_   _|
 |____||_____||   __||__.__| %s : connection buffering proxy
------------- |__| -----------------------------------------------
""" % __version__

    # --------------------------------------------------------------------
    def __init__(self):
        l.debug("Starting readline user interface")
        self.print_logo()
        print " Ready for your commands, my master.\n"

    # --------------------------------------------------------------------
    def read(self):
        line = raw_input("cbpx> ")
        return line

    # --------------------------------------------------------------------
    def write(self, text):
        print text


# ------------------------------------------------------------------------
class ui_net(ui):

    # --------------------------------------------------------------------
    def __init__(self):
        l.debug("Starting TCP user interface on port %i" % int(params.rc_port))
        self.rc_sock = socket(AF_INET, SOCK_STREAM)
        self.rc_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.rc_sock.bind(('', int(params.rc_port)))
        self.rc_sock.listen(5)

    # --------------------------------------------------------------------
    def shutdown(self):
        l.debug("Shutting down TCP user interface")
        self.rc_sock.shutdown(SHUT_RDWR)
        self.rc_sock.close()

    # --------------------------------------------------------------------
    def read(self):
        l.debug("Awaiting TCP command connection...")
        (self.rc_conn, self.rc_addr) = self.rc_sock.accept()
        l.debug("TCP commnd connection from: %s" % str(self.rc_addr))
        l.debug("Awaiting network command...")
        line = self.rc_conn.recv(int(params.net_buffer_size))
        return self.sanitize(line)

    # --------------------------------------------------------------------
    def sanitize(self, command):
        sanitized = command

        # allow only one-time stats
        if command.startswith("stats") and command != "stats":
            l.debug("Sanitizing command: '%s'" % command)
            sanitized = "stats"

        return sanitized

    # --------------------------------------------------------------------
    def write(self, text):
        try:
            self.rc_conn.send(text + "\n")
        except:
            # we couldn't send command output. so what?
            pass

    # --------------------------------------------------------------------
    def finish(self):
        try:
            self.rc_conn.shutdown(SHUT_RDWR)
            self.rc_conn.close()
        except:
            # so what?
            pass



# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
