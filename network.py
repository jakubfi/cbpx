import os
import time
import logging
import select
import subprocess

from socket import *
from threading import Thread, Lock, Event
from Queue import *

from utils import params, l
from th import RelayGate
from stats import cbpx_stats

conn_q = Queue()
relay = RelayGate()
script = None

# --------------------------------------------------------------------
def kill_script():
    l.debug("Trying to kill switch finalize script (just in case)")
    global script
    try: script.kill()
    except: pass

# --------------------------------------------------------------------
def switch_finalize():

    if not params.switch_script:
        l.info("No switch finalize script to run, finishing switch immediately")
        relay.switch_backend("all connections closed")
        return

    try:
        global script

        devnull = open(os.devnull, "rw")

        (ai, ap) = relay.get_active()
        (si, sp) = relay.get_standby()

        l.info("Running script: '%s' with arguments: %s %i %s %i" % (params.switch_script, ai, ap, si, sp))

        script = subprocess.Popen([params.switch_script, ai, str(ap), si, str(sp)], stdin=devnull, stdout=devnull, stderr=devnull, close_fds=True, shell=False, cwd=None, env=None, universal_newlines=False, startupinfo=None, creationflags=0)
        r = script.wait()
    except Exception, e:
        l.error("Exception while executing switch finalize script (%s): %s" % (params.switch_script, str(e)))
        relay.set("script exec failed: %s" % str(e))
        return

    l.info("Script exit: %i" % r)
    if r is None:
        # shouldn't happen
        relay.set("unexpected script finish with no return code")
    if r < 0:
        # terminated
        relay.set("script terminated by signal: %i" % -r)
    elif r > 0:
        # exited with error
        relay.set("script exited with code: %i" % r)
    else:
        # switch is done, change backend
        relay.switch_backend("all connections closed, script returned: %i" % r)

    l.info("Switch finalize script done.")


# ------------------------------------------------------------------------
class cbpx_transporter(Thread):

    # --------------------------------------------------------------------
    def __init__(self):
        l.debug("New transporter")
        Thread.__init__(self, name="Transport")
        self.EPOLL_EVENTS = select.EPOLLIN | select.EPOLLPRI | select.EPOLLERR | select.EPOLLHUP | select.EPOLLRDBAND
        self.DATA_READY = select.EPOLLIN | select.EPOLLPRI | select.EPOLLRDBAND
        self.CONN_STATE = select.EPOLLERR | select.EPOLLHUP
        self.poller = select.epoll()
        self.fd = {}
        self.quit = False
        self.dead = set()
        self.conn_lock = Lock()

    # --------------------------------------------------------------------
    def close(self):
        l.debug("Closing transporter")
        self.quit = True

    # --------------------------------------------------------------------
    def add(self, backend, client):
        fd_backend = backend.fileno()
        fd_client = client.fileno()

        l.debug("Adding fd: %i %i" % (fd_backend, fd_client))

        self.conn_lock.acquire()

        self.fd[fd_backend] = [backend, client, fd_client]
        self.fd[fd_client] = [client, backend, fd_backend]

        self.poller.register(fd_client, self.EPOLL_EVENTS)
        self.poller.register(fd_backend, self.EPOLL_EVENTS)
        
        cbpx_stats.c_endpoints = len(self.fd)

        self.conn_lock.release()

    # --------------------------------------------------------------------
    def remove(self, f):
        self.conn_lock.acquire()

        sock = self.fd[f][0]

        l.debug("Removing fd: %i" % f)

        self.poller.unregister(f)
        del self.fd[f]
        try:
            sock.shutdown(SHUT_RDWR)
            sock.close()
        except:
            pass

        cbpx_stats.c_endpoints = len(self.fd)

        self.conn_lock.release()

    # --------------------------------------------------------------------
    def remove_dead(self):
        l.debug("Dead sockets to remove: %s" % str(self.dead))
        for f in set(self.dead):
            try: self.remove(f)
            except: pass
            self.dead.discard(f)

    # --------------------------------------------------------------------
    def kill_connections(self):
        for f in self.fd:
            try: self.remove(f)
            except: pass

    # --------------------------------------------------------------------
    def run(self):

        rd = []

        l.debug("Running transporter loop")
        while not self.quit:

            # wait for events on all tracked fds
            try:
                rd = self.poller.poll(0.2)
            except Exception, e:
                l.warning("Exception while poll(): %s" % str(e))

            # iterate over all events returned by epoll():
            for f, event in rd:

                # if wata is waiting to be read
                if event & self.DATA_READY:

                    # read the data
                    data = ""
                    try:
                        data = self.fd[f][0].recv(int(params.net_buffer_size))
                    except Exception, e:
                        l.warning("Exception %s while reading data: %s" % (type(e), str(e)))
                        self.dead.add(f)
                        self.dead.add(self.fd[f][2])
                        continue

                    # no data means connection closed
                    if not data:
                        self.dead.add(f)
                        self.dead.add(self.fd[f][2])
                        continue
                    else:
                        # pass the data to the other end
                        try:
                            self.fd[f][1].send(data)
                        except Exception, e:
                            l.warning("Exception %s while transmitting data: %s" % (type(e), str(e)))
                            self.dead.add(self.fd[f][2])
                            self.dead.add(f)
                            continue

                # if something different happened to an fd
                elif event & self.CONN_STATE:
                    l.warning("Erroneous event from poll(): %i" % event)
                    self.dead.add(f)
                else:
                    l.warning("Unhandled event from poll(): %i" % event)

            # remove connections
            self.remove_dead()

            # since we're removing connections only here, we may as well check for switch finale here
            if (cbpx_stats.c_endpoints == 0) and (not relay.isSet()):
                switch_finalize()
 

