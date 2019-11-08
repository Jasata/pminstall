# Config.py
#       Config.Dev.DDNS
#           You meed to create a Dynu DNS account and create DDNS record.
#           Visit Dynu DNS site for details.
#
#           .username       As per Dynu DNS account credentials
#           .password       As per Dynu DNS account credentials
#
#
#       Config.Mode
#           Instance mode. If you deviate from the ["DEV", "UAT", "PRD"] list,
#           you MUST update 'install.py' to match. Also 'writesd.py' script
#           assumed that string "DEV" is used for development mode instances.
#           (See dev unit specific details at the latter half of the script).
#           Otherwise the script is tolerant to any values and will simply
#           write whatever is selected into '/boot/install.config' -file.
#
#           .default        Must be one of the values in .options
#           .options        List of allowed values to choose from
#           .selected       Will be created by 'writesd.py'
#
class Config:
    class Dev:
        class DDNS:
            username        = "<user>"
            password        = "<pass>"
    class Mode:
        default             = "DEV"     # (PRD | UAT | DEV) as default
        options             = ["DEV", "UAT", "PRD"]
        # selected          will be set in the script


# EOF