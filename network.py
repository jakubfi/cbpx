import time
import logging
import select

from socket import *
from threading import Thread, Lock, Event
from Queue import *

from utils import params, l
from th import DescEvent
from stats import cbpx_stats


conn_q = Queue()
relay = DescEvent()
switch_finish = Lock()

# --------------------------------------------------------------------
def check_if_no_connections():
    if cbpx_stats.c_transporters == 0:
        l.debug("No more connections")
        # stopped relaying means we're switching backends
        if not relay.isSet():
            l.info("We were switching, so switch is done.")
            # change backend first
            cbpx_connector.backend = int(not cbpx_connector.backend)
            l.info("Sleeping %2.2f before finishing switch" % float(params.switch_delay))
            time.sleep(float(params.switch_delay))
            # let the connections be established
            relay.set("all connections closed")

# ------------------------------------------------------------------------
class cbpx_transporter(Thread):

    # --------------------------------------------------------------------
    def __init__(self):
        Thread.__init__(self, name="Transport")
        l.debug("New transporter")
        self.READ_ONLY = select.POLLIN | select.POLLPRI | select.POLLERR | select.POLLHUP | select.POLLNVAL
        self.poller = select.poll()
        self.fd = {}
        self.quit = False
        self.tracked = 0

    # --------------------------------------------------------------------
    def close(self):
        l.debug("Closing transporter")
        self.quit = True

    # --------------------------------------------------------------------
    def add(self, backend, client):
        self.poller.register(backend, self.READ_ONLY)
        self.poller.register(client, self.READ_ONLY)
        fd_backend = backend.fileno()
        fd_client = client.fileno()
        l.debug("Adding fd: %i %i" % (fd_backend, fd_client))
        self.fd[fd_backend] = [backend, client, fd_client]
        self.fd[fd_client] = [client, backend, fd_backend]
        self.tracked += 2
        cbpx_stats.c_transporters += 2
        l.debug("Sockets registered: %i" % self.tracked)

    # --------------------------------------------------------------------
    def remove(self, f):
        l.debug("Removing fd: %i" % f)
        try:
            self.poller.unregister(f)
            self.fd[f][0].shutdown(SHUT_RDWR)
            self.fd[f][0].close()
            del self.fd[f]
        except:
            pass
        self.tracked -= 1
        cbpx_stats.c_transporters -= 1
        l.debug("Sockets registered: %i" % self.tracked)
 
    # --------------------------------------------------------------------
    def run(self):
        l.info("Running transporter loop")
        while not self.quit:
            try:
                rd = self.poller.poll(10)
            except Exception, e:
                l.warning("Exception while poll(): %s" % str(e))
                break
            if not rd:
                continue

            for f, event in rd:
                if event & (select.POLLIN | select.POLLPRI):

                    data = ""
                    try:
                        data = self.fd[f][0].recv(int(params.net_buffer_size))
                    except Exception, e:
                        l.warning("Exception %s while reading data: %s" % (type(e), str(e)))
                        self.remove(f)
                        self.remove(self.fd[f][2])
                        continue

                    if not data:
                        self.remove(f)
                        continue
                    else:
                        try:
                            self.fd[f][1].send(data)
                        except Exception, e:
                            l.warning("Exception %s while transmitting data: %s" % (type(e), str(e)))
                            self.remove(self.fd[f][2])
                            self.remove(f)
                            continue

                elif event & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
                    self.remove(f)
                else:
                    l.warning("Unhandled event from poll(): %i" % event)
                    
                    


# ------------------------------------------------------------------------
class cbpx_listener(Thread):

    # --------------------------------------------------------------------
    def __init__(self, port):
        Thread.__init__(self, name="Listener")

        l.info("Setting up listener (backlog: %i)" % int(params.listen_backlog))
        try:
            self.sock = socket(AF_INET, SOCK_STREAM)
            self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self.sock.bind(('', port))
            self.sock.listen(int(params.listen_backlog))
        except Exception, e:
            l.error("Could not create listener: %s" % str(e))
            raise IOError("Could not create listener: %s" % str(e))

    # --------------------------------------------------------------------
    def close(self):
        l.info("Shutting down listener socket")
        self.sock.shutdown(SHUT_RDWR)
        self.sock.close()
        l.debug("Listener socket closed")

    # --------------------------------------------------------------------
    def run(self):
        l.info("Running listener")
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
            if conn_q.qsize() >= int(params.max_queued_conns):
                l.warning("Queued %i connections, limit is %i" % (conn_q.qsize(), int(params.max_queued_conns)))
                switch_finish.acquire()
                # if we were switching, than sorry, but not anymore
                if not relay.isSet():
                    l.info("Enabling relaying")
                    relay.set("connection limit reached")
                switch_finish.release()

            try:
                conn_q.put([n_sock, n_addr], False)
                cbpx_stats.c_qc += 1
                l.debug("Enqueued connection: %s" % str(n_addr))

            except Full:
                l.error("Queue is full with %i elements!" % conn_q.qsize())
                switch_finish.acquire()
                if not relay.isSet():
                    l.info("Enabling relaying")
                    relay.set("connection queue full")
                switch_finish.release()

            except Exception, e:
                l.warning("Exception during connection enqueue: %s" % str(e))

        l.info("Exiting listener loop")


# ------------------------------------------------------------------------
class cbpx_connector(Thread):

    backends = []
    backend = 0
    quit = 0

    # --------------------------------------------------------------------
    def __init__(self, backends, transporter):
        Thread.__init__(self, name="Connector")
        l.info("Initializing connector")
        self.transporter = transporter
        cbpx_connector.backends = backends
        relay.set("connector started")

    # --------------------------------------------------------------------
    def close(self):
        cbpx_connector.quit = 1

    # --------------------------------------------------------------------
    def process_connection(self, n_sock, n_addr):
        l.debug("Processing connection from: %s" % str(n_addr))

        try:
            fwd_sock = socket(AF_INET, SOCK_STREAM)
            fwd_sock.connect(cbpx_connector.backends[cbpx_connector.backend])
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
        active_conns = cbpx_stats.c_transporters/2
        throttle_step = 0.01
        l.debug("Throttle?: %i connections (%i limit)" % (active_conns, int(params.max_open_conns)))
        while active_conns >= int(params.max_open_conns):
            time.sleep(throttle_step)
            active_conns = cbpx_stats.c_transporters/2

    # --------------------------------------------------------------------
    def run(self):
        l.info("Running connector")
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
                switch_finish.acquire()
                self.process_connection(i[0], i[1])
                switch_finish.release()
                conn_q.task_done()
            except Empty:
                l.debug("Connection queue empty")
                if cbpx_connector.quit:
                    l.info("Breaking connector loop on quit")
                    break
        l.info("Exiting connector loop")


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