# ------------------------------------------------------------------------
class cbpx_listener(Thread):

    # --------------------------------------------------------------------
    def __init__(self, port):
        Thread.__init__(self, name="Listener")

        l.debug("Setting up listener (backlog: %i)" % int(params.listen_backlog))
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.sock.bind(('', port))
        self.sock.listen(int(params.listen_backlog))

    # --------------------------------------------------------------------
    def close(self):
        l.debug("Shutting down listener socket")
        self.sock.shutdown(SHUT_RDWR)
        self.sock.close()
        l.debug("Listener socket closed")

    # --------------------------------------------------------------------
    def run(self):
        l.debug("Running listener")
        while True:
            l.debug("Awaiting new connection")

            try:
                # wait for new connection
                (n_sock, n_addr) = self.sock.accept()
            except Exception, e:
                l.error("Error accepting connection: " + str(e))
                break

            l.debug("New connection from: %s" % str(n_addr))

            # if there are more queued connections than allowed
            qc = conn_q.qsize()
            if qc >= int(params.max_queued_conns):
                l.warning("Queued %i connections, limit is %i" % (qc, int(params.max_queued_conns)))
                # if we were switching, than sorry, but not anymore
                l.info("Enabling relaying")
                relay.set("connection limit reached")

            try:
                conn_q.put([n_sock, n_addr], False)
                cbpx_stats.c_qc += 1
                l.debug("Enqueued connection: %s" % str(n_addr))

            except Full:
                l.error("Queue is full with %i elements!" % qc)
                l.info("Enabling relaying")
                relay.set("connection queue full")

            except Exception, e:
                l.warning("Exception during connection enqueue: %s" % str(e))

        l.debug("Exiting listener loop")


# ------------------------------------------------------------------------
class cbpx_connector(Thread):

    quit = 0

    # --------------------------------------------------------------------
    def __init__(self, ai, ap, si, sp, transporter):
        Thread.__init__(self, name="Connector")
        l.debug("Initializing connector")
        self.transporter = transporter
        relay.set_backends(ai, ap, si, sp)
        relay.set("connector started")

    # --------------------------------------------------------------------
    def close(self):
        cbpx_connector.quit = 1

    # --------------------------------------------------------------------
    def process_connection(self, n_sock, n_addr):
        l.debug("Processing connection from: %s" % str(n_addr))

        try:
            fwd_sock = socket(AF_INET, SOCK_STREAM)
            fwd_sock.connect(relay.get_active())
        except IOError, (errno, strerror):
            l.error("Error extablishing connection to backend: I/O error(%i): %s" % (errno, strerror))
            n_sock.close()
            return
        except Exception, e:
            l.error("Exception while extablishing connection to backend: " + str(e))
            n_sock.close()
            return

        # spawn proxy threads
        try:
            self.transporter.add(fwd_sock, n_sock)
        except Exception, e:
            l.error("Error spawning connection threads: " + str(e))
            n_sock.close()


    # --------------------------------------------------------------------
    def throttle(self):
        active_conns = cbpx_stats.c_endpoints/2
        throttle_step = 0.01
        l.debug("Throttle?: %i connections (%i limit)" % (active_conns, int(params.max_open_conns)))
        while active_conns >= int(params.max_open_conns):
            time.sleep(throttle_step)
            active_conns = cbpx_stats.c_endpoints/2

    # --------------------------------------------------------------------
    def run(self):
        l.debug("Running connector")
        while not cbpx_connector.quit:
            l.debug("Waiting until relay event is set")
            relay.wait()
            l.debug("Trying to get connection from queue...")
            try:
                # throttle if throttling enabled
                if int(params.max_open_conns) > 0: self.throttle()
                i = conn_q.get(True, 1)
                cbpx_stats.c_dqc += 1
                l.debug("Dequeue connection: %s (%i in queue)" % (str(i[1]), conn_q.qsize()))
                self.process_connection(i[0], i[1])
                conn_q.task_done()
            except Empty:
                l.debug("Connection queue empty")
                if cbpx_connector.quit:
                    l.debug("Breaking connector loop on quit")
                    break
        l.debug("Exiting connector loop")


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
