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
import subprocess

# img = "/root/2018-11-13-raspbian-stretch-lite.img"
img = "2019-04-08-raspbian-stretch-lite.img"
pmidir = "/srv/pminstall"

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

    blkdev = get_mmcblkdev()

    # Write image
    print(
        "Writing Rasbian image to block device '{}'... ".format(blkdev),
        end = ''
        )
    do_or_die("dd if={} of=/dev/{} bs=4M conv=fsync".format(img, blkdev))
    # For unknown reason, immediate mount after dd fails. Sleep some...
    time.sleep(3)
    print("Done!")


    # Mount /boot partition to /mnt
    print(
        "Mounting SD:/boot into /mnt... ",
        end = ''
        )
    do_or_die("mount /dev/{}1 /mnt".format(blkdev))
    print("Done!")


    # Create 'ssh'
    print(
        "Enabling SSH server... ",
        end = ''
        )
    do_or_die("touch /mnt/ssh")
    print("Done!")


    # Copy ´smb.conf´ to /boot (/mnt)
    print(
        "Copying PATEMON samba config file... ",
        end = ''
        )
    do_or_die("cp {}/smb.conf /mnt/".format(pmidir))
    print("Done!")


    # Copy 'install.py' to /boot (/mnt)
    print(
        "Copying PATEMON install script... ",
        end = ''
        )
    do_or_die("cp {}/install.py /mnt/".format(pmidir))
    print("Done!")


    # Unmount
    do_or_die("umount /mnt")
    print("PATEMON Rasbian image creation is done!")
