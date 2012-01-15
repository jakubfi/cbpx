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

from threading import Thread, Event
from utils import l

# ------------------------------------------------------------------------
class cbpx_stats(Thread):

    sleep = 1
    ticks = 0

    c_endpoints = 0

    c_qc = 0
    l_qc = 0
    s_qc = 0

    c_dqc = 0
    l_dqc = 0
    s_dqc = 0

    # --------------------------------------------------------------------
    def __init__(self):
        l.debug("Starting stats")
        Thread.__init__(self, name="Stats")
        self.quit = False
        self.fin = Event()

    # --------------------------------------------------------------------
    def run(self):
        while not self.quit:
            l.debug("Waiting for stats timer...")
            self.fin.wait(cbpx_stats.sleep)
            #cbpx_stats.ticks += 1

            cbpx_stats.s_qc = (cbpx_stats.c_qc - cbpx_stats.l_qc) * (1/cbpx_stats.sleep)
            cbpx_stats.s_dqc = (cbpx_stats.c_dqc - cbpx_stats.l_dqc) * (1/cbpx_stats.sleep)
            cbpx_stats.l_qc = cbpx_stats.c_qc
            cbpx_stats.l_dqc = cbpx_stats.c_dqc

    # --------------------------------------------------------------------
    def close(self):
        l.debug("Closing stats")
        self.quit = True


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
