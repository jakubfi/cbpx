import sys
import time
import logging
from socket import *
from threading import Thread, Event, Lock
from Queue import *
from utils import params

l = logging.getLogger('network')
l.setLevel(logging.__dict__["_levelNames"][params.log_level])

conn_q = Queue()

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

# ------------------------------------------------------------------------
class cbpx_transporter(Thread):

    c_transporters = 0
    lock_c_transporters = Lock()
    c_opened_conns = 0
    c_closed_conns = 0

    # --------------------------------------------------------------------
    def __init__(self, sock_from, sock_to):
        Thread.__init__(self)
        l.debug("New transporter")
        self.sock_from = sock_from
        self.sock_to = sock_to

        cbpx_transporter.lock_c_transporters.acquire()
        cbpx_transporter.c_transporters += 1
        cbpx_transporter.c_opened_conns += 1
        cbpx_transporter.lock_c_transporters.release()

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

        cbpx_transporter.lock_c_transporters.acquire()
        cbpx_transporter.c_transporters -= 1
        cbpx_transporter.c_closed_conns += 1
        cbpx_transporter.lock_c_transporters.release()

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
        l.info("Shutting down listener")
        self.sock.shutdown(SHUT_RDWR)
        self.sock.close()
        l.info("Listener closed")

    # --------------------------------------------------------------------
    def run(self):
        l.info("Running listener")
        while True:
            l.debug("Awaiting new connection")

            try:
                (n_sock, n_addr) = self.sock.accept()
            except Exception, e:
                l.error("Error accepting connection: " + str(e))
		break

            l.info("New connection from: %s" % str(n_addr))
            try:
                conn_q.put([n_sock, n_addr], False)
                cbpx_listener.c_queued_conns += 1
            except Full:
                l.warning("Queue full!")
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
    def __init__(self, backends, name):
        Thread.__init__(self, name=name)
        l.info("Initializing connector")
        cbpx_connector.backends = backends

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
    def run(self):
        l.info("Running connector")
        while True:
            l.debug("Trying to get connection from queue...")
            try:
                i = conn_q.get(True, 1)
                cbpx_connector.c_dequeued_conns += 1
                l.info("Dequeue connection: %s (%i in queue)" % (str(i[1]), conn_q.qsize()))
                self.process_connection(i[0], i[1])
                conn_q.task_done()
            except Empty:
                l.debug("Connection queue empty")
                if cbpx_connector.quit:
                    l.info("Breaking connector loop on quit")
                    break
        l.debug("Exiting connector loop")


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
