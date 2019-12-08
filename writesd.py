#! /usr/bin/env python3
#
#   Foresail Project // Turku University
#   Department of Future Technologies
#   Embedded Systems Laboratory
#
#   Script to write and prepare Rasbian image for PateMonitor.
#
#   writesd.py - 2018-2019, Jani Tammi <jasata@utu.fi>
#   0.2.0   2019-11-08  Brought up to date with the writesd-dell.py script.
#   0.3.0   2019-11-08  Instance mode commandline options. Other improvements.
#   0.3.1   2019-11-08  Add --device option for writing into a specified device
#   0.3.2   2019-11-11  Changed from 'Config.py'  to 'writesd.conf'.
#   0.3.3   2019-11-11  Add --ddns option to complement --noddns option.
#   0.3.4   2019-11-11  Fixed "Creating [MODE] instance" message.
#   0.3.5   2019-11-11  install.conf changed to install.config.
#   0.3.6   2019-11-25  DDNS created for non-DEV modes + purge /etc/hostname.
#   0.3.7   2019-11-25  DHCP hook to update DDNS on IP change.
#   0.3.8   2019-11-25  Moved DDNS related files into this script.
#   0.3.9   2019-11-25  Warning if DDNS client is requested but no credentials.
#   0.4.0   2019-11-25  Release version 0.4.0. Mainly a Github thing...
#   0.4.1   2019-11-26  Modified to Python 3.5 and python version check added.
#   0.4.2   2019-11-27  Disk device chooser, safe/unsafe information.
#   0.4.3   2019-11-27  Improved messages on disk unsafety.
#   0.4.4   2019-11-27  Add report to the end of the process.
#   0.4.5   2019-11-27  /boot changes now also within try...catch.
#   0.4.6   2019-11-29  Require root to run, improved help/messages.
#   0.4.7   2019-11-29  Handle CTRL-C in choose_* functions.
#   0.4.8   2019-11-29  DH Client Hook script fixed.
#   0.4.9   2019-12-08  Add .bashrc (git-prompt) customisation.
#   0.4.10  2019-12-08  Fixed root privilege check location & message.
#   0.5.0   2019-12-08  Add SSH key copying.
#
#
#   Commandline options:
#
#       -m, --mode      Specify mode for the instance
#       --device        Block device (disk) to write into
#       --noddns        Do not create DDNS client
#       --ddns          Create DDNS client
#
#
#   For home.net development:
#       ./writesd.py -m dev --noddns
#   For utu.fi development:
#       ./writesd.py -m dev --device /dev/sdb
#   For UAT or Release:
#       ./writesd.py -m prd
#
#   ...or define the default mode in 'writesd.config'
#
import os
import sys
import stat
import time
import argparse
import subprocess
import configparser

# Python 3.5 or newer
if sys.version_info < (3, 5):
    import platform
    print("You need Python 3.5 or newer! ", end = "")
    print(
        "You have Python ver.{} on {} {}".format(
            platform.python_version(),
            platform.system(),
            platform.release()
        )
    )
    print(
        "Are you sure you did not run 'python {}' instead of".format(
            os.path.basename(__file__)
        ),
        end = ""
    )
    print(
        "'python3 {}' or './{}'?".format(
            os.path.basename(__file__),
            os.path.basename(__file__)
        )
    )
    os._exit(1)


# PEP 396 -- Module Version Numbers https://www.python.org/dev/peps/pep-0396/
__version__ = "0.5.0"
__author__  = "Jani Tammi <jasata@utu.fi>"
VERSION = __version__
HEADER  = """
=============================================================================
University of Turku, Department of Future Technologies
ForeSail-1 / uSD writer for Rasbian based PATE Monitor
Version {}, 2018-2019 {}
""".format(__version__, __author__)


