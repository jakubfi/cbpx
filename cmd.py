import time
import readline
import logging
import threading

from network import *
from utils import *
from utils import __version__

# ------------------------------------------------------------------------
class cmd_interface:

    def __init__(self):
        pass

    def shutdown(self):
        pass

    def read(self):
        time.sleep(1)
        return "hello"

    def write(self, text):
        pass

    def finish(self):
        pass


# ------------------------------------------------------------------------
class cmd_interface_readline(cmd_interface):

    def __init__(self):
        l.info("Starting readline command interface")
        print " Ready for your commands, my master."

    def read(self):
        line = raw_input("cbpx> ")
        return line

    def write(self, text):
        print text


# ------------------------------------------------------------------------
class cmd_interface_net(cmd_interface):

    def __init__(self):
        l.info("Starting TCP command interface on port %i" % int(params.rc_port))
        self.rc_sock = socket(AF_INET, SOCK_STREAM)
        self.rc_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.rc_sock.bind(('', int(params.rc_port)))
        self.rc_sock.listen(5)
        print " Ready for your commands on TCP port %i, my master." % int(params.rc_port)

    def shutdown(self):
        self.rc_sock.shutdown(SHUT_RDWR)
        self.rc_sock.close()

    def read(self):
        l.debug("Awaiting TCP command connection...")
        (self.rc_conn, self.rc_addr) = self.rc_sock.accept()
        l.info("TCP commnd connection from: %s" % str(self.rc_addr))
        l.debug("Awaiting network command...")
        line = self.rc_conn.recv(int(params.net_buffer_size))
        return line

    def write(self, text):
        self.rc_conn.send(text + "\n")
        pass

    def finish(self):
        self.rc_conn.shutdown(SHUT_RDWR)
        self.rc_conn.close()

