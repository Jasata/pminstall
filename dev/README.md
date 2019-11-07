# Development image specific resources

This directory contains files that are used ONLY in the creation of a development system image.

Please see the writesd.py and/or writesd-dell.py uSD writer scripts for specifics, if interested.

## Dynu DDNS Service

Because in the UTU network devices that have not been purchased through the appropriate channels do not get any IP addresses at all, and because when an IP is requested, it will be granted via dynamic pool, and finally because the development unit will be headless ... a solution is needed to connect to the development device reliably.

Adopted approach is to create an account into a free DDNS service and update the IP of the development device.

Selected service is [Dynu DNS](https://www.dynu.com/en-US/) and the hostname chosen for development machine is `pate.freeddns.org`. Account details are stored into a separate file that is excluded via `.gitignore`.

TODO:

  - Create secret.py and import that `from myconfig import *` -style into the `writesd.py`.
  - Use these values to search and replace tokens in the appropriate files after they have been written/copied to the target.
 
  - Additional todo; enable dev options automatically for the `install.py`
  - Create option `--noddns` for my personal dev use (unnecessary in my own network)
  - Make sure that `install.py` has some way to NOT execute with dev options, if user so chooses.
 
 
