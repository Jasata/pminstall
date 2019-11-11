#! /usr/bin/env python3
#
#   Script to write and prepare Rasbian image.
#
#   writesd.py - 2018, Jani Tammi <jasata@utu.fi>
#   0.2.0   2019-11-08  Brought up to date with the writesd-dell.py script.
#   0.3.0   2019-11-08  Instance mode commandline options. Other improvements.
#   0.3.1   2019-11-08  Add --device option for writing into a specified device
#   0.3.2   2019-11-11  Changed from 'Config.py'  to 'writesd.conf'.
#   0.3.3   2019-11-11  Add --ddns option to complement --noddns option.
#   0.3.4   2019-11-11  Fixed "Creating [MODE] instance" message.
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



# PEP 396 -- Module Version Numbers https://www.python.org/dev/peps/pep-0396/
__version__ = "0.3.4"
__author__  = "Jani Tammi <jasata@utu.fi>"
VERSION = __version__
HEADER  = """
=============================================================================
University of Turku, Department of Future Technologies
ForeSail-1 / uSD writer for Rasbian based PATE Monitor
Version {}, 2019 {}
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
    image           = None      # Rasbian image filename
    blkdev          = None      # Device file to write into


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
# DEVELOPMENT INSTANCE SPECIFIC
#
def setup_ddns(path: str, usr: str, pwd: str):
    # assume that the system partion has been mounted to /mnt
    # Step 1 - create the client script with correct user/pass from secret file
    with open("{}/dev/dynudns.sh".format(path)) as file:
        content = file.read()
    content = content.replace("{{user}}", usr)
    content = content.replace("{{pass}}", pwd)
    with open("/mnt/usr/local/bin/dynudns.sh", "w+") as file:
        file.write(content)

    # Step 2 - set permissions
    do_or_die("chmod 750 /mnt/usr/local/bin/dynudns.sh")
    # Step 3 - create unit file for systemd service
    do_or_die(
        "cp {}/dev/dynudns.service /mnt/lib/systemd/system/".format(
            path
        )
    )
    # Step 4 - set unit file permissions
    do_or_die("chmod 644 /mnt/lib/systemd/system/dynudns.service")
    # Step 5 - create service linkage for startup on boot time
    do_or_die("ln -s /lib/systemd/system/dynudns.service /mnt/etc/systemd/system/multi-user.target.wants/dynudns.service")
    # Step 6 - create an hourly cron job for DDNS updates
    do_or_die(
        "cp {}/dev/dynudns.cronjob /mnt/etc/cron.hourly/dynudns".format(
            path
        )
    )
    # Step 7 - set cron job permissions
    do_or_die("chmod 755 /mnt/etc/cron.hourly/dynudns")
    # Step 8 - set correct username and password from secret file


def smb_setup(path: str):
    #
    # Copy ´smb.conf´ to /boot (/mnt)
    # OBSOLETED BY VSC REMOTE - SSH
    do_or_die(
        "cp {}/dev/smb.conf /mnt/samba/smb.conf".format(
            path
        )
    )


##############################################################################
# COMMON
#
def do_or_die(cmd: list):
    prc = subprocess.run(cmd.split(" "))
    if prc.returncode:
        print("Command '{}' failed!".format(cmd))
        os._exit(-1)


def get_mmcblkdev() -> str:
    """If exactly one MMC block device is connected, return that."""
    accepted = ("mmcblk0", "mmcblk1")
    connected = os.listdir("/sys/block")
    mmcblkdevs = [x for x in connected if x in accepted]
    # Allow and require only one
    if len(mmcblkdevs) < 1:
        sys.exit('No MMC block devices connected!')
    elif len(mmcblkdevs) > 1:
        sys.exit('More than one MMC block devices connected!')
    return mmcblkdevs[0]


def get_image_file(dir: str) -> str:
    """If more than one *.img in script directory, let user choose."""
    import glob
    os.chdir(dir)
    img_list = sorted(glob.glob("*.img"))
    if len(img_list) < 1:
        print("NO Rasbian IMAGES IN SCRIPT DIRECTORY!")
        os._exit(-1)
    elif len(img_list) == 1:
        return img_list[0]
    else:
        print("Choose image:")
        for i, file in enumerate(img_list):
            print("  ", i + 1, file)
        sel = None
        while (not sel):
            sel = input(
                "Enter selection (1-{} or empty to exit): ".format(
                    len(img_list)
                )
            )
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


##############################################################################
#
# MAIN
#
##############################################################################
if __name__ == '__main__':

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
    args = parser.parse_args()


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
    # Mode validity is checked by argparse. Set App.Mode.selected
    #
    App.Mode.selected = args.mode

    #
    # Block device (SD / disk)
    #
    if (args.write_to_device):
        if not disk_exists(args.write_to_device):
            print(
                "Specified device '{}' does not exist!".format(
                    args.write_to_device
                )
            )
            os._exit(-1)
        App.blkdev = args.write_to_device.split('/')[-1]
    else:
        App.blkdev = get_mmcblkdev()
    # App.blkdev will contain device name only (without '/dev/')


    #
    # Work out Rasbian image files to choose from
    #
    App.image = get_image_file(App.Script.path)


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
    print("Done!")


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


    #
    # Create 'ssh' -file
    #
    print(
        "Enabling SSH server... ",
        end = '', flush = True
    )
    do_or_die("touch /mnt/ssh")
    print("Done!")


    #
    # Copy ´install.py´ to /boot (/mnt)
    #
    print(
        "Copying /boot/install.py ... ",
        end = '', flush = True
    )
    do_or_die("cp {}/install.py /mnt/".format(App.Script.path))
    print("Done!")


    #
    # (dev | uat | prd) into /boot/install.conf
    #
    print(
        "Writing /boot/install.conf ...",
        end = '', flush = True
    )
    # Replace with configparser, if the number of options grow much
    with open("/mnt/install.conf", "w+") as file:
        file.write("[Config]\n")
        file.write("mode = {}\n".format(App.Mode.selected))
    print("Done!")


    #
    # Unmount
    #
    print(
        "Unmounting /boot partition from /mnt...",
        end = '', flush = True
        )
    do_or_die("umount /mnt")
    time.sleep(3)
    print("Done!")


    ###########################################################################
    #
    # Dev unit specific details
    #
    if App.Mode.selected == "DEV":
        print("=" * 50)
        print("Making development unit specific modifications!",)
        print("=" * 50)
        print(
            "Mounting system partition to /mnt...",
            end = '', flush = True
            )
        do_or_die(
            "mount {} /mnt".format(
                get_root_partition(App.blkdev)
            )
        )
        print("Done!")
        try:
            if (App.DDNS.selected):
                print(
                    "Setting up DDNS...",
                    end = '', flush = True
                    )
                setup_ddns(
                    App.Script.path,
                    App.DDNS.username,
                    App.DDNS.password
                )
                print("Done!")
            # Obsoleted by VSC Remote - SSH
            #print(
            #    "Copying PATEMON samba config file... ",
            #    end = '', flush = True
            #)
            #smb_setup()
            #print("Done!")
        except Exception as e:
            # Print error, but do not stop (need to unmount)
            print(e)
        finally:
            # Unmount, succeed or fail
            print(
                "Unmounting system partition...",
                end = '', flush = True
                )
            do_or_die("umount /mnt")
            print("Done!")
        print("=" * 50)


    print("PATEMON Rasbian image creation is done!")

# EOF