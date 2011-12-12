import sys
import time
import logging
from socket import *
from threading import Thread, Event, Lock
from Queue import *
from utils import params

l = logging.getLogger('network')
l.setLevel(logging.INFO)

lock_connection = Lock()

do_flush = Event()

# ------------------------------------------------------------------------
class cbpx_transporter(Thread):

    c_transporters = 0

    # --------------------------------------------------------------------
    def __init__(self, sock_from, sock_to):
        Thread.__init__(self)
        l.debug("New transporter")
        self.sock_from = sock_from
        self.sock_to = sock_to

        cbpx_transporter.c_transporters += 1

    # --------------------------------------------------------------------
    def run(self):
        l.debug("Running transporter loop")
        while 1:
            try:
                data = self.sock_from.recv(1024)
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
        except IOError as (errno, strerror):
            l.error("The other transporter shutdown failed: I/O error(%i): %s" % (errno, strerror))
        except Exception, e:
            l.error("The other transporter shutdown failed: %s" % str(e))

        lock_connection.acquire()
        cbpx_transporter.c_transporters -= 1
        # if no more connections
        if cbpx_transporter.c_transporters == 0:
            l.info("No more connections!")
            # if we were switching
            if cbpx_listener.is_switch:
                # change backend after "slave safe" sleep
                time.sleep(0.3)
                # only if real switch, '2' means queuing test
                if cbpx_listener.is_switch == 1:
                    l.info("Finalize switch!")
                    cbpx_listener.backend = 1
                # allow unqueued connections
                cbpx_listener.is_switch = 0
                # flush all connections from queue
                do_flush.set()
        lock_connection.release()

# ------------------------------------------------------------------------
class cbpx_listener(Thread):

    c_all_conns = 0
    is_switch = 0
    backend = 0
    backends = []
    conn_q = Queue()

    # --------------------------------------------------------------------
    def __init__(self, port, backends):
        Thread.__init__(self, name="Listener")
        l.info("Creating queue, size: %s " % str(params["max_conn"]))
        cbpx_listener.conn_q = Queue(int(params["max_conn"]))
        l.info("Initializing connector")
        cbpx_listener.backends = backends

        l.debug("Setting up listener socket")
        try:
            self.sock = socket(AF_INET, SOCK_STREAM)
            self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self.sock.bind(('', port))
            self.sock.listen(20)
        except Exception, e:
            l.error("Could not create listener: %s" % str(e))
    
    # --------------------------------------------------------------------
    def close(self):
        l.info("Shutting down listener")
        self.sock.shutdown(SHUT_RDWR)
        self.sock.close()
        l.info("Listener closed")

    # --------------------------------------------------------------------
    def buffer_connection(self, n_sock, n_addr):
        l.info("Buffering new connection from: %s" % str(n_addr))
        try:
            cbpx_listener.conn_q.put([n_sock, n_addr], False)
        except Full:
            l.warning("Queue full, aborting!")
            cbpx_listener.is_switch = 0
            do_flush.set()
            l.info("Processing unqueued connection")
            self.process_connection(n_sock, n_addr)

    # --------------------------------------------------------------------
    def process_connection(self, n_sock, n_addr):
        l.info("Processing new connection from: %s" % str(n_addr))

        cbpx_listener.c_all_conns += 1

        try:
            fwd_sock = socket(AF_INET, SOCK_STREAM)
            ip = cbpx_listener.backends[cbpx_listener.backend]["ip"]
            port = cbpx_listener.backends[cbpx_listener.backend]["port"]
            fwd_sock.connect((ip, port))
        except IOError as (errno, strerror):
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
        l.info("Running listener")
        while True:
            l.debug("Awaiting new connection")

            try:
                (n_sock, n_addr) = self.sock.accept()
            except IOError as (errno, strerror):
                if errno == 22:
                    l.debug("Looks like socket shutdown")
                    break
                l.error("Error accepting connection: I/O error(%i): %s" % (errno, strerror))
            except Exception, e:
                l.error("Error accepting connection: " + str(e))

            l.debug("New connection")

            lock_connection.acquire()
            if not cbpx_listener.is_switch:
                self.process_connection(n_sock, n_addr)
            else:
                self.buffer_connection(n_sock, n_addr)
            lock_connection.release()
        l.info("Exiting listener loop")


# ------------------------------------------------------------------------
class cbpx_flusher(Thread):

    c_all_conns = 0

    # --------------------------------------------------------------------
    def __init__(self):
        Thread.__init__(self, name="Flusher")
        l.info("Initializing flusher")
        self.quit = 0

    # --------------------------------------------------------------------
    def close(self):
        self.quit = 1

    # --------------------------------------------------------------------
    def process_connection(self, n_sock, n_addr):
        l.info("Processing queued connection from: %s" % str(n_addr))

        cbpx_flusher.c_all_conns += 1

        try:
            fwd_sock = socket(AF_INET, SOCK_STREAM)
            ip = cbpx_listener.backends[cbpx_listener.backend]["ip"]
            port = cbpx_listener.backends[cbpx_listener.backend]["port"]
            fwd_sock.connect((ip, port))
        except IOError as (errno, strerror):
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
        while not self.quit:
            l.info("Waiting for flush request")
            do_flush.wait()
            while True:
                try:
                    l.debug("Trying to get connection from queue...")
                    i = cbpx_listener.conn_q.get(True, 0.1)
                    l.info("Processing connection from queue: %s (%i left)" % (str(i[1]), cbpx_listener.conn_q.qsize()))
                    self.process_connection(i[0], i[1])
                except Empty:
                    l.info("Connection queue empty")
                    lock_connection.acquire()
                    if cbpx_listener.conn_q.empty():
                        l.info("Connection queue really empty, pausing flusher")
                        do_flush.clear()
                    lock_connection.release()
                    break
        l.debug("Exiting flusher loop")

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
