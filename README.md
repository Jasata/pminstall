# PATE Monitor Installation Script

**Target platform:** Raspberry Pi 3 B+<br>
**Target OS:** Rasbian 2018-11-13 or newer<br>
**Dependencies:** Python 3.5.3 or newer, PySerial ver 3.2.1 ...<br>
(There may eventually be Python 3.7 dependancies, as development continues with Debian 10 based system)

## Process in Brief

  1. Write Rasbian uSD using `writesd.py`
  2. Boot Raspberry Pi and execute `/boot/install.py` (added by `writesd.py`)

The main installer (`install.py`) does some system configuration and installs needed software packages before cloning a number of Github repositories and executing a `setup.py` script in each of them.

## Preparations

 - Clone this repository to a Linux PC. One with built-in MMC SD slot is recommended, althought a PC with USB SD adapter will work too.
 - If you need to create development instance or utu.fi network, you need DynuDNS account. Create it and set the username and password in the `writesd.conf` -file.
 - Enter the repository directory (`pminstall`), download and extract Rasbian OS image to this directory.
 - Insert SD card. If USB SD adapter is used, specify `--device ` with the appropriate device file. Find out what it is...
 - (optional) Review and change `Config.py` settings for defaults better suited for your system.

Create utu.fi -domain Pate Monitor development instance using a PC with USB-uSD adapter:

    # ./writesd.py --device /dev/sdb --mode dev

**But, please be absolutely sure your device file points to a uSD, not a harddisk!**

### Installation Activities (performed by install.py)

 - **TODO** Read `boot/install.config` for instance mode (dev|uat|prd specifics still unclear... thus todo)
 - Sets system timezone as Europe/Helsinki
 - Sets keymap to `pc105` / `fi`
 - Updates system packages (`apt update`, `apt -y upgrade`)
 - **TODO** Configures WiFI AP and `dnsmasq` DHCP server. _Needs to be optional for DevMode installs!_
 - Creates needed user groups and accounts
 - Installs packaged needed by PATE Monitor (`apt install ...`)
 - Configures nginx and uwsgi.
 - Clones PATE Monitor related GitHub repositories and executes `setup.py` from each.

# Installation Procedure

A separate script (`writesd.py`) is provided for creating the Raspbian SD along with additional changes therein. If `writesd.py` should not work, please refer to manual SD creation instructions.

## Using writesd.py

    usage: writesd.py [-h] [-m [MODE]] [--noddns]
    
    =============================================================================
    University of Turku, Department of Future Technologies
    ForeSail-1 / uSD writer for Rasbian based PATE Monitor
    Version 0.3.0, 2019 Jani Tammi <jasata@utu.fi>
    
    optional arguments:
      -h, --help            show this help message and exit
      -m MODE, --mode MODE  Instance mode. Default: 'DEV'
      --device DEVICE       Write to specified device.
      --noddns              Do not add DDNS client into the instance.
      --ddns                Add DDNS client into the instance.

*Note that `writesd.config` file can be modified to set the default instance mode.

## Manual Rasbian SD Creation

 1. Write Rasbian image into an SD. (`dd if=${rasbian_image} of=/dev/mmcblk0 bs=4M conv=fsync`)
 2. Mount `/dev/mmcblk0p1` (aka. "boot") to `/mnt` and create file `/mnt/ssh` (to enable remote SSH connections).
 3. Copy the `install.py` to `/mnt/`.
 4. Create `install.config` to `/mnt/`, containing "[Config]\nmode = PRD" (or whatever mode you want).
 4. Unmount `/mnt/` and remove uSD.

## Dev Mode

For a development instances, in utu.fi -domain, you need to enable DDNS client (due to dynamic IP and the unit being headless). Details how to manage that should be read from the `writesd.py` script source.

### Samba (obsoleted by RPi support in VSC Remote - SSH extension)

**NOTE:** Samba shares are less than ideal for UTU network. One stress reducing approach would be to use Visual Studio Code Inisders edition and Remote-SSH module. _As of June 2019, the Remote-SSH has not yet been released for mainstream VSC._
**NOTE2:** November 2019, Raspberry Rasbian support now works!
Basic Samba installation steps (using provided `smb.conf` file):

  1. Install Samba: `# apt -y install samba`.
  2. Copy the provided `smb.conf` into `/etc/samba/`.
  3. Add Samba password for user `pi`: `# smbpasswd -a pi`.
  4. Restard Samba: `# systemctl restart smbd`.

## Install Pate Monitor

Insert uSD to Raspberry Pi, boot, ssh into the box, assume `root` identity (`sudo su -`), run `/boot/install.py`. Unless errors are reported, the system should now be up and running. Open browser on your Pate Monitor address to check.

# Change Log

2019.11.04 Updated to Debian 10 based [Raspbian Buster Lite 2019-09-26](https://www.raspberrypi.org/downloads/raspbian/), Python 3.7.3 and PySerial 3.4.
