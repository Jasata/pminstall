# PATE Monitor Installation Script

**Target platform:** Raspberry Pi 3 B+
**Target OS:** Rasbian 2018-11-13 or newer
**Dependencies:** Python 3.5.3 or newer, PySerial ver X.X ...

### Installation Activities

 - Sets system timezone as Europe/Helsinki
 - Updates system packages.
 - **TODO** Configures WiFI AP and `dnsmasq` DHCP server. _Needs to be optional for DevMode installs!_
 - Creates needed user groups and accounts.
 - Installs packaged needed by PATE Monitor.
 - Configures nginx and uwsgi.
 - Clones PATE Monitor related GitHub repositories and executes `setup.py` from each.

# Installation Procedure

 1. Write Rasbian image into an SD.
 2. Create file `/boot/ssd`.
 3. Copy this `install.py` to `/boot/`.
 4. Boot, ssh into the box, assume `root` identity, run `/boot/install.py`.

# Additional Steps (DevMode)

For development purposes, SMB share should be set up.

  1. Install Samba: `# apt -y install samba`.
  2. Copy the provided `smb.conf` into `/etc/samba/`.
  3. Add Samba password for user `pi`: `# smbpasswd -a pi`.
  4. Restard Samba: `# systemctl restart smbd`.
