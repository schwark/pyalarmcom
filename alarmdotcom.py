import logging
import requests
from time import time
import re
import argparse

log = logging.getLogger("alarmdotcom")
log.setLevel(logging.DEBUG)

class Browser:    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'})
        self.formre = re.compile(r'<input.*?name=[\'"]([^\'"]+).*?value=[\'"]([^\'"]*)', re.I)
 
    def extract_vars(self, response, vars):
        values = self.formre.findall(response.text)
        for name, value in values:
            if name in vars:
                vars[name] = value
        return vars

    def request(self, url, **kwargs):
        method = 'GET'
        if 'method' in kwargs and kwargs['method']:
            method = kwargs['method']
            del kwargs['method']
        response = self.session.request(method, url, **kwargs)
        return response
    
    
class AlarmDotCom:
    STATES = ['disarm', 'armStay', 'armAway']
    SESSION_TIMEOUT = 360
    
    def __init__(self, username=None, password=None, panel_id=None) -> None:
        self.browser = Browser()
        self.reload = False
        self.user_id = None
        self.system_id = None
        self.panel_id = panel_id
        self.username = username
        self.password = password
        self.afg = None
        self.last_request = None
                    
    def update_state(self):
        cookies = requests.utils.dict_from_cookiejar(self.browser.session.cookies)
        if('afg' in cookies):
            afg = cookies['afg']
            if(afg and self.afg != afg):
                self.afg = afg
        
    def set_panel_id(self, panel_id):
        if(panel_id):
            self.panel_id = str(panel_id)
        log.debug("saved panel id")
        
    def set_system_id(self, system_id):
        if(system_id):
            self.system_id = str(system_id)
        log.debug("saved system id")
        
    def set_user_id(self, user_id):
        if(user_id):
            self.user_id = str(user_id)
        log.debug("saved user id")
        
    def init(self):
        if(self.afg and not self.panel_id):
            json = self.authenticated_json('https://www.alarm.com/web/api/identities')
            if json:
                user_id = json['data'][0]['id']
                system_id = json['data'][0]['relationships']['selectedSystem']['data']['id']
                log.debug(str(user_id)+", "+str(system_id))
                self.set_user_id(user_id)
                self.set_system_id(system_id)
                json = self.authenticated_json('https://www.alarm.com/web/api/systems/systems/'+self.system_id)
                if json:
                    panel_id = json['data']['relationships']['partitions']['data'][0]['id']
                    self.set_panel_id(panel_id)
            
    def login(self):
        response = None
        if(self.username and self.password):
            params = {
                '__PREVIOUSPAGE' : '',
			  	'__VIEWSTATE' : '',
			  	'__VIEWSTATEGENERATOR' : '',
			  	'__EVENTVALIDATION' : '',
			  	'IsFromNewSite' : '1',
			  	'JavaScriptTest' :  '1',
			  	'ctl00$ContentPlaceHolder1$loginform$hidLoginID' : '',
				'ctl00$ContentPlaceHolder1$loginform$txtUserName': self.username,
			  	'txtPassword' : self.password,
			  	'ctl00$ContentPlaceHolder1$loginform$signInButton': 'Login'
            }
            response = self.browser.request("https://www.alarm.com/login.aspx")
            if(200 == response.status_code):
                vars = {
                    '__PREVIOUSPAGE' : '',
                    '__VIEWSTATE' : '',
                    '__VIEWSTATEGENERATOR' : '',
                    '__EVENTVALIDATION' : ''
                }            
                vars = self.browser.extract_vars(response, vars)
                params = {**params, **vars}
                response = self.browser.request("https://www.alarm.com/web/Default.aspx", data=params, method='POST', headers={'Referer':'https://alarm.com/login.aspx'})
                if(200 == response.status_code):
                    self.update_state()
        return response and response.url == "https://www.alarm.com/web/system/"
    
    def authenticated_json(self, url, **kwargs):
        result = None
        for i in [1,2]:
            authenticated =  self.last_request and (time() - self.last_request) < self.SESSION_TIMEOUT
            if(not authenticated):
                authenticated = self.login()
            if(authenticated):
                json_headers = {'Accept': 'application/vnd.api+json', 'AjaxRequestUniqueKey': self.afg, 'Referer': 'https://www.alarm.com/web/system/'}
                headers = {}
                if 'headers' in kwargs and kwargs['headers']:
                    headers = kwargs['headers']
                headers = {**headers, **json_headers}
                kwargs['headers'] = headers
                response = self.browser.request(url, **kwargs)
                if(200 == response.status_code):
                    result = response.json()
                    self.last_request = time()
                    break
                if(403 == response.status_code):
                    self.last_request = None
        return result
    
    def command(self, command, flags={}):
        default_flags = {'silent': True, 'bypass': False, 'nodelay': False}
        flags = {**default_flags, **flags}
        states = self.STATES
        result = None
        if(not self.afg):
            self.login()
        if(not self.panel_id):
            self.init()
        url_base = 'https://www.alarm.com/web/api/devices/partitions/'+self.panel_id
        commands = {
            states[0]:  {'method': 'POST', 'urlext': '/'+states[0], 'resultfunc': lambda x: bool(x), 'json': {'statePollOnly': False}},
            states[1]: {'method': 'POST', 'urlext': '/'+states[1], 'resultfunc': lambda x: bool(x), 'json': {'silentArming': flags['silent'], 'forceBypass': flags['bypass'], 'noEntryDelay': flags['nodelay'], 'statePollOnly': False}},
            states[2]: {'method': 'POST', 'urlext': '/'+states[2], 'resultfunc': lambda x: bool(x), 'json': {'silentArming': flags['silent'], 'forceBypass': flags['bypass'], 'noEntryDelay': flags['nodelay'], 'statePollOnly': False}},
            'status': {'method': 'GET', 'urlext': '', 'resultfunc': lambda x: states[int(x['data']['attributes']['state'])-1], 'json': None}
        }
        args = {'method': commands[command]['method'], 'json': commands[command]['json']}
        log.info('params are '+str(args['json']))
        json = self.authenticated_json(url_base+commands[command]['urlext'], **(args))
        if json:
            result = commands[command]['resultfunc'](json)
            self.update_state()
        return result
    
    def arm_stay(self, flags={}):
        return self.command('armStay', flags)

    def arm_away(self, flags={}):
        return self.command('armAway', flags)

    def disarm(self):
        return self.command('disarm')

    def status(self):
        return self.command('status')

def main():
    parser = argparse.ArgumentParser(description='Command line interface to alarm.com panels')
    parser.add_argument('-u', '--username', metavar='username', 
                        help='alarm.com username')
    parser.add_argument('-p', '--password', metavar='password',
                        help='alarm.com password')
    parser.add_argument('operation', choices = ['arm_stay', 'arm_away', 'disarm', 'status'],
                        help='panel operation command: arm_stay, arm_away, disarm or status')
    parser.add_argument('-s', '--silent', action='store_true',
                        help='enable silent arming', default=True)
    parser.add_argument('-b', '--bypass', action='store_true',
                        help='force bypass of open sensors', default=False)
    parser.add_argument('-n', '--nodelay', action='store_true',
                        help='enable arming with no entry delay', default=False)
    args = parser.parse_args()

    alarm = AlarmDotCom(args.username, args.password)
    print("current status is "+alarm.command(args.operation, {'bypass': args.bypass, 'nodelay': args.nodelay, 'silent': args.silent}))

if __name__ == '__main__':
	main()