#
# GLOBAL Application Variables
#
class App:
    error           = None
    version         = __version__
    class Script:
        name        = os.path.basename(__file__)
        path        = os.path.dirname(os.path.realpath(__file__))
        config_file = os.path.splitext(__file__)[0] + ".config"
    class Mode:
        default     = "PRD"
        options     = ["DEV", "UAT", "PRD"]
        selected    = None      # Set in argparse step
    class DDNS:
        default_for = ["DEV", "UAT"]
        username    = None
        password    = None
        selected    = None
    class SSHKeys:
        selected    = True
    image           = None      # Rasbian image filename
    blkdev          = None      # Device file to write into
    summary         = ""        # Report of actions
    @staticmethod
    def report(msg: str):
        App.summary += "  - " + msg + "\n"


###############################################################################
#
# Various files that may be created
#

class File:
    name            = None      # Use real paths, let script prefix with "/mnt"
    permissions     = None
    content         = None
    def __init__(self, name, permissions, content):
        self.name = name
        self.permissions = permissions
        self.content = content


# Rasbian runs dhcpcd, thus hooks go into:
# /lib/dhcpcd/dhcpcd-hooks
# (NOT /etc/dhcp/dhclient-exit-hooks.d)
App.DDNS.dhclient_hook = File(
    "/lib/dhcpcd/dhcpcd-hooks/ddnsupdate",
    0o755,
    """#!/bin/bash
# Option '-i' for logger is useless because it will be the PID of the logger,
# not this script! (every line has higher PID....)
#
TAG="DH client hook"
NIC="eth0"
CMD="/usr/local/bin/dynudns.sh"

#logger -t "${TAG}" "dhclient hook activated! (if: ${interface}  reason: ${reason})"

# Disregard changes in other interfaces
if [ "$interface" != "$NIC" ]; then
        #logger -t "${TAG}" "Not my interface: '${interface}' != '${NIC}'"
        exit 0
fi

case "$reason" in
    BOUND|RENEW|REBIND|REBOOT)
        if ! [ -x "$(command -v ${CMD})" ]; then
            logger -t "${TAG}" "Command ${CMD} not found or not executable!"
            exit 1
        fi
        logger -t "${TAG}" "$interface: IP change, updating DDNS"
        (/bin/bash ${CMD}) || logger -t "${TAG}" "Command ${CMD} failed!"
        ;;
esac

# EOF
"""
)

App.DDNS.HTML_API_update = File(
    "/usr/local/bin/dynudns.sh",
    0x755,
    """#!/bin/bash
# 2019.11.07 // Jani Tammi
# Dynu DNS - Service for dynamic IP
#
#    IP Update Protocol
#    https://www.dynu.com/en-US/DynamicDNS/IP-Update-Protocol
#
#    Interface:
#    http://api.dynu.com/nic/update?myip=${}&username=${}&password=${}
#      myip            The IP you wish to store into the DDNS
#      username        The username you gave them when you creaed your account
#      password        A MD5 sum of the password string
#
#    Resposes
#      nochg           Sent IP was the same that was already stored in the DDNS
#      good {ip}       String "good" followed by the IP that was sent
#      (?)             Some response for authentication / other errors
#
username="{{user}}"
password="{{pass}}"
uri="http://api.dynu.com/nic/update"
passmd5="$(echo -n ${password} | md5sum - | awk '{print $1;}')"
ip="$(hostname -I | awk '{print $NF;exit}')"
uri="${uri}?myip=${ip}&username=${username}&password=${passmd5}"

if [ "${username}" == "" ]; then
    logger -t "DDNS" -i "DDNS credentials not set! Aborting..."
    exit 1
fi

# -s for silent
reply="$(curl -s ${uri})"

# log entry
logger -t "DDNS" -i "${uri} : ${reply}"

# EOF
"""
)

App.DDNS.cron_job = File(
    "/etc/cron.hourly/dynudns",
    0x755,
    """#!/bin/bash
#
# Execute DynuDSN script to update IP into the DDNS
#

/usr/local/bin/dynudns.sh
"""
)

