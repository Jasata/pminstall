#! /usr/bin/env python3
#
#   Script to write and prepare Rasbian image.
#
#   writesd.py - 2018, Jani Tammi <jasata@utu.fi>
#   0.2.0   2019-11-08  Brought up to date with the writesd-dell.py script.
#   0.3.0   2019-11-08  Instance mode commandline options. Other improvements.
#   0.3.1   2019-11-08  Add --device option for writing into a specified device
#
#
#   Commandline options:
#
#       -m, --mode      Specify mode for the instance.
#       --device        Block device (disk) to write into.
#       --noddns        Do not create DDNS client (default for DEV instance)
#
#
#   For home.net development:
#       ./writesd.py -m dev --noddns
#   For utu.fi development:
#       ./writesd.py -m dev --device /dev/sdb
#   For UAT or Release:
#       ./writesd.py -m prd
#
#   ...or define the default mode in Config.py
#
import os
import sys
import stat
import time
import argparse
import subprocess

from Config import Config


# PEP 396 -- Module Version Numbers https://www.python.org/dev/peps/pep-0396/
__version__ = "0.3.1"
__author__  = "Jani Tammi <jasata@utu.fi>"
VERSION = __version__
HEADER  = """
=============================================================================
University of Turku, Department of Future Technologies
ForeSail-1 / uSD writer for Rasbian based PATE Monitor
Version {}, 2019 {}
""".format(__version__, __author__)


#
# GLOBAL Application Error (display warning about errors, if set)
#
app_error = None


##############################################################################
# DEVELOPMENT INSTANCE SPECIFIC
#
def setup_ddns():
    # assume that the system partion has been mounted to /mnt
    # Step 1 - create the client script with correct user/pass from secret file
    with open("{}/dev/dynudns.sh".format(Config.script_dir)) as file:
        content = file.read()
    content = content.replace("{{user}}", Config.Dev.DDNS.username)
    content = content.replace("{{pass}}", Config.Dev.DDNS.password)
    with open("/mnt/usr/local/bin/dynudns.sh", "w+") as file:
        file.write(content)

    # Step 2 - set permissions
    do_or_die("chmod 750 /mnt/usr/local/bin/dynudns.sh")
    # Step 3 - create unit file for systemd service
    do_or_die(
        "cp {}/dev/dynudns.service /mnt/lib/systemd/system/".format(
            Config.script_dir
        )
    )
    # Step 4 - set unit file permissions
    do_or_die("chmod 644 /mnt/lib/systemd/system/dynudns.service")
    # Step 5 - create service linkage for startup on boot time
    do_or_die("ln -s /lib/systemd/system/dynudns.service /mnt/etc/systemd/system/multi-user.target.wants/dynudns.service")
    # Step 6 - create an hourly cron job for DDNS updates
    do_or_die(
        "cp {}/dev/dynudns.cronjob /mnt/etc/cron.hourly/dynudns".format(
            Config.script_dir
        )
    )
    # Step 7 - set cron job permissions
    do_or_die("chmod 755 /mnt/etc/cron.hourly/dynudns")
    # Step 8 - set correct username and password from secret file


