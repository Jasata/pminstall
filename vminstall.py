#! /usr/bin/env python3
#
#   Utility to install vm.utu.fi development unit
#
#   mvinstall.py - 2019, Jani Tammi <jasata@utu.fi>
#   0.1.0   2019-12-16  Initial version.
#
#   MUST have Python 3.5+ (subprocess.run())
#
import os
import sys
import getpass
import logging
import platform
import argparse
import datetime
import subprocess

# PEP 396 -- Module Version Numbers https://www.python.org/dev/peps/pep-0396/
__version__ = "0.1.0"
__author__  = "Jani Tammi <jasata@utu.fi>"
VERSION = __version__
HEADER  = """
=============================================================================
University of Turku, Department of Future Technologies
Course Virtualization Project
Version {}, 2019 {}
""".format(__version__, __author__)


class Config:
    logging_level = "DEBUG"

class File:
    """As everything in this script, assumes superuser privileges."""
    name            = None      # full path and name
    owner           = None      # str 'user'
    group           = None      # str 'group'
    permissions     = None      # Octal; 0o644
    content         = None      # String, since we don't deal with binary
    def __init__(
        self,
        name: str,
        content: str,
        owner: str = None,
        group: str = None,
        permissions: int = 0o644
    ):
        owner = getpass.getuser() if not owner else owner
        group = grp.getgrgid(pwd.getpwnam(owner).pw_gid).gr_name if not group else group
        self.name           = name
        self._owner         = owner
        self._group         = group
        self.uid            = pwd.getpwnam(owner).pw_uid
        self.gid            = grp.getgrnam(group).gr_gid
        self.permissions    = permissions
        self.content        = content
    def create(self, overwrite = False):
        mode = "x" if not overwrite else "w+"
        with open(self.name, mode) as file:
            file.write(self.content)
        os.chmod(self.name, self.permissions)
        os.chown(self.name, self.uid, self.gid)
    def replace(self, key: str, value: str):
        self.content = self.content.replace(key, value)
    @property
    def owner(self) -> str:
        return self._owner
    @owner.setter
    def owner(self, name: str):
        self.uid            = pwd.getpwnam(name).pw_uid
        self._owner         = name
    @property
    def group(self) -> str:
        return self._group
    @group.setter
    def group(self, name: str):
        self.gid            = grp.getgrnam(name).gr_gid
        self._group         = name

packages = [
    "nginx",
    "build-essential",
    "python3-dev",
    "python3-pip",
    "python3-flask",
    "git",
    "sqlite3",
    "uwsgi",
    "uwsgi-plugin-python3"
]
# DUBIOUS:
#  libffi-dev
#  python3-setuptools
#  libssl-dev

files = {}

files['nginx.site'] = File(
    '/etc/nginx/sites-available/vm.utu.fi',
    """
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root /var/www/vm.utu.fi;
    server_name _;
 
    location / {
        include uwsgi_params;
        uwsgi_pass unix:/run/uwsgi/app/vm.utu.fi/vm.utu.fi.socket;
    }
}
"""
)

files['uwsgi.ini'] = File(
    '/etc/uwsgi/apps-available/vm.utu.fi.ini',
    """
[uwsgi]
plugins = python3
module = application
callable = app
# Execute in directory...
chdir = /var/www/vm.utu.fi/

# Execution parameters
master = true
processes = 1
threads = 4

# Logging (cmdline logging directive overrides this, unfortunately)
logto=/var/log/uwsgi/uwsgi.log

# Credentials that will execute Flask
uid = www-data
gid = www-data

# Since these components are operating on the same computer,
# a Unix socket is preferred because it is more secure and faster.
socket = /run/uwsgi/app/vm.utu.fi/vm.utu.fi.socket
chmod-socket = 664

# Clean up the socket when the process stops
vacuum = true

# This is needed because the Upstart init system and uWSGI have
# different ideas on what different process signals should mean.
# Setting this aligns the two system components, implementing
# the expected behavior:
die-on-term = true
"""
)

files['flask.conf'] = File(
    '/var/www/vm.utu.fi/instance/application.conf',
    """
# -*- coding: utf-8 -*-
#
# Turku University (2019) Department of Future Technologies
# Website for Course Virtualization Project
# Flask application configuration
#
# application.conf - Jani Tammi <jasata@utu.fi>
#
#   0.1.0   2019.12.07  Initial version.
#
#
# See http://flask.pocoo.org/docs/0.12/config/ for built-in config values.
#
#
import os
import logging

DEBUG                    = True
SESSION_COOKIE_NAME      = 'session'
SECRET_KEY               = {{secret_key}}
EXPLAIN_TEMPLATE_LOADING = True
TOP_LEVEL_DIR            = os.path.abspath(os.curdir)
BASEDIR                  = os.path.abspath(os.path.dirname(__file__))


#
# Command table configuration (seconds)
#
COMMAND_TIMEOUT         = 0.5
COMMAND_POLL_INTERVAL   = 0.2


#
# Flask app logging
#
LOG_FILENAME             = 'application.log'
LOG_LEVEL                = 'DEBUG'      # DEBUG, INFO, WARNING, ERROR, CRITICAL


#
# SQLite3 configuration
#
SQLITE3_DATABASE_FILE   = 'application.sqlite3'


#
# Flask email
#


#
# File upload
#
UPLOAD_FOLDER           = '/var/www/vm.utu.fi/upload/unprocessed'
ALLOWED_EXTENSIONS      = ['ova', 'img', 'zip', 'jpg', 'png']  # Use lowercase!

# EOF

""",
    'pi', 'www-data'
)

###############################################################################
# FUNCTIONS ETC