App.DDNS.systemd_service = File(
    "/lib/systemd/system/dynudns.service",
    0o644,
    """[Unit]
Description=DynuDNS, free dynamic IP service.
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/bin/bash /usr/local/bin/dynudns.sh

[Install]
WantedBy=multi-user.target
"""
)




##############################################################################
#
# Read <script>.config into App class
#
def read_config(config_file: str):
    """Reads the specified config file and updates App configuration."""
    cfg = configparser.ConfigParser()
    if file_exists(config_file):
        try:
            cfg.read(config_file)
        except Exception as e:
            print(e)
            os._exit(-1)
    else:
        print(
            "Notification: Configuration file '{}' does not exist.".format(
                os.path.basename(config_file)
            )
        )
        return
    #
    # Section "Mode"
    #
    try:
        section = cfg["Mode"]
        val = section.get("default", App.Mode.default)
        if val in App.Mode.options:
            App.Mode.default = val
        else:
            print(
                "{}: WARNING: Invalid Mode.default value! Ignoring...".format(
                    os.path.basename(config_file)
                )
            )
    except Exception as e:
        print(e)
        os._exit(-1)
    #
    # Section "DDNS"
    #
    try:
        section = cfg["DDNS"]
        App.DDNS.username   = section.get("username", App.DDNS.username)
        App.DDNS.password   = section.get("password", App.DDNS.password)
        val                 = section.get("enabled modes", App.DDNS.default_for)
        if val != "":
            # Strip leading and trailing whitespace, convert to uppercase
            lst = [ x.strip().upper() for x in val.split(",") ]
            # Remove duplicates
            lst = list(dict.fromkeys(lst))
            # Include only those that are included in mode options -list
            App.DDNS.default_for = [ x for x in lst if x in App.Mode.options ]
    except Exception as e:
        print(e)
        os._exit(-1)




##############################################################################
#
# DDNS (Dynamic Domain Name Service)
#
def setup_ddns(path: str, usr: str, pwd: str):
    # assume that the system partion has been mounted to /mnt
    """Params: path - path to this script, usr & pwd - Dynu DDNS credentials"""


    # Step 1 - create the client script with correct user/pass from secret file
    #with open("{}/dev/dynudns.sh".format(path)) as file:
    #    content = file.read()
    file = App.DDNS.HTML_API_update
    file.content = file.content.replace("{{user}}", usr)
    file.content = file.content.replace("{{pass}}", pwd)
    with open("/mnt" + file.name, "w+") as handle:
        handle.write(file.content)
    os.chmod("/mnt" + file.name, file.permissions)


    # Step 2 - create unit file for systemd service
    file = App.DDNS.systemd_service
    with open("/mnt" + file.name, "w+") as handle:
        handle.write(file.content)
    os.chmod("/mnt" + file.name, file.permissions)


    # Step 3 - enable service by linking it
    shell("ln -s /lib/systemd/system/dynudns.service /mnt/etc/systemd/system/multi-user.target.wants/dynudns.service")


    # Step 4 - create an hourly cron job for DDNS updates
    file = App.DDNS.cron_job
    with open("/mnt" + file.name, "w+") as handle:
        handle.write(file.content)
    os.chmod("/mnt" + file.name, file.permissions)


    # Step 5 - create DHCP client hook for DDNS update on IP change
    #          This is very much utu.fi specific feature, where even registered
    #          NIC will initially begin with bohus IP, receiving a correct one
    #          from DHCP later (sometimes 5 or 10 minutes after booting).
    #          Environment like that needs a functionality to update DDNS as
    #          soon as the IP again changes - and this is it.
    #
    file = App.DDNS.dhclient_hook
    with open("/mnt" + file.name, "w+") as handle:
        handle.write(file.content)
    os.chmod("/mnt" + file.name, file.permissions)

    # Report to App.summary
    msg = "DDNS client installed"
    if usr == "" and pwd == "":
        msg += " (with no credentials!)"
    elif usr == "":
        msg += " (with no username!)"
    elif pwd == "":
        msg += " (with no password!)"
    App.report(msg)



