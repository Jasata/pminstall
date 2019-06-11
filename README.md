# PATE Monitor Installation Script

**Target platform:** Raspberry Pi 3 B+<br>
**Target OS:** Rasbian 2018-11-13 or newer<br>
**Dependencies:** Python 3.5.3 or newer, PySerial ver X.X ...<br>

### Installation Activities

 - Sets system timezone as Europe/Helsinki
 - Sets keymap to `pc105` / `fi`
 - Updates system packages (`apt update`, `apt -y upgrade`)
 - **TODO** Configures WiFI AP and `dnsmasq` DHCP server. _Needs to be optional for DevMode installs!_
 - Creates needed user groups and accounts
 - Installs packaged needed by PATE Monitor (`apt install ...`)
 - Configures nginx and uwsgi.
 - Clones PATE Monitor related GitHub repositories and executes `setup.py` from each.

# Installation Procedure

 1. Write Rasbian image into an SD.
 2. Create file `/boot/ssd`.
 3. Copy this `install.py` to `/boot/`.
 4. Boot, ssh into the box, assume `root` identity, run `/boot/install.py`.

# Additional Steps (DevMode)

**NOTE:** Samba shares are less than ideal for UTU network. One stress reducing approach would be to use Visual Studio Code Inisders edition and Remote-SSH module. _As of June 2019, the Remote-SSH has not yet been released for mainstream VSC._

Basic Samba installation steps (using provided `smb.conf` file):

  1. Install Samba: `# apt -y install samba`.
  2. Copy the provided `smb.conf` into `/etc/samba/`.
  3. Add Samba password for user `pi`: `# smbpasswd -a pi`.
  4. Restard Samba: `# systemctl restart smbd`.
