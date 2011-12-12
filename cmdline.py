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

# ------------------------------------------------------------------------
def cmd_stats(args):
    l.debug("Processing command")

    e = threading.Event()
    cnt = 0
    while True:
        e.clear()
        if not cnt % 50:
            print "Current backend       active in queue enqueued dequeued"
            print "--------------------- ------ -------- -------- --------"
        print "%-21s %6i %8i %8i %8i" % (cbpx_connector.backends[cbpx_connector.backend]["ip"] + str(cbpx_connector.backends[cbpx_connector.backend]["port"]), cbpx_transporter.c_transporters, conn_q.qsize(), cbpx_listener.c_queued_conns, cbpx_connector.c_dequeued_conns)
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
def cmd_queue(args):
    l.debug("Processing command")

# ------------------------------------------------------------------------
def cmd_dequeue(args):
    l.debug("Processing command")

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
