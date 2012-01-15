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

from threading import Condition, Lock

# --------------------------------------------------------------------
# Relay gate (based on python's _Event)
class RelayGate():

    # ----------------------------------------------------------------
    def __init__(self):
        self.__cond = Condition(Lock())
        self.__flag = False
        self.reason = "[no reason]"
        self.backends = [('0.0.0.0', 0), ('0.0.0.0', 0)]
        self.backend = 0

    # ----------------------------------------------------------------
    def isSet(self):
        return self.__flag

    # ----------------------------------------------------------------
    def set_backends(self, ai, ap, si, sp):
        self.__cond.acquire()
        try:
            self.backends = [(ai, ap), (si, sp)]
        finally:
            self.__cond.release()

    # ----------------------------------------------------------------
    def switch_backend(self, reason):
        self.__cond.acquire()
        try:
            if not self.__flag:
                self.backend = int(not self.backend)
                self.reason = reason
                self.__flag = True
            self.__cond.notify_all()
        finally:
            self.__cond.release()

    # ----------------------------------------------------------------
    def set(self, reason):
        self.__cond.acquire()
        try:
            if not self.__flag:
                self.__flag = True
                self.reason = reason
            self.__cond.notify_all()
        finally:
            self.__cond.release()

    # ----------------------------------------------------------------
    def clear(self, reason):
        self.__cond.acquire()
        try:
            if self.__flag:
                self.reason = reason
                self.__flag = False
        finally:
            self.__cond.release()

    # ----------------------------------------------------------------
    def wait(self, timeout=None):
        self.__cond.acquire()
        try:
            if not self.__flag:
                self.__cond.wait(timeout)
            return self.__flag
        finally:
            self.__cond.release()

    # ----------------------------------------------------------------
    def get_active(self):
        return self.backends[self.backend]

    # ----------------------------------------------------------------
    def get_standby(self):
        return self.backends[int(not self.backend)]

    # ----------------------------------------------------------------
    def get_reason(self):
        self.__cond.acquire()
        try:
            reason = self.reason
            self.reason = "[no reason]"
        finally:
            self.__cond.release()
        return reason


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
