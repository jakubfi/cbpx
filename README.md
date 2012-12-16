```
        __
 .----.|  |--..-----..--.--.
 |  __||  _  ||  _  ||_   _|
 |____||_____||   __||__.__|  connection buffering proxy
------------- |__| ----------------------------------------
```

Warning note
====================================

This is experimental software.
Make sure you know what you're doing before using it for anything else than testing it.

Description
====================================

cbpx allows you to switch application (clients) between two backends, but only when
all connections to previously active backend have been closed.

Requirements
====================================

* Python >=2.6 <3.0

Command line options
====================================

* -p PORT, --port=PORT : port that proxy will listen on
* -a ACTIVE, --active=ACTIVE : IP:port pair of active backend (the one we switch from)
* -s STANDBY, --standby=STANDBY : IP:port pair of standby backend (the one we switch to)
* -r RC_PORT, --rc_port=RC_PORT : port for remote control connections (remote control is disabled if not specified)
* -t SWITCH_MAX_TIME, --switch_max_time=SWITCH_MAX_TIME : timeout (in seconds) after which switchover fails
* -c MAX_QUEUED_CONNS, --max_queued_conns=MAX_QUEUED_CONNS : queued connections limit, after which switchover fails
* -o MAX_OPEN_CONNS, --max_open_conns=MAX_OPEN_CONNS : open connections limit (used for throttling, 0 disables this feature)
* -b LISTEN_BACKLOG, --listen_backlog=LISTEN_BACKLOG :  backlog for listen()
* -n NET_BUFFER_SIZE, --net_buffer_size=NET_BUFFER_SIZE : network communication buffer size
* -w SWITCH_LOOP_WAIT, --switch_loop_wait=SWITCH_LOOP_WAIT : wait in switch loop
* -f LOG_FILE, --log_file=LOG_FILE : log file name
* -l LOG_LEVEL, --log_level=LOG_LEVEL : log level: DEBUG, INFO, WARNING, ERROR
* -x SWITCH_SCRIPT, --switch_script=SWITCH_SCRIPT : script to execute before switch completion (optional)

Proxy Commands
====================================

* hello   : Server greeting (for checking proxy availability in remote control mode)
* help    : Print help 
* quit    : Quit proxy (use 'force' parameter to close all active and ignore queued connections)
* set     : Show/set variables (set PARAMETER VALUE) 
* stats   : Print current statistics (stats [SLEEP] [COUNT]) 
* switch  : Perform the switch
* threads : List alive threads