# ------------------------------------------------------------------------
class cmd_runner:

    # --------------------------------------------------------------------
    def __init__(self, cmd_if):
        self.cmd = cmd_if
        self.commands = {
            'help' : [self.cmd_help, "Print this help"],
            'quit' : [self.cmd_quit, "Kill the kitten"],
            'threads' : [self.cmd_threads, "List alive threads"],
            'switch' : [self.cmd_switch, "Summon All Demons of Evil"],
            'stats' : [self.cmd_stats, "Print current statistics (stats [SLEEP])"],
            'set' : [self.cmd_set, "Show/set variables (set PARAMETER VALUE)"],
            'hello' : [self.cmd_hello, "Be polite, say hello"]
        }

    # --------------------------------------------------------------------
    def cmd_help(self, args):
        l.debug("Processing command")
        self.cmd.write("\n Available commands:\n")
        for c in sorted(self.commands.keys()):
            self.cmd.write("   %-10s : %s " % (c, self.commands[c][1]))
        self.cmd.write("")

    # --------------------------------------------------------------------
    def cmd_quit(self, args):
        l.debug("Processing command")
        if (cbpx_transporter.c_transporters > 0):
            self.cmd.write(" I won't quit with active connections. See stats.")
            return
        if (conn_q.qsize() > 0):
            self.cmd.write(" I won't quit with connections in queue. See stats.")
            return
        self.cmd.write(" Exiting...")
        return 1

    # --------------------------------------------------------------------
    def cmd_threads(self, args):
        l.debug("Processing command")

        workers = 0
        threads = ""
        for t in threading.enumerate():
            if t.getName().startswith("Thread-"):
                workers += 1
            else:
                threads = threads + ", " + t.getName()

        self.cmd.write("Threads: Workers: %i%s" % (workers, threads))

    # --------------------------------------------------------------------
    def cmd_switch(self, args):
        l.debug("Processing command")

        active = cbpx_connector.backend
        standby = int(not cbpx_connector.backend)

        self.cmd.write("")
        self.cmd.write(" Starting switch: %s:%i -> %s:%i, timeout: %2.2f s, %i connections buffer" % (cbpx_connector.backends[active][0], cbpx_connector.backends[active][1], cbpx_connector.backends[standby][0], cbpx_connector.backends[standby][1], float(params.switch_max_time), int(params.max_queued_conns)))
        self.cmd.write("")
        l.info("Starting switch: %s:%i -> %s:%i, timeout: %2.2f s, %i connections buffer" % (cbpx_connector.backends[active][0], cbpx_connector.backends[active][1], cbpx_connector.backends[standby][0], cbpx_connector.backends[standby][1], float(params.switch_max_time), int(params.max_queued_conns)))

        old_backend = cbpx_connector.backend

        # stop relaying connections now
        relay.clear()

        # check for 'dry switch' with no connections
        switch_finish.acquire()
        l.debug("Checking first for no connections")
        check_if_no_connections()
        switch_finish.release()

        # required for loop delay timer
        e = threading.Event()

        waited = 0
        while True:
            try:
                l.debug("Switch active, waited: %2.2f" % float(waited))

                # wait params.switch_loop_wait seconds before next loop turn
                l.debug("Switch loop wait")
                e.clear()
                threading.Timer(float(params.switch_loop_wait), e.set).start()
                e.wait()

                # print stats
                if not int((waited/float(params.switch_loop_wait))) % 50: self.print_stats(True, waited)
                else: self.print_stats(False, waited)

                waited += float(params.switch_loop_wait)

                # check if one of other threads enabled relaying in the meantime
                if relay.isSet():
                    l.info("Relaying enabled during switch wait")
                    if cbpx_connector.backend == old_backend:
                        # if backend stays the same, it means connection limit was reached
                        self.cmd.write(" Queued connections limit reached")
                    break

                # check if we're out of loop time here
                if waited > float(params.switch_max_time):
                    l.warning("Switch time exceeded")
                    self.cmd.write(" Timeout reached")
                    break

            except Exception, e:
                l.warning("Exception in 'switch' loop: %s, break" % str(e))
                self.cmd.write(" Exception: %s" % str(e))
                break

            except KeyboardInterrupt:
                l.warning("Ctrl-c in switch loop, break")
                self.cmd.write(" Ctrl-c")
                break

        l.debug("Loop done, checking conditions")

        # check what happened and report to user
        switch_finish.acquire()
        if cbpx_connector.backend == old_backend:
            l.warning("Backend not switched")
            self.cmd.write("")
            self.cmd.write(" Switch failed")
        else:
            l.info("Backend switched")
            self.cmd.write("")
            self.cmd.write(" Switch OK!")
        relay.set()
        switch_finish.release()
        
        
    # --------------------------------------------------------------------
    def print_stats(self, header, switch):
        sw = "  --  "
        if switch != -1:
            try:
                sw = "%2.2f" % float(switch)
            except:
                pass
        if header:
            self.cmd.write(" SWtime Current backend       active in queue enqueued dequeued opened closed")
            self.cmd.write(" ------ --------------------- ------ -------- -------- -------- ------ ------")
        self.cmd.write(" %-6s %-21s %6i %8i %8i %8i %6i %6i" % (sw, cbpx_connector.backends[cbpx_connector.backend][0] + ":" + str(cbpx_connector.backends[cbpx_connector.backend][1]), cbpx_transporter.c_transporters/2, conn_q.qsize(), cbpx_listener.c_queued_conns, cbpx_connector.c_dequeued_conns, cbpx_transporter.c_opened_conns, cbpx_transporter.c_closed_conns))

    # --------------------------------------------------------------------
    def cmd_stats(self, args):
        l.debug("Processing command")

        e = threading.Event()
        cnt = 0
        while True:
            e.clear()
            if not cnt % 50: self.print_stats(True, -1)
            else: self.print_stats(False, -1)
            cnt += 1
            try:
                threading.Timer(float(args[0]), e.set).start()
                e.wait()
            except Exception, e:
                l.debug("Exception in 'stats' loop: %s, break" % str(e))
                break
            except KeyboardInterrupt:
                l.debug("Ctrl-C in stats loop, break")
                break

    # --------------------------------------------------------------------
    def cmd_set(self, args):
        l.debug("Processing command")

        # no arguments = prit current settings
        if len(args) == 0:
            print_cfg()
            self.cmd.write("Settable: %s" % str(params.settable))
            return

        # wrong number of arguments
        if len(args) != 2:
            self.cmd.write("Use: 'set PARAMETER VALUE' to change setting")
            return

        # check if parameter is available in configuration
        if not hasattr(params, args[0]):
            self.cmd.write(" No such parameter: %s" % args[0])
            return

        # check if parameter can be set
        if args[0] not in params.settable:
            self.cmd.write(" Paremeter is not settable: %s" % args[0])
            return

        # everything looks fine, set the parameter

        l.info("Setting '%s' to '%s'" % (args[0], args[1]))
        try:
            params.__dict__[args[0]] = args[1]
        except Exception, e:
            self.cmd.write(" Could not set parameter '%s' to '%s', error: %s" % (args[0], args[1], str(e)))
            l.warning("Could not set parameter '%s' to '%s', error: %s" % (args[0], args[1], str(e)))
            raise e
        self.cmd.write(" Parameter '%s' set to '%s' " % (args[0], params.__dict__[args[0]]))

    # --------------------------------------------------------------------
    def cmd_hello(self, args):
        l.debug("Processing command")
        self.cmd.write(" Hello! I'm cbpx %s" % __version__)

   
    # --------------------------------------------------------------------
    def process_command(self):
        try:
            line = self.cmd.read()
            l.debug("Got input: '%s'" % line)
            if not line:
                return
            l_cmd = line.split(" ")[0]
            l_args = line.split(" ")[1:]
            if l_cmd and (l_cmd not in self.commands.keys()):
                self.cmd.write(" Unknown command: '%s'" % l_cmd)
            else:
                res = self.commands[l_cmd][0](l_args)
                self.cmd.finish()
                return res
        except KeyboardInterrupt:
            l.debug("Got KeyboardInterrupt, ignoring")
            self.cmd.write("")
        except EOFError:
            self.cmd.write("")
        except Exception, e:
            l.warning("Exception %s: %s" % (type(e), str(e)))
        return

    # --------------------------------------------------------------------
    def run(self):
        while True:
            if self.process_command():
                break

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
