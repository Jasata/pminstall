#! /usr/bin/env python3
#
#   Script to write and prepare Rasbian image.
#
#   writesd.py - 2018, Jani Tammi <jasata@utu.fi>
#   0.2.0   2019-11-08  Brought up to date with the writesd-dell.py script.
#
import os
import sys
import time
import argparse
import subprocess

from Config import Config
##############################################################################
# CONFIGURABLE ITEMS BELOW
#
#img = "/root/2018-11-13-raspbian-stretch-lite.img"
#img = "/root/2018-11-13-raspbian-stretch-lite.img"
#img = "2019-04-08-raspbian-stretch-lite.img"
img = "2019-09-26-raspbian-buster-lite.img"

# TODO: Make these into get_script_dir() function, which
# resolves the location of this script. All resources must
# be relative to this script (unless someday provided via
# command line parameters)
pmidir = "/srv/pminstall"
pminstall_dir = "/srv/pminstall"

# PEP 396 -- Module Version Numbers https://www.python.org/dev/peps/pep-0396/
__version__ = "0.2.0"
__author__  = "Jani Tammi <jasata@utu.fi>"
VERSION = __version__
HEADER  = """
=============================================================================
University of Turku, Department of Future Technologies
ForeSail-1 / PATE Monitor uSD writer
Version {}, 2019 {}
""".format(__version__, __author__)


##############################################################################
# DEVELOPMENT INSTANCE SPECIFIC
#
def setup_ddns():
    # assume that the system partion has been mounted to /mnt
    # Step 1 - create the client script with correct user/pass from secret file
    with open("/mnt/usr/local/bin/dynudns.sh") as file:
        filecontent = file.read()
    filecontent.replace("{{user}}", Config.Dev.DDNS.username)
    filecontent.replace("{{pass}}", Config.Dev.DDNS.password)
    with open("/mnt/usr/local/bin/dynudns.sh") as file:
        file.write(filecontent)
    #do_or_die("cp {}/dev/dynudns.sh /mnt/usr/local/bin".format(pmidir))

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


##############################################################################
# COMMON
#
def do_or_die(cmd: list):
    prc = subprocess.run(cmd.split(" "))
    if prc.returncode:
        print("Command '{}' failed!".format(cmd))
        os._exit(-1)


def get_mmcblkdev() -> str:
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
        '-d',
        '--dev',
        help = 'Create development instance.',
        action = 'store_true'
    )
    args = parser.parse_args()


    #
    # Get script directory
    #
    Config.script_dir = os.path.dirname(os.path.realpath(__file__))


    #
    # Work out Rasbian image files to choose from
    #
    Config.image = get_image_file(Config.script_dir)


    #
    # Retrieve correct block device
    #
    Config.blkdev = get_mmcblkdev()


    # Write image
    print(
        "Writing Rasbian image to block device '{}'... ".format(Config.blkdev),
        end = '', flush = True
    )
    do_or_die("dd if={} of=/dev/{} bs=4M conv=fsync".format(img, Config.blkdev))
    # For unknown reason, immediate mount after dd has high chance of failure.
    # Sleep some...
    time.sleep(3)
    print("Done!")


    # Mount /boot partition to /mnt
    print(
        "Mounting SD:/boot into /mnt... ",
        end = '', flush = True
    )
    do_or_die("mount /dev/{}p1 /mnt".format(Config.blkdev))
    print("Done!")


    # Create 'ssh' -file
    print(
        "Enabling SSH server... ",
        end = '', flush = True
    )
    do_or_die("touch /mnt/ssh")
    print("Done!")


    #
    # TODO: Make dev specific
    #
    # Copy ´smb.conf´ to /boot (/mnt)
    print(
        "Copying PATEMON samba config file... ",
        end = '', flush = True
    )
    do_or_die("cp {}/smb.conf /mnt/".format(Config.script_dir))
    print("Done!")


    # Copy ´install.py´ to /boot (/mnt)
    print(
        "Copying PATEMON install script... ",
        end = '', flush = True
    )
    do_or_die("cp {}/install.py /mnt/".format(Config.script_dir))
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
        print("=" * 50)
        print("Making development unit specific modifications!",)
        print("=" * 50)
        print(
            "Mounting system partition to /mnt...",
            end = '', flush = True
            )
        do_or_die("mount /dev/{}p2 /mnt".format(Config.blkdev))
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
        print("=" * 50)


    print("PATEMON Rasbian image creation is done!")

# EOF