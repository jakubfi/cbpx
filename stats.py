from threading import Thread, Event
from utils import l

# ------------------------------------------------------------------------
class cbpx_stats(Thread):

    ticks = 0

    c_transporters = 0

    c_qc = 0
    l_qc = 0
    s_qc = 0
    a_qc = 0.0

    c_dqc = 0
    l_dqc = 0
    s_dqc = 0
    a_dqc = 0.0

    # --------------------------------------------------------------------
    def process(self):
        cbpx_stats.s_qc = cbpx_stats.c_qc - cbpx_stats.l_qc
        cbpx_stats.s_dqc = cbpx_stats.c_dqc - cbpx_stats.l_dqc
        cbpx_stats.a_qc = cbpx_stats.c_qc / cbpx_stats.ticks
        cbpx_stats.a_dqc = cbpx_stats.c_dqc / cbpx_stats.ticks
        cbpx_stats.l_qc = cbpx_stats.c_qc
        cbpx_stats.l_dqc = cbpx_stats.c_dqc
        
    # --------------------------------------------------------------------
    def __init__(self):
        l.info("Starting stats")
        Thread.__init__(self)
        self.setName("Stats")
        self.quit = False
        self.fin = Event()

    # --------------------------------------------------------------------
    def run(self):
        while not self.quit:
            l.debug("Waiting for stats timer...")
            self.fin.wait(1)
            cbpx_stats.ticks += 1
            self.process()

    # --------------------------------------------------------------------
    def close(self):
        l.info("Closing stats")
        self.quit = True
        

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
