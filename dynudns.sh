#!/bin/bash
# 2019.11.07 // Jani Tammi
# Dynu DNS - Service for dynamic IP
#
#    IP Update Protocol
#    https://www.dynu.com/en-US/DynamicDNS/IP-Update-Protocol
#
#    Interface:
#    http://api.dynu.com/nic/update?myip=${}&username=${}&password=${}
#      myip            The IP you wish to store into the DDNS
#      username        The username you gave them when you creaed your account
#      password        A MD5 sum of the password string
#
#    Resposes
#      nochg           Sent IP was the same that was already stored in the DDNS
#      good {ip}       String "good" followed by the IP that was sent
#      (?)             Some response for authentication / other errors
#
username="jani"
password="qwerty"
passmd5="$(echo -n ${password} | md5sum - | awk '{print $1;}')"
logfile="/var/log/dynudns.org"
datetime="$(date +"%Y-%m-%d %T")"
uri="http://api.dynu.com/nic/update"

ip="$(hostname -I | awk '{print $NF;exit}')" # eval?

uri="${uri}?myip=${ip}&username=${username}&password=${passmd5}"
# -s for silent
reply="$(curl -s ${uri})"

# log entry
echo ${datetime} ${uri} : ${reply} >> ${logfile}

# EOF
