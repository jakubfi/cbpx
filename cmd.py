import readline
import logging
import threading

from network import *
from utils import *

# ------------------------------------------------------------------------
def cmd_help(args):
    l.debug("Processing command")
    print "\n Available commands:\n"
    for c in sorted(commands.keys()):
        print "   %-10s : %s " % (c, commands[c][1])
    print

# ------------------------------------------------------------------------
def cmd_quit(args):
    l.debug("Processing command")
    if (cbpx_transporter.c_transporters > 0):
        print " I won't quit with active connections. See stats."
        return
    if (conn_q.qsize() > 0):
        print " I won't quit with connections in queue. See stats."
        return
    print " Exiting..."
    return 1

# ------------------------------------------------------------------------
def cmd_threads(args):
    l.debug("Processing command")
    print " Threads: ",
    workers = 0
    for t in threading.enumerate():
        if t.getName().startswith("Thread-"):
            workers += 1
        else:
            print "%s," % t.getName(),
    print "Transporters: %i " % workers

# ------------------------------------------------------------------------
def cmd_switch(args):
    l.debug("Processing command")

    active = cbpx_connector.backend
    standby = int(not cbpx_connector.backend)

    print
    print " Starting switch: %s:%i -> %s:%i, timeout: %2.2f s, %i connections buffer" % (cbpx_connector.backends[active][0], cbpx_connector.backends[active][1], cbpx_connector.backends[standby][0], cbpx_connector.backends[standby][1], float(params.max_time), int(params.max_conn))
    print
    l.debug("Starting switch: %s:%i -> %s:%i, timeout: %2.2f s, %i connections buffer" % (cbpx_connector.backends[active][0], cbpx_connector.backends[active][1], cbpx_connector.backends[standby][0], cbpx_connector.backends[standby][1], float(params.max_time), int(params.max_conn)))

    old_backend = cbpx_connector.backend

    relay.clear()
    waited = 0

    # check for 'dry switch' with no connections
    switch_finish.acquire()
    l.debug("Checking first for no connections")
    check_if_no_connections()
    switch_finish.release()

    e = threading.Event()

    while True:
        try:
            l.debug("Switch active, waited: %2.2f" % float(waited))

            # wait params.switch_loop_wait
            l.debug("Switch loop wait")
            e.clear()
            threading.Timer(float(params.switch_loop_wait), e.set).start()
            e.wait()

            # print stats
            if not int((waited/float(params.switch_loop_wait))) % 50: print_stats(True, waited)
            else: print_stats(False, waited)

            waited += float(params.switch_loop_wait)

            # check if we switched backends already
            if relay.is_set():
                l.debug("Relaying enabled during switch wait")
                if cbpx_connector.backend == old_backend:
                    print " Connection limit reached"
                break

            # check if we're out of time
            if waited > float(params.max_time):
                l.debug("Switch time exceeded")
                print ' Timeout reached'
                break

        except Exception, e:
            l.warning("Exception in 'switch' loop: %s, break" % str(e))
            print " Exception: %s" % str(e)
            break

        except KeyboardInterrupt:
            l.warning("Ctrl-c in switch loop, break")
            print " Ctrl-c"
            break

    l.debug("Loop done, checking conditions")

    switch_finish.acquire()
    if cbpx_connector.backend == old_backend:
        l.debug("Backend not switched")
        print
        print " Switch failed"
    else:
        l.debug("Backend switched")
        print
        print " Switch OK!"
    relay.set()
    switch_finish.release()
        
        
# ------------------------------------------------------------------------
def print_stats(header, switch):
    sw = "  --  "
    if switch != -1:
        try:
            sw = "%2.2f" % float(switch)
        except:
            pass
    if header:
        print " SWtime Current backend       active in queue enqueued dequeued opened closed"
        print " ------ --------------------- ------ -------- -------- -------- ------ ------"
    print " %-6s %-21s %6i %8i %8i %8i %6i %6i" % (sw, cbpx_connector.backends[cbpx_connector.backend][0] + ":" + str(cbpx_connector.backends[cbpx_connector.backend][1]), cbpx_transporter.c_transporters/2, conn_q.qsize(), cbpx_listener.c_queued_conns, cbpx_connector.c_dequeued_conns, cbpx_transporter.c_opened_conns, cbpx_transporter.c_closed_conns)

# ------------------------------------------------------------------------
def cmd_stats(args):
    l.debug("Processing command")

    e = threading.Event()
    cnt = 0
    while True:
        e.clear()
        if not cnt % 50: print_stats(True, -1)
        else: print_stats(False, -1)
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

# ------------------------------------------------------------------------
def cmd_set(args):
    l.debug("Processing command")

    if len(args) == 0:
        print_cfg()
        print "Settable: %s" % str(params.settable)
        return
    
    if len(args) != 2:
        print "Use: 'set PARAMETER VALUE' to change setting"
        return

    if not hasattr(params, args[0]):
        print " No such parameter: %s" % args[0]
        return

    if args[0] not in params.settable:
        print " Paremeter is not settable: %s" % args[0]
        return

    l.debug("Setting '%s' to '%s'" % (args[0], args[1]))
    try:
        params.__dict__[args[0]] = args[1]
    except Exception, e:
        print " Could not set parameter '%s' to '%s', error: %s" % (args[0], args[1], str(e))
        l.warning("Could not set parameter '%s' to '%s', error: %s" % (args[0], args[1], str(e)))
        raise e
    print " Parameter '%s' set to '%s' " % (args[0], params.__dict__[args[0]])

# ------------------------------------------------------------------------
commands = {
    'help' : [cmd_help, "Print this help"],
    'quit' : [cmd_quit, "Kill the kitten"],
    'threads' : [cmd_threads, "List alive threads"],
    'switch' : [cmd_switch, "Summon All Demons of Evil"],
    'stats' : [cmd_stats, "Print current network statistics (stats [SLEEP])"],
    'set' : [cmd_set, "Show/set variables (set PARAMETER VALUE)"]
}

# ------------------------------------------------------------------------
def process_command():
    try:
        line = raw_input("cbpx> ")
        l.debug("Got input: '%s'" % line)
        if not line:
            return
        l_cmd = line.split(" ")[0]
        l_args = line.split(" ")[1:]
        if l_cmd and (l_cmd not in commands.keys()):
            print "Unknown command: '%s'" % l_cmd
        else:
            return commands[l_cmd][0](l_args)
    except KeyboardInterrupt:
        l.debug("Got KeyboardInterrupt, ignoring")
        print
    except EOFError:
        print
    except Exception, e:
        l.warning("Exception %s: %s" % (type(e), str(e)))
    return

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