class Identity():
    def __init__(self, user: str, group: str = None):
        self.uid = pwd.getpwnam(user).pw_uid
        if not group:
            self.gid = pwd.getpwnam(user).pw_gid
        else:
            self.gid = grp.getgrnam(group).gr_gid
    def __enter__(self):
        self.original_uid = os.getuid()
        self.original_gid = os.getgid()
        os.setegid(self.uid)
        os.seteuid(self.gid)
    def __exit__(self, type, value, traceback):
        os.seteuid(self.original_uid)
        os.setegid(self.original_gid)



def do_or_die(cmd: str):
    prc = subprocess.run(
        cmd.split(" "),
        stdout = subprocess.DEVNULL,
        stderr = subprocess.DEVNULL
    )
    if prc.returncode:
        log.error("Command '{}' failed!".format(cmd))
        raise ValueError("{} from: {}".format(prc.returncode, cmd))
        #os._exit(-1)


def localize_timezone():
    do_or_die("ln -fs /usr/share/zoneinfo/Europe/Helsinki /etc/localtime")
    do_or_die("dpkg-reconfigure -f noninteractive tzdata")



def localize_keymap(model = "pc105", layout = "fi", variant = "", options = ""):
    """This routine is 'borrowed' from raspi-config."""
    keyboard_config_file = "# KEYBOARD CONFIGURATION FILE\n\n" + \
        "# Consult the keyboard(5) manual page.\n\n" + \
        "XKBMODEL=\"{}\"\nXKBLAYOUT=\"{}\"\n".format(model, layout) + \
        "XKBVARIANT=\"{}\"\nXKBOPTIONS=\"{}\"\n\n".format(variant, options) + \
        "BACKSPACE=\"guess\""
    with open("/etc/default/keyboard", 'w') as kfile:
        kfile.write(keyboard_config_file)
    # Apply changes
    do_or_die('dpkg-reconfigure -f noninteractive keyboard-configuration')
    do_or_die('invoke-rc.d keyboard-setup start')
    do_or_die("setupcon -k --force")
    do_or_die("udevadm trigger --subsystem-match=input --action=change")





###############################################################################
#
# MAIN
#
###############################################################################

if __name__ == '__main__':

    #
    # Commandline arguments
    #
    parser = argparse.ArgumentParser(
        description     = HEADER,
        formatter_class = argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-l',
        '--log',
        help    = "Set logging level. Default: '{}'".format(Config.logging_level),
        choices = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        nargs   = '?',
        dest    = "logging_level",
        const   = "INFO",
        default = Config.logging_level,
        type    = str.upper,
        metavar = "LEVEL"
    )
    parser.add_argument(
        '--check',
        help = 'Check installation.',
        action = 'store_true'
    )
    args = parser.parse_args()
    Config.logging_level = getattr(logging, args.logging_level)


    #
    # Set up logging
    #
    logging.basicConfig(
        level       = Config.logging_level,
        filename    = "install.log",
        format      = "%(asctime)s.%(msecs)03d %(levelname)s: %(message)s",
        datefmt     = "%H:%M:%S"
    )
    log = logging.getLogger()
    log.addHandler(logging.StreamHandler(sys.stdout))
    #logger.setLevel(logging.DEBUG)
    log.setLevel(getattr(logging, args.logging_level))


    try:
        #
        # BASIC
        #
        log.info("Setting Finnish localtime")
        localize_timezone()

        log.info("Setting Finnish keymap")
        localize_keymap()

        log.info("Updating system packages....")
        do_or_die("apt update")
        do_or_die("apt -y upgrade")
        log.info("System update done!")


        #
        # Install system packages
        #
        log.info("Installing software packages")
        do_or_die("apt -y install " + " ".join(packages))
        log.info("Package installations complete!")


        #
        # Add user 'www-data' to group 'pi'
        #
        log.info("Adding user 'www-data' to group 'pi'")
        do_or_die("usermod -a -G pi www-data")


        #
        # Create /var/wwww/vm.utu.fi
        #
        log.info("Creating /var/www/vm.utu.fi")
        do_or_die("mkdir /var/www/vm.utu.fi")
        do_or_die("chown pi.pi /var/www/vm.utu.fi")


        #
        # Create Virtual Host into Nginx
        #
        log.info("Creating virtual host into Nginx")
        files['nginx.site'].create()
        #with open("/etc/nginx/sites-available/vm.utu.fi", "w") as f:
        #    f.write(ngimx_vhost)
        do_or_die("ln -s /etc/nginx/sites-available/vm.utu.fi /etc/nginx/sites-enabled/vm.utu.fi")


        #
        # Configure uswgi
        #
        log.info("Creating uWSGI application config")
        files['uwsgi.ini'].create()
        #with open("/etc/uwsgi/apps-available/vm.utu.fi.ini", "w") as f:
        #    f.write(uwsgi_app)
        do_or_die("ln -s /etc/uwsgi/apps-available/vm.utu.fi.ini /etc/uwsgi/apps-enabled/vm.utu.fi.ini")


        #
        # TODO: use git@github.com/jasata/utu-vm-site.git
        #       ..but that requires a key (or perhaps )
        #
        with Identity('pi'):
            do_or_die("git clone https://github.com/jasata/utu-vm-site /var/www/vm.utu.fi")


        #
        # Create instance/application.conf
        #
        files['Flask.conf'].replace('{{secret_key}}', str(os.urandom(24))
        files['Flask.conf'].create()


        #
        # Create application.sqlite3
        #
        pass


        #
        # Only now can the nginx and uwsgi services be restarted
        #
        do_or_die("systemctl restart uwsgi")
        do_or_die("systemctl restart nginx")


    except Exception as e:
        log.exception(e)
        log.error("Install script FAILED!!")


# EOF
