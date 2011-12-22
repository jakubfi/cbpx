import optparse
import logging

l = logging.getLogger()

__version__ = "0.4.1"

# ------------------------------------------------------------------------
# class for storing configuration provided by optparse as well as our own stuff
class my_params:

    settable = {'switch_max_time':[float, 0, 10], 'max_queued_conns':[int, 10, 10000], 'max_open_conns':[int, 10, 65536], 'switch_delay':[float, 0, 1], 'switch_loop_wait':[float, 0.1, 1], 'net_buffer_size':[int, 1024, 65536]}

    # network:
    port = 0
    rc_port = 0
    active = ''
    standby = ''
    active_ip = ''
    active_port = ''
    backends = []
    standby_ip = ''
    standby_port = ''
    listen_backlog = '512'
    net_buffer_size = '2048'

    # switch:
    max_queued_conns = ''
    max_open_conns = ''
    switch_max_time = ''
    switch_delay = '0.3'
    switch_loop_wait = '0.1'

    # logging
    log_file = 'cbpx.log'
    log_level = 'INFO'
    log_format = '%(asctime)-15s %(levelname)-7s [%(threadName)-10s] (%(module)s::%(funcName)s) [L:%(lineno)d] %(message)s'
    log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']

params = my_params()

# ------------------------------------------------------------------------
def parse_cmdline():
    parser = optparse.OptionParser(description='cbpx ' + __version__ + ' : connection buffering proxy', version="%prog " + __version__)
    parser.add_option('-p', '--port', help='port that proxy will listen on', type=int)
    parser.add_option('-a', '--active', help='IP:port pair of active backend (the one we switch from)')
    parser.add_option('-s', '--standby', help='IP:port pair of standby backend (the one we switch to)')
    parser.add_option('-r', '--rc_port', help='port for remote control connections (RC disabled if not specified)', type=int)
    parser.add_option('-t', '--switch_max_time', help='timeout (in seconds) after which switchover fails')
    parser.add_option('-c', '--max_queued_conns', help='queued connections limit, after which switchover fails')
    parser.add_option('-o', '--max_open_conns', help='open connections limit (used for throttling, 0 disables this feature)')

    parser.add_option('-b', '--listen_backlog', help='backlog for listen()')
    parser.add_option('-n', '--net_buffer_size', help='network communication buffer size')
    parser.add_option('-d', '--switch_delay', help='delay between last connection and switch finish')
    parser.add_option('-w', '--switch_loop_wait', help='wait in switch loop')
    parser.add_option('-f', '--log_file', help='log file name')
    parser.add_option('-l', '--log_level', help='log level: %s' % str(my_params.log_levels))

    (params, args) = parser.parse_args(values=my_params)

    # check for required parameters
    if not params.port:
        raise SyntaxError("-p PORT is required")
    if not params.active:
        raise SyntaxError("-a ACTIVE is required")
    if not params.standby:
        raise SyntaxError("-s STANDBY is required")
    if not params.switch_max_time:
        raise SyntaxError("-t MAX_TIME is required")
    if not params.max_queued_conns:
        raise SyntaxError("-c MAX_QUEUED_CONNS is required")
    if not params.max_open_conns:
        raise SyntaxError("-o MAX_OPEN_CONNS is required")
    if params.log_level not in params.log_levels:
        raise SyntaxError("Log level must be one of: %s ('%s' is wrong)" % (str(params.log_levels), params.log_level))

    # get IP and PORT from what user provided
    try:
        params.active_ip = params.active.split(":")[0]
        params.active_port = int(params.active.split(":")[1])
    except Exception, e:
        raise SyntaxError("specify active backend as IP:PORT, not '%s'\nException: %s" % (params.active, str(e)))

    try:
        params.standby_ip = params.standby.split(":")[0]
        params.standby_port = int(params.standby.split(":")[1])
    except Exception, e:
        raise SyntaxError("specify standby backend as IP:PORT, not '%s'\nException: %s" % (params.standby, str(e)))

    params.backends = [(params.active_ip, params.active_port), (params.standby_ip, params.standby_port)]

# ------------------------------------------------------------------------
def setup_logging():
    logging.basicConfig(format=params.log_format, filename=params.log_file)
    l.setLevel(logging.__dict__["_levelNames"][params.log_level])



# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
