from utils import params, l
from network import cbpx_listener, cbpx_connector, cbpx_transporter
from cmd import cmd_runner
from ui import ui_net, ui_readline
from stats import cbpx_stats

# ------------------------------------------------------------------------
class cbpx:

    # --------------------------------------------------------------------
    def __init__(self):

        # start gathering statistics

        try:
            l.debug("Proxy setting up stats")
            self.stats = cbpx_stats()
        except Exception, e:
            raise RuntimeError("Error setting up stats: %s" % str(e))

        # start transporter

        try:
            l.debug("Proxy setting up Transporter")
            self.transporter = cbpx_transporter()
        except Exception, e:
            raise RuntimeError("Error setting up transporter: %s" % str(e))

        # start connector

        try:
            l.debug("Proxy setting up Connector")
            self.connector = cbpx_connector(params.backends, self.transporter)
        except Exception, e:
            raise RuntimeError("Error setting up connector: %s" % str(e))

        # start listener

        try:
            l.debug("Proxy setting up Listener")
            self.listener = cbpx_listener(params.port)
        except Exception, e:
            raise RuntimeError("Error setting up listener: %s" % str(e))

        # setup command interface

        try:
            if int(params.rc_port) > 0:
                l.debug("Proxy setting up command runner with network user interface")
                self.cmd = cmd_runner(ui_net())
            else:
                l.debug("Proxy setting up command runner with readline user interface")
                self.cmd = cmd_runner(ui_readline())
        except Exception, e:
            raise RuntimeError("Error setting up command interface: %s" % str(e))

    # --------------------------------------------------------------------
    def close(self):
        l.debug("Proxy closing listener")
        try: self.listener.close()
        except: pass
        l.debug("Proxy joining listener")
        self.listener.join()

        l.debug("Proxy closing connector")
        try: self.connector.close()
        except: pass
        l.debug("Proxy joining connector")
        self.connector.join()

        l.debug("Proxy closing stats")
        try: self.stats.close()
        except: pass
        l.debug("Proxy joining stats")
        self.stats.join()

        l.debug("Proxy closing transporter")
        try: self.transporter.close()
        except: pass

        l.debug("Proxy killing connections (if any) on close()")
        self.transporter.kill_connections()

        l.debug("Proxy joining transporter")
        self.transporter.join()

    # --------------------------------------------------------------------
    def run(self):
        l.debug("Proxy starting stats")
        self.stats.start()
        l.debug("Proxy starting transporter")
        self.transporter.start()
        l.debug("Proxy starting connector")
        self.connector.start()
        l.debug("Proxy starting listener")
        self.listener.start()
        l.debug("Proxy starting command interface")
        self.cmd.run()
        l.debug("Exiting proxy run() loop")

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
