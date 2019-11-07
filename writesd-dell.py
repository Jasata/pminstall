#! /usr/bin/env python3
#
#   Script to write and prepare Rasbian image.
#
#       - Write the image into the uSD card
#       - Enables SSH (touch /boot/ssh)
#       - Copy smb.conf into /boot
#       - Copy install.py into /boot
#
import os
import sys
import time            # sleep()
import argparse
import subprocess

##############################################################################
# CONFIGURABLE ITEMS BELOW
#
# img = "/root/2018-11-13-raspbian-stretch-lite.img"
# img = "2019-04-08-raspbian-stretch-lite.img"
img = "2019-09-26-raspbian-buster-lite.img"
pmidir = "/srv/pminstall"


# PEP 396 -- Module Version Numbers https://www.python.org/dev/peps/pep-0396/
__version__ = "0.5.0"
__author__  = "Jani Tammi <jasata@utu.fi>"
VERSION = __version__
HEADER  = """
=============================================================================
University of Turku, Department of Future Technologies
ForeSail-1 / PATE Monitor uSD writer
Version {}, 2019 {}
""".format(__version__, __author__)


def setup_ddns():
    # assume that the system partion has been mounted to /mnt
    # Step 1 - create the client script
    do_or_die("cp {}/dev/dynudns.sh /mnt/usr/local/bin".format(pmidir))
    # Step 2 - set permissions
    do_or_die("chmod 750 /mnt/usr/local/bin/dynudns.sh")
    # Step 3 - create unit file for systemd service
    do_or_die("cp {}/dev/dynudns.service /mnt/lib/systemd/system/".format(pmidir))
    # Step 4 - set unit file permissions
    do_or_die("chmod 644 /mnt/lib/systemd/system/dynudns.service")
    # Step 5 - create service linkage for startup on boot time
    do_or_die("ln -s /lib/systemd/system/dynudns.service /mnt/etc/systemd/system/multi-user.target.wants/dynudns.service")
    # Step 6 - create an hourly cron job for DDNS updates
    do_or_die("cp {}/dev/dynudns.cronjob /mnt/etc/cron.hourly/dynudns".format(pmidir))
    # Step 7 - set cron job permissions
    do_or_die("chmod 755 /mnt/etc/cron.hourly/dynudns")

def do_or_die(cmd: list):
    prc = subprocess.run(cmd.split(" "))
    if prc.returncode:
        print("Command '{}' failed!".format(cmd))
        os._exit(-1)

def get_mmcblkdev_orig():
    """Return one (connected) or die."""
    accepted = ("mmcblk0", "mmcblk1")
    connected = os.listdir("/sys/block")
    mmcblkdevs = [x for x in connected if x in accepted]
    # Allow and require only one
    if len(mmcblkdevs) < 1:
        sys.exit('No MMC block devices connected!')
    elif len(mmcblkdevs) > 1:
        sys.exit('More than one MMC block devices connected!')
    return mmcblkdevs[0]

def get_mmcblkdev():
    """Dummy function for DELL TY1811020 use!"""
    return "sdb"

if __name__ == '__main__':

    #
    # Commandline arguments
    #
    parser = argparse.ArgumentParser(
        description     = HEADER,
        formatter_class = argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-d',
        '--dev',
        help = 'Create development instance.',
        action = 'store_true'
    )
    args = parser.parse_args()


    #
    # Retrieve correct block device
    #
    blkdev = get_mmcblkdev()

    # Write image
    print(
        "Writing Rasbian image to block device '{}'... ".format(blkdev),
        end = '', flush = True
        )
    do_or_die("dd if={} of=/dev/{} bs=4M conv=fsync".format(img, blkdev))
    # For unknown reason, immediate mount after dd fails. Sleep some...
    time.sleep(3)
    print("Done!")


    # Mount /boot partition to /mnt
    print(
        "Mounting SD:/boot into /mnt... ",
        end = '', flush = True
        )
    do_or_die("mount /dev/{}1 /mnt".format(blkdev))
    print("Done!")


    # Create 'ssh'
    print(
        "Enabling SSH server... ",
        end = '', flush = True
        )
    do_or_die("touch /mnt/ssh")
    print("Done!")


    # Copy ´smb.conf´ to /boot (/mnt)
    print(
        "Copying PATEMON samba config file... ",
        end = '', flush = True
        )
    do_or_die("cp {}/smb.conf /mnt/".format(pmidir))
    print("Done!")


    # Copy 'install.py' to /boot (/mnt)
    print(
        "Copying PATEMON install script... ",
        end = '', flush = True
        )
    do_or_die("cp {}/install.py /mnt/".format(pmidir))
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
    if args.dev:
        print("Making development unit specific modifications!",)
        print(
            "Mounting system partition to /mnt...",
            end = '', flush = True
            )
        do_or_die("mount /dev/{}2 /mnt".format(blkdev))
        print("Done!")
        print(
            "Setting up DDNS...",
            end = '', flush = True
            )
        setup_ddns()
        print("Done!")
        print(
            "Unmounting system partition...",
            end = '', flush = True
            )
        do_or_die("umount /mnt")
        print("Done!")


    print("PATEMON Rasbian image creation is done!")