def smb_setup(path: str):
    """Obsoleted by VSC Remote SSH. Left in case this becomes necessary again."""
    smb_conf = r"""[global]
   workgroup = WORKGROUP
   dns proxy = no
   log file = /var/log/samba/log.%m
   max log size = 1000
   panic action = /usr/share/samba/panic-action %d

   server role = standalone server
   passdb backend = tdbsam
   obey pam restrictions = yes
   unix password sync = yes
   passwd program = /usr/bin/passwd %u
   passwd chat = *Enter\snew\s*\spassword:* %n\n *Retype\snew\s*\spassword:* %n\n *password\supdated\ssuccessfully* .
   pam password change = yes
   map to guest = bad user
   usershare allow guests = yes

[homes]
   comment = Home Directories
   browseable = no
   read only = no
   create mask = 0700
   directory mask = 0700
   valid users = %S

[srv]
   comment = Working Directory
   directory = /srv
   browsable = yes
   read only = no
   create mask = 0755
   directory mask = 0755
"""
    with open("/mnt/samba/smb.conf", "w+") as handle:
        handle.write(smb_conf)
    #
    # ATTENTION!
    # This lacks user password creation "smbpasswd" or whatever...
    # I have no idea where that piece of code was lost. Redo, if needed.




###############################################################################
#
# COMMON
#

def getch():
    """Read single character from standard input without echo."""
    import sys, tty, termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    except Exception as e:
        print(e)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def yes_or_no(question):
    c = ""
    print(question + " (Y/N): ", end = "", flush = True)
    while c not in ("y", "n"):
        c = getch().lower()
    return c == 'y'


def shell(cmd: str):
    """Allow exceptions"""
    return subprocess.run(cmd.split(" ")).returncode


def do_or_die(cmd: str):
    """Die (exit) on exception or non-zero return code"""
    try:
        if shell(cmd):
            raise ValueError("Non-zero return code!")
    except Exception as e:
        print(e)
        print("Command '{}' failed!".format(cmd))
        os._exit(-1)


def choose_image_file(dir: str) -> str:
    """If more than one *.img in script directory, let user choose."""
    import glob
    os.chdir(dir)
    img_list = sorted(glob.glob("*.img"))
    if len(img_list) < 1:
        print("NO Rasbian IMAGES IN SCRIPT DIRECTORY!")
        print(
            "Please download from https://downloads.raspberrypi.org/raspbian_lite_latest and extract to '{}' directory".format(
                dir
            )
        )
        os._exit(-1)
    elif len(img_list) == 1:
        return img_list[0]
    else:
        print("Choose image:")
        for i, file in enumerate(img_list):
            print("  ", i + 1, file)
        sel = None
        while (not sel):
            try:
                sel = input(
                    "Enter selection (1-{} or empty to exit): ".format(
                        len(img_list)
                    )
                )
            except KeyboardInterrupt:
                print("\nExiting...")
                os._exit(0)
            # Exit on ENTER (empty)
            if sel == "":
                print("Exiting...")
                os._exit(0)
            try:
                val = int(sel)
                if val < 1 or val > len(img_list):
                    sel = None
                else:
                    return img_list[val - 1]
            except:
                sel = None
        print("CRITICAL ERROR - EXECUTION MUST NEVER REACH THIS POINT!!")
        os._exit(-1)


def disk_exists(path: str) -> bool:
    """Simply checks if given path points to a block device. For this reason, both /dev/sda and /dev/sda1 return both true."""
    try:
        return stat.S_ISBLK(os.stat(path).st_mode)
    except:
        return False


