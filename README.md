# pyalarmcom

* command line interface to alarm.com panels
* python "api" to alarm.com panels

```bash
usage: alarm.py [-h] [-u username] [-p password] [-s] [-b] [-n]
                {armstay,armaway,disarm,status}

Command line interface to alarm.com panels

positional arguments:
  {armstay,armaway,disarm,status}
                        panel operation command: armstay, armaway, disarm or
                        status

optional arguments:
  -h, --help            show this help message and exit
  -u username, --username username
                        alarm.com username
  -p password, --password password
                        alarm.com password
  -s, --silent          enable silent arming
  -b, --bypass          force bypass of open sensors
  -n, --nodelay         enable arming with no entry delay
```
