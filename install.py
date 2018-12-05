#! /usr/bin/env python3
#
#   Utility to install PATE Monitor
#
#   install.py - 2018, Jani Tammi <jasata@utu.fi>
#   0.1.0   2018-11-24  Initial version.
#   0.2.0   2018-11-27  Modified to set local timezone and to install
#                       uwsgi with pip3 (apt package refuses to coperate).
#
import os
import sys
import platform

# PEP 396 -- Module Version Numbers https://www.python.org/dev/peps/pep-0396/
__version__ = "0.2.0"
__author__  = "Jani Tammi <jasata@utu.fi>"
VERSION = __version__
HEADER  = """
=============================================================================
University of Turku, Department of Future Technologies
ForeSail-1 / PATE Monitor installation script
Version {}, 2018 {}
""".format(__version__, __author__)


# Group memberships
# 1st use is to just collect distinct groups and check they exist (exit if not)
#       This has some special steps: look into 'users' and collect all
#       to-be-created user groups and assume they "already exist".
# 2nd use is to assign the memberships (after solution specific user creation)
memberships = {
    "patemon"       : ("patemon", "dialout", "www-data"),
    "www-data"      : ("www-data", "patemon")
}


# user accounts needed by this solution
# tuple (username, uid, pwd, primary_grp, other_groups)
# if 'uid' is None, system assign the next UID.
# if 'pwd' is None, password is not created and login is disabled.
# If 'primary_grp' is None, a user group is created (like: pi.pi).
users = [
    ("patemon", None, "patemon", None, ["dialout"])
]


# Tuple (mode, owner, group)
initialfilesys = {
    "/srv"              : (0o775, "patemon", "patemon"),
    "/srv/nginx-root"   : (0o755, "www-data", "patemon"),
    "/srv/backend"      : (0o755, "patemon", "patemon")
}

# must also do pip3 install uwsgi
packages = [
    "nginx",
    "build-essential",
    "python3-dev",
    "python3-pip",
    "python3-flask",
    "git-all",
    "sqlite3"
]
# Persistently want the config files to be under /etc/uwsgi..
# Bad as it is to compile own packages, I cannot use this.
# "uwsgi",
# "uwsgi-plugin-python3",


#
# Repositories
#
#   Target directory is created (repo[0]), after which
#   'git' clones the online repository (repo[1]) into it.
#   Finally (if not None), a setup script is run (repo[2]).
#
repositories = [
    (
        "755 root.root /srv/pmdatabase",
        "https://github.com/jasata/pmdatabase",
        "setup.py"
    ),
    (
        "775 www-data.www-data /srv/nginx-root",
        "https://github.com/jasata/pmapi",
        "setup.py"
    ),
    (
        "775 patemon.patemon /srv/backend",
        "https://github.com/jasata/psud",
        "setup.py"
    )
]

class Config:
    logging_level = "DEBUG"


###############################################################################
#
# Requirements
#
print(HEADER)
try:
    #
    # Require Python 3.5 or greater
    #
    v = platform.python_version_tuple()
    if (int(v[0]) < 3) or (int(v[0]) > 2 and int(v[1]) < 5):
        raise ValueError(
            "Python version 3.5 or greater is required! " +
            "Current version is {}.{}.{}"
            .format(*v)
        )

    #
    # Must be Linux OS
    #
    if platform.system().lower() != "linux":
        raise ValueError("This script supports only Linux OS.")

    #
    # Must be run as root
    #
    if os.geteuid() != 0:
        raise ValueError("You need to have root privileges to run this script.")


except Exception as e:
    print("Requirement checking failed!")
    print(str(e))
    print("Exiting...")
    os._exit(-1)

###############################################################################
#
# Functions
#
###############################################################################

#
# Late imports so that these won't crash the script before checks
#
import pwd
import grp
import shutil
import logging
import argparse
import datetime
import subprocess

