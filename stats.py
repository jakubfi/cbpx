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