def choose_disk(suggested: str) -> str:
    """Check and choose disk device to write into"""
    def disk_safety_message(disk: str) -> str:
        """Verbose reason for not-safe, or empty for safe disks"""
        mpoints = disk_mountpoints(disk)
        if "/" in mpoints:
            return "FATAL! Contains system root partition!"
        elif len(mpoints) > 0:
            return "UNSAFE! One or more partitions are mounted"
        else:
            return ""
        # End-of-function
    # User suggested may be None
    if suggested is not None:
        if not disk_exists(suggested):
            print(
                "Specified device '{}' does not exist!".format(
                    suggested
                )
            )
            os._exit(-1)
        elif disk_is_mounted(suggested):
            print(
                "Specifield device '{}' has mounted parition(s)!".format(
                    suggested
                )
            )
            if not yes_or_no("This is unsafe! Continue?"):
                print("NO")
                os._exit(0)
            else:
                print("YES")
        return suggested

    # User has not provided target device
    disks = get_disk_list()
    # a list of safe disks (not mounted)
    safes = [ disk for disk in disks if not disk_is_mounted(disk) ]

    if len(safes) == 1 and safes[0].startswith("/dev/mmcblk"):
        # Only one MMCBLK present, and nothing mounted from it
        print(
            "Single mmcblk device detected ('{}') ".format(
                safes[0]
            ) + \
            "and none of its partitions are mounted."
        )
        print("Autoselecting '{}'".format(safes[0]))
        return safes[0]

    # Prompt user to choose
    print("Choose target device:")
    for i, disk in enumerate(disks):
        print(
            "{:>4} {:<20} {}".format(
                i + 1,
                disk,
                disk_safety_message(disk)
            )
        )
    sel = None
    while (not sel):
        try:
            sel = input(
                "Enter selection (1-{} or empty to exit): ".format(
                    len(disks)
                )
            )
        except KeyboardInterrupt:
            print("\nExiting...")
            os._exit(0)
        # Exit on ENTER (empty)
        if sel == "":
            print("Exiting...")
            os._exit(0)
        try:
            val = int(sel)
            if val < 1 or val > len(disks):
                sel = None
            else:
                if disks[val - 1] not in safes:
                    if not yes_or_no(
                        "Choosing mounted disk is VERY unsafe! Continue?"
                    ):
                        return choose_disk(None)
                    else:
                        print("YES")
                return disks[val - 1]
        except:
            sel = None

    print("CRITICAL ERROR - EXECUTION MUST NEVER REACH THIS POINT!!")
    os._exit(-1)


#
# Both of these should check for parition's filesystem...
#
def get_boot_partition(blkdev: str) -> str:
    """Naive implementation. Accepts name only, without '/dev/' path."""
    if blkdev.startswith("mmcblk"):
        return "/dev/{}p1".format(blkdev)
    else:
        return "/dev/{}1".format(blkdev)


def get_root_partition(blkdev: str) -> str:
    """Naive implementation. Accepts name only, without '/dev/' path."""
    if blkdev.startswith("mmcblk"):
        return "/dev/{}p2".format(blkdev)
    else:
        return "/dev/{}2".format(blkdev)


def file_exists(file: str) -> bool:
    """Accepts path/file or file and tests if it exists (as a file)."""
    if os.path.exists(file):
        if os.path.isfile(file):
            return True
    return False


def get_disk_list() -> list:
    """Using lsblk, create a list of canonical disk names"""
    import subprocess
    # -p canonical names, -d no partitions, -r raw (delimited by one space),
    # -n no header
    out = subprocess.run(
        "/bin/lsblk -p -d -r -n".split(),
        stdout = subprocess.PIPE
    )
    stdout = out.stdout.decode('utf-8').strip()
    return [ dsk[0] for dsk in [ line.split() for line in stdout.split('\n') ]]


