class Config:
    class Dev:
        class DDNS:
            username        = "{{user}}"
            password        = "{{pass}}"
        class Samba:
            dummy           = "dummy"
    mode                    = "DEV"     # REL | UAT | DEV


# EOF