import time
import logging
from socket import *
from threading import Thread, Event, Lock
from Queue import *

from utils import params, l

conn_q = Queue()
relay = Event()
switch_finish = Lock()

# ------------------------------------------------------------------------
def test_connection(ip, port):
    test_sock = socket(AF_INET, SOCK_STREAM)
    test_sock.settimeout(1)

    try:
        test_sock.connect((ip, port))
    except Exception, e:
        test_sock.close()
        raise IOError("can't connect: %s" % str(e))
    try:
        data = test_sock.recv(int(params.net_buffer_size))
        sv = data[5:].split("\0")[0]
    except Exception, e:
        test_sock.close()
        raise IOError("didn't get server version: %s" % str(e))

    return sv

# --------------------------------------------------------------------
def check_if_no_connections():
    if cbpx_transporter.c_transporters == 0:
        l.debug("No more connections")
        # stopped relaying means we're switching backends
        if not relay.isSet():
            l.debug("We were switching, so switch is done.")
            # change backend first
            cbpx_connector.backend = int(not cbpx_connector.backend)
            l.debug("Sleeping %2.2f before finishing switch" % float(params.switch_delay))
            time.sleep(float(params.switch_delay))
            # let the connections be established
            relay.set()

# ------------------------------------------------------------------------
class cbpx_transporter(Thread):

    c_transporters = 0
    c_opened_conns = 0
    c_closed_conns = 0

    # --------------------------------------------------------------------
    def __init__(self, sock_from, sock_to):
        Thread.__init__(self)
        l.debug("New transporter")
        self.sock_from = sock_from
        self.sock_to = sock_to

        cbpx_transporter.c_transporters += 1
        cbpx_transporter.c_opened_conns += 1

    # --------------------------------------------------------------------
    def run(self):
        l.debug("Running transporter loop")
        while 1:
            try:
                data = self.sock_from.recv(int(params.net_buffer_size))
                if not data:
                    l.debug("Transporter endpoint closed")
                    break
                self.sock_to.send(data)
            except Exception, e:
                l.error("Exception in transporter loop: %s" % str(e))
                break

        l.debug("Exiting transporter loop")

        try:
            self.sock_to.shutdown(SHUT_RDWR)
        except IOError, (errno, strerror):
            l.error("The other transporter shutdown failed: I/O error(%i): %s" % (errno, strerror))
        except Exception, e:
            l.error("The other transporter shutdown failed: %s" % str(e))

        switch_finish.acquire()
        cbpx_transporter.c_transporters -= 1
        cbpx_transporter.c_closed_conns += 1
        check_if_no_connections()
        switch_finish.release()

# ------------------------------------------------------------------------
class cbpx_listener(Thread):

    c_queued_conns = 0

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
        l.info("Listener socket closed")

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

            l.info("New connection from: %s" % str(n_addr))

            # if there are more queued connections than allowed
            if conn_q.qsize() >= int(params.max_queued_conns):
                l.warning("Queued %i connections, limit is %i" % (conn_q.qsize(), int(params.max_queued_conns)))
                switch_finish.acquire()
                # if we were switching, than sorry, but not anymore
                if not relay.isSet():
                    l.info("Enabling relaying")
                    relay.set()
                switch_finish.release()

            try:
                conn_q.put([n_sock, n_addr], False)
                cbpx_listener.c_queued_conns += 1
                l.debug("Enqueued connection: %s" % str(n_addr))

            except Full:
                l.error("Queue is full with %i elements!" % conn_q.qsize())
                switch_finish.acquire()
                if not relay.isSet():
                    l.info("Enabling relaying")
                    relay.set()
                switch_finish.release()

            except Exception, e:
                l.warning("Exception during connection enqueue: %s" % str(e))

        l.info("Exiting listener loop")


# ------------------------------------------------------------------------
class cbpx_connector(Thread):

    c_dequeued_conns = 0
    backends = []
    backend = 0
    quit = 0

    # --------------------------------------------------------------------
    def __init__(self, backends):
        Thread.__init__(self, name="Connector")
        l.info("Initializing connector")
        cbpx_connector.backends = backends
        relay.set()

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
            cbpx_transporter(n_sock, fwd_sock).start()
            cbpx_transporter(fwd_sock, n_sock).start()
        except Exception, e:
            l.error("Error spawning connection threads: " + str(e))
            n_sock.close()


    # --------------------------------------------------------------------
    def throttle(self):
        active_conns = cbpx_transporter.c_transporters/2
        throttle_step = 0.01
        l.debug("Throttle?: %i connections (%i limit)" % (active_conns, int(params.max_open_conns)))
        while active_conns >= int(params.max_open_conns):
            time.sleep(throttle_step)
            active_conns = cbpx_transporter.c_transporters/2

    # --------------------------------------------------------------------
    def run(self):
        l.info("Running connector")
        while True:
            l.debug("Waiting until relay event is set")
            relay.wait()
            l.debug("Trying to get connection from queue...")
            try:
                # throttle if throttling enabled
                if int(params.max_open_conns) > 0: self.throttle()
                i = conn_q.get(True, 1)
                cbpx_connector.c_dequeued_conns += 1
                l.info("Dequeue connection: %s (%i in queue)" % (str(i[1]), conn_q.qsize()))
                switch_finish.acquire()
                self.process_connection(i[0], i[1])
                switch_finish.release()
                conn_q.task_done()
            except Empty:
                l.debug("Connection queue empty")
                if cbpx_connector.quit:
                    l.info("Breaking connector loop on quit")
                    break
        l.debug("Exiting connector loop")


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
