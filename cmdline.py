import sys
import time
import readline
import logging
import threading

from network import *
from utils import *

l = logging.getLogger('cmdline')
l.setLevel(logging.__dict__["_levelNames"][params.log_level])

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
    if (cbpx_listener.conn_q.qsize() > 0):
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
    if cbpx_listener.backend == 1:
        print " I think we did that already."
        return
    lock_connection.acquire()
    cbpx_listener.is_switch = 1
    lock_connection.release()
    l.info("Switch initiated, Waiting for connections to finish")

    print " Waiting for connections to finish"
    waited = 0
    while (waited < float(params.max_time)):
        time.sleep(float(params.switch_loop_wait))
        waited += float(params.switch_loop_wait)
        print " connections active/queued: %4i/%-4i switch time: %2.1f" % (cbpx_transporter.c_transporters, cbpx_listener.conn_q.qsize(), waited)
        lock_connection.acquire()
        if (cbpx_listener.is_switch == 0):
            lock_connection.release()
            l.info("Switch terminated while waiting")
            if cbpx_listener.backend == 1:
                print " Backend switched"
                l.info("Switch finished successfully while waiting")
            else:
                print " Switch failed (connection queue full)"
                l.warning("Switch failed while waiting")
            break
        lock_connection.release()

    l.debug("Outside switch wait loop")

    if (waited >= float(params.max_time)):
        print " Switch timed out"
        l.info("Switch timed out")
        lock_connection.acquire()
        if (cbpx_listener.is_switch == 0):
            l.debug("Switch finished just after timeout")
            if cbpx_listener.backend == 1:
                print " But we managed to switch in the meantime :-)"
                l.info("Looks like switch went fine")
            else:
                print " Switch failed"
                l.warning("Switch failed after the wait loop")
        else:
            print " Switch failed after the timeout"
            l.warning("Switch failed after the timeout")
            cbpx_listener.is_switch = 0
        lock_connection.release()
        do_flush.set()
    else:
        l.info("Switch finished in: %f seconds, limit was: %f" % (waited, params.max_time))

    l.debug("Leaving switch block")

# ------------------------------------------------------------------------
def cmd_stats(args):
    l.debug("Processing command")

    e = threading.Event()

    while True:
        e.clear()
        print " Backend           : %s:%s" % (cbpx_listener.backends[cbpx_listener.backend]["ip"], cbpx_listener.backends[cbpx_listener.backend]["port"])
        print " Active transports : %i (%i connections)" % (cbpx_transporter.c_transporters, cbpx_transporter.c_transporters/2)
        print " Currently queued  : %i" % cbpx_listener.conn_q.qsize()
        print " Total relayed     : %i" % cbpx_listener.c_all_conns
        print " Total dequeued    : %i" % cbpx_flusher.c_all_conns
        l.debug("Trying to sleep in stats loop")
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
def cmd_queue(args):
    l.debug("Processing command")
    print " Now queuing connections"
    lock_connection.acquire()
    cbpx_listener.is_switch = 2
    lock_connection.release()
    l.info("Queuing started")

# ------------------------------------------------------------------------
def cmd_dequeue(args):
    l.debug("Processing command")
    print " Now dequeuing connections"
    lock_connection.acquire()
    cbpx_listener.is_switch = 0
    lock_connection.release()
    do_flush.set()
    l.info("Queuing stopped")

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
    'queue': [cmd_queue, "Start queuing connections (for test purposes only)"],
    'dequeue': [cmd_dequeue, "Start dequeuing connections (for test purposes only)"],
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
