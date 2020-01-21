# Simple script wrapping and keeping track of an application process and it's lifecycle.
# The script has two main purposes:
#   1. To ensure that the application is restarted if it ever stops/crashes.
#   2. To kill the program forcefully should it stop responsing, thus leading back to step 1 (restart).
#
# Use like:
#
#   pyrevive.py [process_path] [port]
#
# Where process_path is the name of the application or script to start, and port is the port number on which
# to send ping requests to check for liveness. Example:
#
#   pyrevive.py ./my_app 1337

import os
import sys
import time
import signal
import socket
import logging
import traceback
import subprocess

from pathlib import Path

# Configure logging to both stderr and file

logger = logging.getLogger('watcher')

log_directory = str(Path.home()) + '/.pyrevive/log/'
os.makedirs(log_directory, exist_ok=True)

file_log_handler = logging.FileHandler(log_directory + 'pyrevive.log')
stderr_log_handler = logging.StreamHandler()

logger.addHandler(stderr_log_handler)
logger.addHandler(file_log_handler)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_log_handler.setFormatter(formatter)
stderr_log_handler.setFormatter(formatter)
logger.setLevel('INFO')

# Globals

COMMAND = "server"
PORT = "1337"
HOST = "127.0.0.1"

sub_process = None
was_killed = False

def start_process(proc_path):
    global sub_process
    global was_killed

    if was_killed:
        logger.info('%s was killed - attempting to revive', COMMAND)
        was_killed = False

    sub_process = subprocess.Popen(proc_path.split())

    if sub_process:
        logger.info('Started %s with PID %s', COMMAND, sub_process.pid)
    else:
        logger.error('Failed to start %s.. attempting again in a few seconds', COMMAND)

    return sub_process

def kill_process():
    global sub_process
    global was_killed
    if sub_process:
        os.kill(sub_process.pid, signal.SIGKILL)
        logger.info('Killed %s (PID %s)', COMMAND, sub_process.pid)
        was_killed = True
    else:
        logger.error('Could not kill %s as the sub_process is somehow lost', COMMAND)

def main(argv):
    error_counter = 0

    logger.info("Watcher process main() starting up!")
    port = PORT if len(argv) != 2 else argv[1]
    command = COMMAND + port
    logger.info(command)

    message = "ping\n"

    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((HOST, int(port)))
            sock.settimeout(5.0)
            sock.sendall(message.encode())
            if sock.recv(2).decode() == 'OK':
                if error_counter > 0:
                    logger.info('Connected to process - resetting error counter from %s to 0', error_counter)
                    error_counter = 0
            else:
                raise socket.timeout('Response missing or malformed')

        except (BrokenPipeError, ConnectionRefusedError):
            logger.info('Broken pipe or connection refused, assuming process is dead - trying to launch in 5 seconds')
            time.sleep(5)
            start_process(command)
        except socket.timeout:
            error_counter += 1
            logger.warning('Socket timeout - incrementing error counter to %s', error_counter)
        except Exception as ex:
            logging.error('Unknown exception %s', str(ex))
            logging.error(traceback.format_exc())
            time.sleep(5)
            start_process(command)
        finally:
            if error_counter > 3:
                logger.error('Error counter reached above 3 attempts - killing process!')
                kill_process()
                error_counter = 0
            sock.close()

        # Rinse and repeat
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            # Don't show stacktrace on Ctrl+C
            sys.exit(0)

    logger.info('Closing up')

if __name__ == "__main__":
    main(sys.argv)
