import optparse

__version__ = "0.1.3"

# ------------------------------------------------------------------------
class my_params:

    settable = ['max_time', 'switch_delay', 'switch_loop_wait']

    # network:
    port = ''
    active = ''
    standby = ''
    active_ip = ''
    active_port = ''
    standby_ip = ''
    standby_port = ''
    listen_backlog = '512'
    net_buffer_size = '2048'

    # switch:
    max_conn = ''
    max_time = ''
    switch_delay = '0.3'
    switch_loop_wait = '0.1'

    # logging
    log_file = 'cbpx.log'
    log_level = 'INFO'

params = my_params()

# ------------------------------------------------------------------------
def print_logo():
    print """        __                  
 .----.|  |--..-----..--.--.
 |  __||  _  ||  _  ||_   _|
 |____||_____||   __||__.__| %s : connection buffering proxy
------------- |__| -----------------------------------------------
""" % __version__

# ------------------------------------------------------------------------
def print_cfg():
    print " Listening on      : %i" % params.port
    print " Active backend    : %s:%i" % (params.active_ip, params.active_port)
    print " Standby backend   : %s:%i" % (params.standby_ip, params.standby_port)
    print " Timeout           : %2.2f s"  % float(params.max_time)
    print " Max connections   : %i" % int(params.max_conn)
    print " listen() backlog  : %i" % int(params.listen_backlog)
    print " Network buffer    : %i bytes" % int(params.net_buffer_size)
    print " Safe switch delay : %2.2f s" % float(params.switch_delay)
    print " Switch loop wait  : %2.2f s" % float(params.switch_loop_wait)
    print " Log file          : %s" % params.log_file
    print " Log level         : %s" % params.log_level
    print

# ------------------------------------------------------------------------
def parse_cmdline():
    parser = optparse.OptionParser(description='cbpx ' + __version__ + ' : connection buffering proxy', version="%prog " + __version__)
    parser.add_option('-p', '--port', help='port that proxy will listen on', type=int)
    parser.add_option('-a', '--active', help='IP:port pair of active backend (the one we switch from)')
    parser.add_option('-s', '--standby', help='IP:port pair of standby backend (the one we switch to)')
    parser.add_option('-t', '--max_time', help='timeout (in seconds) after which switchover fails')
    parser.add_option('-c', '--max_conn', help='queued connections limit, after which switchover fails')
    (params, args) = parser.parse_args(values=my_params)

    if not params.port:
        raise SyntaxError("-p PORT is required")
    if not params.active:
        raise SyntaxError("-a ACTIVE is required")
    if not params.standby:
        raise SyntaxError("-s STANDBY is required")
    if not params.max_time:
        raise SyntaxError("-t MAX_TIME is required")
    if not params.max_conn:
        raise SyntaxError("-c MAX_CONN is required")

    try:
        params.active_ip = params.active.split(":")[0]
        params.active_port = int(params.active.split(":")[1])
    except Exception, e:
        raise SyntaxError("wrong active IP:port: '%s' (%s)" % (params.active, str(e)))

    try:
        params.standby_ip = params.standby.split(":")[0]
        params.standby_port = int(params.standby.split(":")[1])
    except Exception, e:
        raise SyntaxError("wrong standby IP:port: '%s' (%s)" % (params.standby, str(e)))



# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
