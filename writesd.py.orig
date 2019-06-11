#! /usr/bin/env python3
#
#   Script to write and prepare Rasbian image.
#
import os
import sys
import subprocess

img = "/root/2018-11-13-raspbian-stretch-lite.img"
pmidir = "/srv/pminstall"

def do_or_die(cmd: list):
    prc = subprocess.run(cmd.split(" "))
    if prc.returncode:
        print("Command '{}' failed!".format(cmd))
        os._exit(-1)

def get_mmcblkdev():
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


if __name__ == '__main__':

    blkdev = get_mmcblkdev()
    print("Writing Rasbian image to block device '{}'".format(blkdev))

    # Write image
    do_or_die("dd if={} of=/dev/{} bs=4M conv=fsync".format(img, blkdev))

    # Mount /boot partition to /mnt
    do_or_die("mount /dev/{}p1 /mnt".format(blkdev))

    # Create 'ssh'
    do_or_die("touch /mnt/ssh")

    # Copy ´smb.conf´ and ´install.py´ to /boot (/mnt)
    do_or_die("cp {}/smb.conf /mnt/".format(pmidir))
    do_or_die("cp {}/install.py /mnt/".format(pmidir))

    # Unmount
    do_or_die("umount /mnt")

    print("Done!")