__moduleName = os.path.basename(os.path.splitext(__file__)[0])
__fileName   = os.path.basename(__file__)


def do_or_die(cmd: list):
    prc = subprocess.run(cmd.split(" "))
    if prc.returncode:
        print("Command '{}' failed!".format(cmd))
        os._exit(-1)


def get_group(group) -> grp.struct_group:
    """Returns the group ID or None if it does not exist."""
    try:
        if type(group) is str:
            group = grp.getgrnam(group)
        elif type(group) is int:
            group = grp.getgrgid(group)
        else:
            raise ValueError(
                "Invalid argument type {} ('{}')!".format(
                    type(group), group
                )
            )
    except KeyError:
        return None
    return group

def get_user(user) -> pwd.struct_passwd:
    """Returns the user ID or None if it does not exist."""
    try:
        if type(user) is str:
            user = pwd.getpwnam(user)
        elif type(user) is int:
            user = pwd.getpwuid(user)
        else:
            raise ValueError(
                "Invalid argument type {} ('{}')!".format(
                    type(user), user
                )
            )
    except KeyError:
        return None
    return user

def create_group(name, gid=None) -> grp.struct_group:
    """Creates a group and returns grp.struct_group for it."""
    # NOTE: use 'groupdel <name>' to remove
    # There are no known Python modules to handle this, so subprocesses...
    log = logging.getLogger(
        __fileName + ":" + \
        sys._getframe().f_code.co_name + "()"
    )
    if gid:
        cmd = ["groupadd", "--gid", str(gid), name]
    else:
        cmd = ["groupadd", name]
    log.debug("Running subprocess {}".format(" ".join(cmd)))
    # Let exceptions propagate up. Nothing we can do about them anyway.
    process = subprocess.run(cmd)
    log.debug("Subprocess returned: " + str(process))
    if process.returncode:
        raise ValueError("Subprocess groupadd returned with nonzero code!")
    return get_group(name)

def create_user(name, pwd, primarygrp, uid=None) -> pwd.struct_passwd:
    """Creates a user and returns pwd.struct_passwd for it. If primarygrp is None, user shall be created into its own group (like pi.pi, for example). NOTE: Debian Stretch 'useradd' has bug(s). For one, the default shell no longer gets set. We need to do this explictly after creation with 'usermod' command."""
    # NOTE: use 'userdel -r -f <name>' to remove
    # There are no known Python modules to handle this, so subprocesses...
    log = logging.getLogger(
        __fileName + ":" + \
        sys._getframe().f_code.co_name + "()"
    )
    # useradd --password $(openssl passwd -1 patemon) --uid 2000 --user-group --create-home patemon
    cmd = ["useradd"]
    if pwd:
        # Python 3.5 does not have 'capture_output' !!
        proc_openssl = subprocess.run(
            ["openssl", "passwd", "-1", pwd],
            stdout = subprocess.PIPE
        )
        if proc_openssl.returncode:
            raise ValueError("openssl returned error!")
        cmd = [*cmd, *["--password", proc_openssl.stdout.decode("utf-8")[:-1]]]
    if uid:
        cmd = [*cmd, *["--uid", str(uid)]]
    if primarygrp:
        cmd = [*cmd, *["--gid", str(primarygrp)]]
    else:
        cmd = [*cmd, *["--user-group"]]
    cmd = [*cmd, *["--create-home", name]]
    log.debug("Subprocess: '{}'".format(" ".join(cmd)))
    # Let exceptions propagate up. Nothing we can do about them anyway.
    proc_useradd = subprocess.run(cmd, stdout = subprocess.PIPE)
    log.debug("Subprocess returned: " + str(proc_useradd))
    if proc_useradd.returncode:
        raise ValueError(
            "Subprocess useradd returned with nonzero code!\n" + \
            proc_useradd.stdout.decode("utf-8")
        )
    # Buggy Debian Stretch 'useradd' needs you to set the shell explicitly
    proc_usermod = subprocess.run(
        ["usermod", "--shell", "/bin/bash", name]
    )
    if proc_useradd.returncode:
        raise ValueError(
            "Subprocess usermod returned with nonzero code!\n" + \
            proc_useradd.stdout.decode("utf-8")
        )
    return get_user(name)