def disk_mountpoints(disk: str) -> list:
    """Returns a list of mount points, or empty list if none"""
    import subprocess
    res = []
    # -r raw, -n no header, -x sort (very necessary, disk first)
    out = subprocess.run(
        "/bin/lsblk -r -n -x MAJ:MIN {}".format(disk).split(),
        stdout = subprocess.PIPE
    )
    # First line is the disk, strip it, leave partitions
    stdout = out.stdout.decode('utf-8').strip().split("\n", 1)[1]
    for partition in [ line.split() for line in stdout.split('\n') ]:
        assert(partition[1].split(':')[1] != '0') # No disks!
        # if partition has 7th column, its mounted
        if len(partition) > 6:
            res.append(partition[6])
    return res


def disk_is_mounted(disk: str) -> bool:
    """Return True if specified disk has any partitions that are mounted"""
    if len(disk_mountpoints(disk)) > 0:
        return True
    return False


def customise_bash(home: str):
    """Bash customization for user specfied via 'home' directory argument."""
    content = "\n\n\n# Added by {} ver.{}\n\n".format(
        App.Script.name,
        App.version
    )
    content += r"""git_status() {
    STATUS=$(git status 2>/dev/null |
    awk '
    /^On branch / {printf($3)}
    /^You are currently rebasing/ {printf("rebasing %s", $6)}
    /^Initial commit/ {printf(" (init)")}
    /^Untracked files/ {printf("|+")}
    /^Changes not staged / {printf("|?")}
    /^Changes to be committed/ {printf("|*")}
    /^Your branch is ahead of/ {printf("|^")}
    ')
    """
    content += """[ -n "$STATUS" ] &&  echo -ne " [$STATUS]"\n"""
    content += "}\n\n"
    content += r"""PS1='\[\033[0;32m\]\[\033[0m\033[0;32m\]\u\[\033[0;36m\]@\h:\w\[\033[0;32m\]$(git_status)\[\033[0m\033[0;32m\] \$\[\033[0m\033[0;32m\]\[\033[0m\] '"""

    rcfile = "{}/.bashrc".format(home)
    try:
        with open(rcfile, "a") as rc:
            rc.write(content)
    except:
        print("ERROR: Unable to open '{}'! Does not exist?".format(rcfile))
        raise


def copy_ssh(home: str):
    """If './ssh/' directory is present, copies its content to '{home}/.ssh'. Return a list of copied files, or empty list if the source directory existed but contained no files. Returns None if source directory does not exist."""
    src = "{}/ssh".format(App.Script.path)
    tgt = "{}/.ssh".format(home)
    lst = []
    if not os.path.isdir(src):
        return None
    # get UID and GID for home - use them to set ownerships
    home_info = os.stat(home) # raises FileNotFoundError if necessary
    # Create target directory, if necessary
    if not os.path.isdir(tgt):
        os.mkdir(tgt, 0o755)
        os.chown(tgt, home_info.st_uid, home_info.st_gid)
    # loop over files in source
    for filename in os.listdir(src):
        import shutil
        shutil.copy("{}/{}".format(src, filename), tgt)
        os.chown(
            "{}/{}".format(tgt, filename),
            home_info.st_uid,
            home_info.st_gid
        )
        lst.append(filename)
    return lst




