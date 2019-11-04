#! /usr/bin/env python3
#
#   Script to write and prepare Rasbian image.
#
import os
import sys
import time             # for time.sleep()
import subprocess

img = "/root/2018-11-13-raspbian-stretch-lite.img"
pminstall_dir = "/srv/pminstall"

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
    print(
        "Writing Rasbian image to block device '{}'... ".format(blkdev),
        end = '', flush=True
    )
    do_or_die("dd if={} of=/dev/{} bs=4M conv=fsync".format(img, blkdev))
    # For unknown reason, immediate mount after dd has high chance of failure.
    # Sleep some...
    time.sleep(3)
    print("Done!")

    # Mount /boot partition to /mnt
    print(
        "Mounting SD:/boot into /mnt... ",
        end = '', flush=True
    )
    do_or_die("mount /dev/{}p1 /mnt".format(blkdev))
    print("Done!")

    # Create 'ssh'
    print(
        "Enabling SSH server... ",
        end = '', flush=True
    )
    do_or_die("touch /mnt/ssh")
    print("Done!")

    # Copy ´smb.conf´ to /boot (/mnt)
    print(
        "Copying PATEMON samba config file... ",
        end = '', flush=True
    )
    do_or_die("cp {}/smb.conf /mnt/".format(pminstall_dir))
    print("Done!")

    # Copy ´install.py´ to /boot (/mnt)
    print(
        "Copying PATEMON install script... ",
        end = '', flush=True
    )
    do_or_die("cp {}/install.py /mnt/".format(pminstall_dir))
    print("Done!")

    # Unmount
    do_or_die("umount /mnt")
    print("PATEMON Rasbian image creation is done!")

# EOF