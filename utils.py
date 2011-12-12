import argparse

__version__ = "0.1"

params = {}

# ------------------------------------------------------------------------
def print_logo():
    print """        __                  
 .----.|  |--..-----..--.--.
 |  __||  _  ||  _  ||_   _|
 |____||_____||   __||__.__| v%s : connection buffering proxy
------------- |__| ---------------------------------------------
""" % __version__

# ------------------------------------------------------------------------
def print_cfg(cfg):
    print " Listening on    : %i"    % cfg.port
    print " Active master   : %s:%i" % (cfg.active_ip, cfg.active_port)
    print " Standby master  : %s:%i" % (cfg.standby_ip, cfg.standby_port)
    print " Timeout         : %i s"  % params["max_time"]
    print " Max connections : %i"    % params["max_conn"]
    print

# ------------------------------------------------------------------------
def parse_cmdline():
    parser = argparse.ArgumentParser(description='cbpx v0.1a : connection buffering proxy')
    parser.add_argument('-p', '--port', help='port that proxy will listen on', type=int, required=True)
    parser.add_argument('-a', '--active', help='IP:port pair of active service (the one we switch from)', required=True)
    parser.add_argument('-s', '--standby', help='IP:port pair of standby service (the one we switch to)', required=True)
    parser.add_argument('-t', '--max_time', help='timeout (in seconds) after which switchover fails', type=int, required=True)
    parser.add_argument('-c', '--max_conn', help='proxy connections limit, after which switchover fails', type=int, required=True)
    args = parser.parse_args()

    params["max_time"] = args.max_time
    params["max_conn"] = args.max_conn

    try:
        args.active_ip = args.active.split(":")[0]
        args.active_port = int(args.active.split(":")[1])
    except Exception, e:
        raise SyntaxError("wrong active IP:port")

    try:
        args.standby_ip = args.standby.split(":")[0]
        args.standby_port = int(args.standby.split(":")[1])
    except Exception, e:
        raise SyntaxError("wrong standby IP:port")
    return args

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