##############################################################################
#
# MAIN
#
##############################################################################
if __name__ == '__main__':

    #
    # Check that /mnt is not already a mount point
    #
    if os.path.ismount("/mnt"):
        # Auto-unmount is not very wise - it may not be a leftover from us.
        print("Directory '/mnt' is already mounted!")
        print("Unmount ('umount /mnt') and re-run this script.")
        os._exit(1)


    #
    # Read .config -file
    #
    read_config(App.Script.config_file)


    #
    # Commandline arguments
    #
    parser = argparse.ArgumentParser(
        description     = HEADER,
        formatter_class = argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-m',
        '--mode',
        help    = "Instance mode. Default: '{}'".format(App.Mode.default),
        choices = App.Mode.options,
        dest    = "mode",
        default = App.Mode.default,
        type    = str.upper,
        metavar = "MODE"
    )
    parser.add_argument(
        '--device',
        help    = "Write to specified device.",
        dest    = "write_to_device",
        metavar = "DEVICE"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--noddns',
        help = 'Do not add DDNS client into the instance.',
        action = 'store_true'
    )
    group.add_argument(
        '--ddns',
        help = 'Add DDNS client into the instance.',
        action = 'store_true'
    )
    parser.add_argument(
        '-s',
        '--nokeys',
        help    = 'Do not copy SSH keys.',
        action  = 'store_true',
        dest    = 'nokeys'
    )
    args = parser.parse_args()


    #
    # Require root user
    # Checked here so that non-root user can still get help displayed
    #
    if os.getuid() != 0:
        parser.print_help(sys.stderr)
        print("ERROR: root privileges required!")
        print(
            "Use: 'sudo {}' (alternatively 'sudo su -' or 'su -')".format(
                App.Script.name
            )
        )
        os._exit(1)


    #
    # Print header
    #
    print(HEADER)
    print(
        "Creating",
        args.mode,      # Not yet in App data structure...
        "instance  (use -m {} to change)".format(
            "[" + "|".join(App.Mode.options) + "]"
        )
    )


    #
    # Disable ssh/ -files copy?
    #
    if args.nokeys:
        App.SSHKeys.selected = False


    #
    # Mode validity is checked by argparse. Set App.Mode.selected
    #
    App.Mode.selected = args.mode

    #
    # Block device (SD / disk)
    # Argument is "suggested" device (--device DEVICE)
    #
    App.blkdev = choose_disk(args.write_to_device).split('/')[-1]
    # App.blkdev will contain device name only (without '/dev/')


    #
    # Work out Rasbian image files to choose from
    #
    App.image = choose_image_file(App.Script.path)


    #
    # Resolve if to install DDNS or not
    #
    if args.noddns:
        App.DDNS.selected = False
    elif args.ddns:
        App.DDNS.selected = True
    elif App.Mode.selected in App.DDNS.default_for:
        App.DDNS.selected = True
    else:
        App.DDNS.selected = False


    #
    # Warn if DDNS credentials are not set, but DDNS client is requested
    #
    if App.DDNS.selected == True and (
        App.DDNS.username == "" or App.DDNS.password == ""
    ):
        print("WARNING! DDNS client is requested, but credentials for it are not set!")
        print("Tip: Add DDNS username and password into '{}'.".format(
                App.Script.config_file
            )
        )
        if not yes_or_no("Continue without DDNS credentials?"):
            print("NO")
            os._exit(0)
        else:
            print("YES")


    ###########################################################################
    #
    # Write and configure SD / target disk
    #

    #
    # Write image
    #
    print(
        "Writing Rasbian image to block device '{}'... ".format(App.blkdev),
        end = '', flush = True
    )
    do_or_die(
        "dd if={} of=/dev/{} bs=4M conv=fsync".format(
            App.image,
            App.blkdev
        )
    )
    # For unknown reason, immediate mount after dd has high chance of failure.
    # Sleep some...
    time.sleep(3)
    # First, write directly into the App.summary to get differnt kind of indent
    App.summary = "\n/dev/{}:\n".format(App.blkdev)
    App.report("Rasbian image '{}'".format(App.image))
    print("Done!")


    ###########################################################################
    #
    # /boot partition related items
    #

    #
    # Mount /boot partition to /mnt
    #
    print(
        "Mounting SD:/boot into /mnt... ",
        end = '', flush = True
    )
    do_or_die(
        "mount {} /mnt".format(
            get_boot_partition(App.blkdev)
        )
    )
    print("Done!")


    try:
        #
        # Create 'ssh' -file
        #
        print(
            "Enabling SSH server... ",
            end = '', flush = True
        )
        do_or_die("touch /mnt/ssh")
        App.report("SSH server enabled")
        print("Done!")


        #
        # Copy ´install.py´ to /boot (/mnt)
        #
        print(
            "Copying /boot/install.py... ",
            end = '', flush = True
        )
        do_or_die("cp {}/install.py /mnt/".format(App.Script.path))
        App.report("/boot/install.py")
        print("Done!")


        #
        # (dev | uat | prd) into /boot/install.conf
        #
        print(
            "Writing /boot/install.config... ",
            end = '', flush = True
        )
        # Replace with configparser, if the number of options grow much
        with open("/mnt/install.config", "w+") as file:
            file.write("[Config]\n")
            file.write("mode = {}\n".format(App.Mode.selected))
        App.report("/boot/install.config")
        print("Done!")

    except Exception as e:
        App.report("EXCEPTION: " + str(e))

    finally:
        #
        # Unmount /boot
        #
        print(
            "Unmounting /boot partition from /mnt... ",
            end = '', flush = True
            )
        do_or_die("umount /mnt")
        # Mounting /mnt immediately after umount sometimes causes errors
        # Sleeping here will make sure no such errors happen
        time.sleep(3)
        print("Done!")


    ###########################################################################
    #
    # / (root) partition related items
    #
    print(
        "Mounting SD:/ into /mnt... ",
        end = '', flush = True
    )
    do_or_die(
        "mount {} /mnt".format(
            get_root_partition(App.blkdev)
        )
    )
    print("Done!")


    try:
        #
        # System accepts DHCP specified hostname, if we have empty /etc/hostname
        #
        print(
            "Clearing /etc/hostname... ",
            end = '', flush = True
        )
        # Gets truncated on open
        with open("/mnt/etc/hostname", "w") as file:
            pass
        App.report("/etc/hostname cleared")
        print("Done!")


        #
        # DDNS Client
        #
        if App.DDNS.selected:
            print(
                "Setting up DDNS... ",
                end = '', flush = True
            )
            setup_ddns(
                App.Script.path,
                App.DDNS.username,
                App.DDNS.password
            )
            # setup_ddns() writes the App.report()
            # BECAUSE the message changes depending on
            # which credentials were found while doing it.
            print("Done!")


        #
        # Bash customisation for user 'pi'
        #
        print(
            "Customising Bash prompt for user 'pi'...",
            end = '', flush = True
        )
        customise_bash("/mnt/home/pi")
        App.report("User 'pi' Bash prompt customised")
        print("Done!")


        #
        # Copy ssh -keys
        #
        if  App.SSHKeys.selected:
            if os.path.isdir(App.Script.path + "/ssh"):
                print(
                    "Copying SSH keys...",
                    end = "", flush = True
                )
                files = copy_ssh("/mnt/home/pi")
                print("Done!")
                App.report("SSH keys copied: {}".format(", ".join(files)))
            else:
                print(
                    "SSH keys directory '{}' not found. Skipping!".format(
                        App.Script.path + "/ssh"
                    )
                )
                App.report(
                    "No SSH keys copied. '{}' does not exist.".format(
                        App.Script.path + "/ssh"
                    )
                )


    except Exception as e:
        App.report("EXCEPTION: " + str(e))
        raise

    finally:
        #
        # Unmount root partition
        #
        print(
            "Unmounting system partition... ",
            end = '', flush = True
        )
        do_or_die("umount /mnt")
        print("Done!")

    print("PATEMON Rasbian image creation is done!")
    print(App.summary)
    print("You can safely remove the uSD card now.")
    print("Next:")
    print("\t1. Insert the uSD into PateMonitor Raspberry and start it up.")
    print("\t2. Login as pi/raspberry.")
    print("\t3. Run install.py ('sudo /boot/install.py')")
    print("\t4. Follow the instructions provided by install.py")
    # some sounds to wake user up on completion
    for _ in range(0, 4):
        sys.stdout.write('\a')
        sys.stdout.flush()
        time.sleep(0.6)


# EOF