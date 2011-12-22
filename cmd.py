import time
import readline
import logging
import threading

from network import cbpx_connector, cbpx_listener, cbpx_transporter, conn_q, relay, switch_finish, check_if_no_connections
from utils import params, l
from utils import __version__
from stats import cbpx_stats


# ------------------------------------------------------------------------
# Timer that handles switch timeout
class SwitchTimer(threading._Timer):

    # --------------------------------------------------------------------
    def __init__(self, timeout):
        threading._Timer.__init__(self, timeout, self.timeout_action)
        self.setName("SWTimer")

    # --------------------------------------------------------------------
    def timeout_action(self):
        switch_finish.acquire()
        if not relay.isSet():
            relay.set("switch timeout")
            l.warning("Switch time exceeded")
        switch_finish.release()


# ------------------------------------------------------------------------
class cmd_runner:

    # --------------------------------------------------------------------
    def __init__(self, ui):
        self.ui = ui
        self.commands = {
            'help' : [self.cmd_help, "Print this help"],
            'quit' : [self.cmd_quit, "Kill the kitten. Using 'force' is an option."],
            'threads' : [self.cmd_threads, "List alive threads"],
            'switch' : [self.cmd_switch, "Summon All Demons of Evil"],
            'stats' : [self.cmd_stats, "Print current statistics (stats [SLEEP] [COUNT])"],
            'set' : [self.cmd_set, "Show/set variables (set PARAMETER VALUE)"],
            'hello' : [self.cmd_hello, "Be polite, say hello"]
        }

    # --------------------------------------------------------------------
    def cmd_help(self, args):
        self.ui.write(" Available commands:")
        for c in sorted(self.commands.keys()):
            self.ui.write("   %-10s : %s " % (c, self.commands[c][1]))

    # --------------------------------------------------------------------
    def cmd_quit(self, args):

        force = False
        try:
            if args[0]:
                if args[0] == "force":
                    force = True
                else:
                    self.ui.write(" I don't know how to quit this way, sorry")
                    return 0
        except:
            pass

        if not force:
            if (cbpx_stats.c_endpoints > 0):
                self.ui.write(" I won't quit with active connections. See stats.")
                return 0
            if (conn_q.qsize() > 0):
                self.ui.write(" I won't quit with connections in queue. See stats.")
                return 0
            self.ui.write(" Exiting...")
        else:
            self.ui.write(" Terminating connections and exiting...")
        return 1

    # --------------------------------------------------------------------
    def cmd_threads(self, args):
        threads = ""
        for t in threading.enumerate():
            threads = "%s %s" % (t.getName(), threads)

        self.ui.write(" Threads: %s" % threads)

    # --------------------------------------------------------------------
    def cmd_switch(self, args):
        active = cbpx_connector.backend
        standby = int(not cbpx_connector.backend)

        self.ui.write(" Starting switch: %s:%i -> %s:%i, timeout: %2.2f s, %i connections buffer\n" % (cbpx_connector.backends[active][0], cbpx_connector.backends[active][1], cbpx_connector.backends[standby][0], cbpx_connector.backends[standby][1], float(params.switch_max_time), int(params.max_queued_conns)))
        l.info("Starting switch: %s:%i -> %s:%i, timeout: %2.2f s, %i connections buffer" % (cbpx_connector.backends[active][0], cbpx_connector.backends[active][1], cbpx_connector.backends[standby][0], cbpx_connector.backends[standby][1], float(params.switch_max_time), int(params.max_queued_conns)))

        # stop relaying connections now
        relay.clear("switch started")

        # check for 'dry switch' with no connections
        l.debug("Checking first for no connections")
        switch_finish.acquire()
        check_if_no_connections()
        switch_finish.release()

        # set the timer for max switch time
        switch_timer = SwitchTimer(float(params.switch_max_time))
        switch_timer.start()
        switch_start = time.time()

        # print initial stats
        self.print_stats(True, 0)

        l.debug("About to enter switch loop")

        while not relay.isSet():
            try:
                l.debug("Switch loop wait")
                threading.Event().wait(float(params.switch_loop_wait))

                # print stats
                waited = time.time() - switch_start
                self.print_stats(False, waited)
                l.debug("Switch active, waited: %2.2f" % waited)

            except Exception, e:
                l.info("Exception in 'switch' loop: %s" % str(e))

            except KeyboardInterrupt:
                l.warning("Ctrl-c in switch loop, break")
                self.ui.write(" Ctrl-c")
                switch_finish.acquire()
                relay.set("ctrl-c")
                switch_finish.release()

        switch_timer.cancel()

        l.debug("Loop done, checking conditions")

        # check what happened and report to user
        reason = relay.get_reason()
        if cbpx_connector.backend == active:
            l.warning("Backend not switched: %s" % reason)
            self.ui.write("\n Switch failed: %s" % reason)
        else:
            l.info("Backend switched: %s" % reason)
            self.ui.write("\n Switch OK!: %s " % reason)


    # --------------------------------------------------------------------
    def print_stats(self, header, switch):
        sw = "[n/a] "
        if switch != -1:
            try:
                sw = "%2.2f" % float(switch)
            except:
                pass
        if header:
            self.ui.write(" SWtime Current backend       active in queue enqueued dequeued avgcps   cps")
            self.ui.write(" ------ --------------------- ------ -------- -------- -------- ------ -----")
        self.ui.write(" %-6s %-21s %6i %8i %8i %8i %6i %5i" % (sw, cbpx_connector.backends[cbpx_connector.backend][0] + ":" + str(cbpx_connector.backends[cbpx_connector.backend][1]), cbpx_stats.c_endpoints/2, conn_q.qsize(), cbpx_stats.c_qc, cbpx_stats.c_dqc, cbpx_stats.a_qc, cbpx_stats.s_qc))

    # --------------------------------------------------------------------
    def cmd_stats(self, args):

        try:
            maxloop = int(args[1])
            if maxloop < 1:
                self.ui.write(" Stats loop count should be >= 1")
                return
        except:
            maxloop = 0

        try:
            sleep = float(args[0])
            if sleep < 0.1:
                self.ui.write(" Stats loop sleep should be >= 0.1")
                return
        except Exception, e:
            sleep = 0

        cnt = 0

        while True:
            if not cnt % 50:
                self.print_stats(True, -1)
            else:
                self.print_stats(False, -1)
            cnt += 1
            try:
                threading.Event().wait(float(args[0]))
                if maxloop and cnt >= maxloop:
                    break
            except Exception, e:
                l.debug("Exception in 'stats' loop: %s, break" % str(e))
                break
            except KeyboardInterrupt:
                l.debug("Ctrl-C in stats loop, break")
                break

    # --------------------------------------------------------------------
    def print_cfg(self):
        if int(params.rc_port) > 0:
            remote = str(params.rc_port)
        else:
            remote = "DISABLED"
        self.ui.write(" Remote control port : %s" % remote)
        self.ui.write(" Listening on        : %i" % params.port)
        self.ui.write(" Active backend      : %s:%i" % (params.active_ip, params.active_port))
        self.ui.write(" Standby backend     : %s:%i" % (params.standby_ip, params.standby_port))
        self.ui.write(" Switch timeout      : %2.2f s" % float(params.switch_max_time))
        self.ui.write(" Max queued conns    : %i" % int(params.max_queued_conns))
        self.ui.write(" Max open conns      : %i" % int(params.max_open_conns))
        self.ui.write(" listen() backlog    : %i" % int(params.listen_backlog))
        self.ui.write(" Network buffer      : %i bytes" % int(params.net_buffer_size))
        self.ui.write(" Safe switch delay   : %2.2f s" % float(params.switch_delay))
        self.ui.write(" Switch loop wait    : %2.2f s" % float(params.switch_loop_wait))
        self.ui.write(" Log file            : %s" % params.log_file)
        self.ui.write(" Log level           : %s" % params.log_level)
        self.ui.write("")
        self.ui.write(" Dynamic: %s" % str(params.settable.keys()))

    # --------------------------------------------------------------------
    def cmd_set(self, args):
        # no arguments = prit current settings
        if len(args) == 0:
            self.print_cfg()
            return

        # wrong number of arguments
        if len(args) != 2:
            self.ui.write("Use: 'set PARAMETER VALUE' to change setting")
            return

        # check if parameter is available in configuration
        if not hasattr(params, args[0]):
            self.ui.write(" No such parameter: %s" % args[0])
            return

        # check if parameter can be set
        if args[0] not in params.settable:
            self.ui.write(" Paremeter is not settable: %s" % args[0])
            return

        # check if value type is correct
        try:
            v_test = params.settable[args[0]][0] (args[1])
        except:
            self.ui.write(" VALUE for '%s' must be of %s" % (args[0], params.settable[args[0]][0]))
            return

        # check if value range is correct
        if v_test < params.settable[args[0]][1] or v_test > params.settable[args[0]][2]:
            self.ui.write(" %s must be between %s and %s" % (args[0], str(params.settable[args[0]][1]), str(params.settable[args[0]][2])))
            return

        # everything looks fine, set the parameter
        l.debug("Setting '%s' to '%s'" % (args[0], args[1]))
        try:
            params.__dict__[args[0]] = args[1]
        except Exception, e:
            self.ui.write(" Could not set parameter '%s' to '%s', error: %s" % (args[0], args[1], str(e)))
            l.warning("Could not set parameter '%s' to '%s', error: %s" % (args[0], args[1], str(e)))
            return

        self.ui.write(" Parameter '%s' set to '%s' " % (args[0], params.__dict__[args[0]]))

    # --------------------------------------------------------------------
    def cmd_hello(self, args):
        self.ui.write(" Hello! I'm cbpx %s. And you look great today, I must say." % __version__)

    # --------------------------------------------------------------------
    def process_command(self):
        try:
            line = self.ui.read()
            if not line:
                return
            l.info("Got command: '%s'" % line)
            l_cmd = line.split(" ")[0]
            l_args = line.split(" ")[1:]
            if l_cmd and (l_cmd not in self.commands.keys()):
                self.ui.write(" Unknown command: '%s'" % l_cmd)
                self.ui.finish()
            else:
                res = self.commands[l_cmd][0](l_args)
                self.ui.finish()
                return res
        except KeyboardInterrupt:
            l.debug("Got KeyboardInterrupt, ignoring")
            self.ui.write("")
        except EOFError:
            self.ui.write("")
        except Exception, e:
            l.warning("Exception %s: %s" % (type(e), str(e)))
        return

    # --------------------------------------------------------------------
    def run(self):
        while True:
            if self.process_command():
                break
        self.ui.shutdown()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