def add2group(user, group):
    """Adds specified user to specified secondary group."""
    # usermod -a G 
    proc_usermod = subprocess.run(
        ["usermod", "-a", "-G", group, user]
    )
    if proc_usermod.returncode:
        raise ValueError("usermod returned non-zero!")

def display_all():
    """Print all configuration data."""
    # Display users from 'memberships'
    print("Group memberships:")
    for user, groups in memberships.items():
        print(user)
        for group in groups:
            print("    {:.<{w}} : ".format(group, w=20), end="", flush=True)
            print("OK" if user in get_group(group).gr_mem else "MISSING!")
    print("")
    # initialfilesys
    print("Filesystem statuses:")
    for path, values in initialfilesys.items():
        stats = os.stat(path)
        print("    {:.<{w}} : ".format(path, w=20), end="", flush=True)
        if stats.st_mode & 0o777 != values[0]:
            print("Permission mode NOT OK!")
            continue
        if stats.st_uid != get_user(values[1]).pw_uid:
            print("Incorrect owner!")
            continue
        if stats.st_gid != get_group(values[2]).gr_gid:
            print("Incorrect group!")
            continue
        print("OK")

class User:
    uid         = None
    pwd         = None
    grp         = None
    othergroups = None
    def __init__(self, name, uid=None, pwd=None, grp=None, othergroups=None):
        self.name = name
        self.uid = uid
        self.pwd = pwd
        self.grp = grp
        self.othergroups = othergroups
    @property
    def exits(self) -> bool:
        return get_user(self.name) is not None
    @property
    def struct_passwd(self):
        return get_user(self.name)
    def create(self):
        # 
        # Check that 'othergroups' exist
        for grp in self.othergroups:
            if not get_group(grp):
                raise ValueError("Cannot create user! Secondary group '{}' does not exist!".format(grp))
        create_user(
            self.name,
            self.pwd,
            primarygrp = self.grp,
            uid = self.uid
        )
        for grp in self.othergroups:
            proc_usermod = subprocess.run(
                ["usermod", "-a", "-G", grp, self.name]
            )
            if proc_usermod.returncode:
                raise ValueError("usermod returned non-zero!")
    def __str__(self):
        return "{} ({}) pwd: '{}', grp: '{}', other groups: '{}'".format(
            self.name, self.uid, self.pwd, self.grp, self.othergroups
        )

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

    #
    # Special feature - check and exit
    #
    if args.check:
        display_all()
        os._exit(0)


    #
    # ELSE, we install...
    #
    log.info(
        "{} version {}, {}".format(
            __fileName,
            __version__,
            datetime.datetime.now().isoformat())
    )


    # non-interactive timezone configuration
    # https://stackoverflow.com/questions/8671308/non-interactive-method-for-dpkg-reconfigure-tzdata
    # 1. Force-relink '/etc/localtime -> /usr/share/zoneinfo/Europe/Helsinki'
    # 2. Issue 'dpkg-reconfigure -f noninteractive tzdata'

    print("Setting Finnish localtime")
    do_or_die("ln -fs /usr/share/zoneinfo/Europe/Helsinki /etc/localtime")
    do_or_die("dpkg-reconfigure -f noninteractive tzdata")
    print("Done!")


    print("Updating system....")
    do_or_die("apt update")
    do_or_die("apt -y upgrade")
    print("System update done!\n")


    #
    # Check that necesary groups exist or will exist
    #
    # Generate list of "future groups" based on 'users'.
    # These are usernames that have primary group defined as None.
    # They will be created a new user group with identical name (pi.pi).
    print("Checking for needed groups...", end="", flush=True)
    future_groups = []
    for user in users:
        if user[3] is None:
            future_groups.append(user[0])
    # Get existing groups and merge both into one list
    existing_groups = [g.gr_name for g in grp.getgrall()]
    all_groups = [*future_groups, *existing_groups]

    # Generate a list of needed groups
    needed = []
    for _, t in memberships.items():
        needed = [*needed, *[g for g in t if g not in needed]]

    # Check that needed exist or will exist
    missing = [group for group in needed if group not in all_groups]
    if missing:
        log.error("Missing necessary group(s): {}".format(",".join(missing)))
        print("Missing necessary group(s): {}".format(",".join(missing)))
        os._exit(-1)
    print("OK!\n")


    #
    # Create solution specific user accounts
    #
    print("Creating PATE Monitor specific user accounts...")
    try:
        for usertuple in users:
            user = User(*usertuple)
            if not user.exits:
                print(
                    "User '{}' does not exist. Creating...".format(
                        user.name
                    ),
                    end="",
                    flush=True
                )
                user.create()
                print("OK!")

            # print(str(user.struct_passwd))
            # print("exits" if user.exits else "does not exist")
    except Exception as e:
        log.exception("User account creation failed!")
        print("User account creation failed!")
        print(str(e))
        os._exit(-1)
    print("")


    #
    # Assign group memberships
    #
    print("Assigning group memberships...")
    for user, groups in memberships.items():
        for group in groups:
            print(
                "    Adding user '{}' to group '{}'...".format(
                    user, group
                ),
                end="",
                flush=True
            )
            add2group(user, group)
            print("Done!")
    print("")


    #
    # Filesystem setup
    #
    print(
        "Setting up initial filesystem ownerships and permissions...",
        end="", flush=True
    )
    for path, values in initialfilesys.items():
        if not os.path.exists(path):
            os.makedirs(path)
        elif not os.path.isdir(path):
            print("ERROR! '{}' exists and is not a directory!".format(path))
            os._exit(-1)
        shutil.chown(path, values[1], values[2])
        os.chmod(path, values[0])
    print("OK!")



    #
    # Install packages
    #
    print("Begin APT package installations...")
    do_or_die("apt -y install " + " ".join(packages))
    # proc_apt = subprocess.run(
    #     ["apt", "-y", "install", *packages]
    # )
    # if proc_apt.returncode:
    #     print("apt install returned with non-zero!")
    #     os._exit(-1)
    print("APT package installations completed\n")


    #
    # Pip install(s)
    #
    print("pip3 install uwsgi...")
    do_or_die("pip3 install uwsgi")


    #
    # Clone repositories
    #
    print("Using git to clone repositories...")
    for repo in repositories:
        # Create and change to target directory
        if not os.path.exists(repo[0]):
            os.makedirs(repo[0])
        elif not os.path.isdir(repo[0]):
            print("ERROR! '{}' exists and is not a directory!".format(repo[0]))
            os._exit(-1)
        os.chdir(repo[0])
        # Run git clone
        do_or_die("git clone --recurse-submodules " + repo[1] + " .")
        # proc_git = subprocess.run(
        #     ["git", "clone", "--recurse-submodules", repo[1], "."]
        # )
        # if proc_git.returncode:
        #     print("git clone returned with error code! Exiting...")
        #     os._exit(-1)

        # Run post-clone script, if any
        if repo[3]:
            do_or_die("python3 " + repo[3])
            # proc_script = subprocess.run(
            #     ["python3", repo[3]]
            # )
            # if proc_script.returncode:
            #     print("Post clone installation script returned with error!")
            #     os._exit(-1)
        # Change permissions
        # subprocess.run() "setup_ownership_and_permission.py" if exists
        # No... let "setup.py" in each repo do that...
    print("All repositories cloned!")


# EOF