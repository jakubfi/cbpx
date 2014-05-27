#  Copyright (c) 2011-2012 Jakub Filipowicz <jakubf@gmail.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#  Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import time
import readline
import logging

from socket import *

from utils import params, l
from utils import __version__

COMMANDS = ["help", "quit", "threads", "switch", "stats", "set", "hello"]

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
    def __print_logo(self):
        print """        __
 .----.|  |--..-----..--.--.
 |  __||  _  ||  _  ||_   _|
 |____||_____||   __||__.__| %s : connection buffering proxy
------------- |__| -----------------------------------------------
""" % __version__

    # --------------------------------------------------------------------
    def __complete(self, text, state):
        for cmd in COMMANDS:
            if cmd.startswith(text):
                if not state:
                    return cmd
                else:
                    state -= 1
    # --------------------------------------------------------------------
    def __init__(self):
        l.debug("Starting readline user interface")
        self.__print_logo()
        print " Ready for your commands, my master.\n"

    # --------------------------------------------------------------------
    def read(self):
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self.__complete)
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