def smb_setup():
    #
    # Copy ´smb.conf´ to /boot (/mnt)
    # OBSOLETED BY VSC REMOTE - SSH
    do_or_die(
        "cp {}/dev/smb.conf /mnt/samba/smb.conf".format(
            Config.script_dir
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
    img_list = glob.glob("*.img")
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
                "Enter selection (1-{} or ENTER to exit): ".format(
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
                return img_list[val - 1]
            except:
                sel = None
        print("CRITICAL ERROR - EXECTION MUST NEVER REACH THIS POINT!!")
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


##############################################################################
#
# MAIN
#
##############################################################################
if __name__ == '__main__':

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
        help    = "Instance mode. Default: '{}'".format(Config.Mode.default),
        choices = Config.Mode.options,
        #nargs   = '+',
        dest    = "mode",
        default = Config.Mode.default,
        type    = str.upper,
        metavar = "MODE"
    )
    parser.add_argument(
        '--device',
        help    = "Write to specified device.",
        dest    = "write_to_device",
        metavar = "DEVICE"
    )
    parser.add_argument(
        '--noddns',
        help = 'Do not add DDNS client into dev instance.',
        action = 'store_true'
    )
    args = parser.parse_args()
    #
    # Check selection validity and set Config.Mode.selected
    #
    if (args.mode not in Config.Mode.options):
        print(
            "Invalid instance mode ('{}')! Check your Config.py!".format(
                args.mode
            )
        )
        print("Existing...")
        os._exit(-1)
    Config.Mode.selected = args.mode


    #
    # Print header
    #
    print(HEADER)
    print(
        "Creating",
        Config.Mode.selected,
        "instance  (use -m {} to change)".format(
            "[" + "|".join(Config.Mode.options) + "]"
        )
    )


    #
    # Get script directory
    #
    Config.script_dir = os.path.dirname(os.path.realpath(__file__))


    #
    # Work out Rasbian image files to choose from
    #
    Config.image = get_image_file(Config.script_dir)


    #
    # Retrieve correct block device (or use specified)
    #
    if (args.write_to_device):
        if not disk_exists(args.write_to_device):
            print(
                "Specified device '{}' does not exist!".format(
                    args.write_to_device
                )
            )
            os._exit(-1)
        Config.blkdev = args.write_to_device.split('/')[-1]
    else:
        Config.blkdev = get_mmcblkdev()
    # Config.blkdev will contain device name only (without '/dev/')


    # Write image
    print(
        "Writing Rasbian image to block device '{}'... ".format(Config.blkdev),
        end = '', flush = True
    )
    do_or_die(
        "dd if={} of=/dev/{} bs=4M conv=fsync".format(
            Config.image,
            Config.blkdev
        )
    )
    # For unknown reason, immediate mount after dd has high chance of failure.
    # Sleep some...
    time.sleep(3)
    print("Done!")


    # Mount /boot partition to /mnt
    print(
        "Mounting SD:/boot into /mnt... ",
        end = '', flush = True
    )
    do_or_die(
        "mount {} /mnt".format(
            get_boot_partition(Config.blkdev)
        )
    )
    print("Done!")


    # Create 'ssh' -file
    print(
        "Enabling SSH server... ",
        end = '', flush = True
    )
    do_or_die("touch /mnt/ssh")
    print("Done!")


    # Copy ´install.py´ to /boot (/mnt)
    print(
        "Copying PATEMON install script... ",
        end = '', flush = True
    )
    do_or_die("cp {}/install.py /mnt/".format(Config.script_dir))
    print("Done!")


    # (dev | uat | prd) into /boot/install.conf
    print(
        "Writing /boot/install.conf ...",
        end = '', flush = True
    )
    with open("/mnt/install.conf", "w+") as file:
        file.write("[Config]\n")
        file.write("mode = {}\n".format(Config.Mode.selected))
    print("Done!")


    # Unmount
    print(
        "Unmounting /boot partition from /mnt...",
        end = '', flush = True
        )
    do_or_die("umount /mnt")
    time.sleep(3)
    print("Done!")


    #
    # Dev unit specific details
    #
    if Config.Mode.selected == "DEV":
        print("=" * 50)
        print("Making development unit specific modifications!",)
        print("=" * 50)
        print(
            "Mounting system partition to /mnt...",
            end = '', flush = True
            )
        do_or_die(
            "mount {} /mnt".format(
                get_root_partition(Config.blkdev)
            )
        )
        print("Done!")
        try:
            if (not args.noddns):
                print(
                    "Setting up DDNS...",
                    end = '', flush = True
                    )
                setup_ddns()
                print("Done!")
            # Obsoleted by VSC Remote - SSH
            #print(
            #    "Copying PATEMON samba config file... ",
            #    end = '', flush = True
            #)
            #smb_setup()
            #print("Done!")
        except Exception as e:
            app_error = True
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


    if (app_error):
        print("ERROR: Image creation was not entirely successful!")
    else:
        print("PATEMON Rasbian image creation is done!")

# EOF