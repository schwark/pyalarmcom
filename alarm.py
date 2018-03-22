#!/usr/bin/python

import re
import mechanize
import argparse
import logging
import json
import sys

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
logging.basicConfig()


class AlarmDotCom(object):

	def __init__(self, username, password):
		self.username = username
		self.password = password
		self.state = 'UNKNOWN'
		self.browser = None
		self.panel_id = None
		self.logged_in = False

	def _get_browser(self):
		if not self.browser:
			br = mechanize.Browser()

			br.set_handle_equiv(True)
			#br.set_handle_gzip(True)
			br.set_handle_redirect(False)
			br.set_handle_referer(True)
			br.set_handle_robots(False)
			br.set_debug_http(logging.DEBUG == log.getEffectiveLevel())
			br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

			br.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'),
				('Accept','text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
				('Accept-Language','en-US,en;q=0.5')]
			self.browser =  br

		return self.browser


	def _login(self):
		if not self.logged_in:
			br = self._get_browser()
			response = br.open( "https://www.alarm.com/login.aspx" )
			location = response.geturl()
			content = response.read()
			session = re.search(r'\/(\(S[^\/]+)\/', location)
			if session:
				session = session.group(1)
			viewstate = re.search(r'name="__VIEWSTATE".*?value="([^"]*)"', content)
			if viewstate:
				viewstate = viewstate.group(1)
			log.debug("VIEWSTATE is  %s",viewstate)
			viewstategenerator = re.search(r'name="__VIEWSTATEGENERATOR".*?value="([^"]*)"', content)
			if viewstategenerator:
				viewstategenerator = viewstategenerator.group(1)
			log.debug("VIEWSTATEGENERATOR is %s", viewstategenerator)
			eventval = re.search(r'name="__EVENTVALIDATION".*?value="([^"]*)"', content)
			if eventval:
				eventval = eventval.group(1)
			log.debug("EVENTVALIDATION is  %s",eventval)
			post = mechanize.Request('https://www.alarm.com/web/Default.aspx',
				data={'__VIEWSTATE': viewstate, '__EVENTVALIDATION': eventval, '__VIEWSTATEGENERATOR': viewstategenerator, 'IsFromNewSite': '1', 'JavaScriptTest': '1', 'ctl00$ContentPlaceHolder1$loginform$hidLoginID': '', 'ctl00$ContentPlaceHolder1$loginform$txtUserName': self.username, 'ctl00$ContentPlaceHolder1$loginform$txtPassword': self.password, 'ctl00$ContentPlaceHolder1$loginform$signInButton': 'Logging In...', 'ctl00$bottom_footer3$ucCLS_ZIP$txtZip': 'Zip Code'}, method='POST')
			try:
				response = br.open(post)
				log.debug("Post login URL is  %s", response.geturl())
			except:
				e = sys.exc_info()[0]
				log.debug("got an error %s", e)
			self.logged_in = True
		return self.logged_in


	def _get_panel(self):
		if not self.panel_id:	
			result = self.api_call('systems/availableSystemItems')
			user_id = result['data'][0]['id']
			log.debug('user id is'+user_id)
			result = self.api_call('systems/systems/'+user_id)
			panel_id = result['data']['relationships']['partitions']['data'][0]['id']
			log.debug('panel id is '+panel_id)
			self.panel_id = panel_id

		return self.panel_id

	def api_call(self, apiUrl, apiMethod='GET', apiBody=''):
		br = self._get_browser()
		if not self.logged_in:
			self._login()

		cookiejar = br.cookiejar
		ajaxkey = None
		for cookie in cookiejar:
			if 'afg' == cookie.name:
				ajaxkey = cookie.value
		log.debug("ajaxkey is %s", ajaxkey)
		apiCall = mechanize.Request('https://www.alarm.com/web/api/'+apiUrl,data=apiBody, method=apiMethod)
		apiCall.add_header('ajaxrequestuniquekey', ajaxkey)
		apiCall.add_header('Accept', 'application/vnd.api+json')
		result = None
		try:
			response = br.open(apiCall)
			content = response.read()
			log.debug("Post command JSON is  %s", content)
			result = json.loads(content)
			log.debug(result)
		except:
			e = sys.exc_info()[0]
			log.debug("got an error %s", e)
		return result


	def refresh(self):
		return self.command('STATUS')

	def command(self, command, forceBypass=False, noEntryDelay=False, silentArming=True):
		states = ['UNKNOWN', 'DISARM', 'ARMSTAY', 'ARMAWAY']
		commands = {'ARMSTAY': '/armStay', 'ARMAWAY': '/armAway', 'DISARM': '/disarm', 'STATUS': ''}
		panel_id = self._get_panel()
		command = command.upper()

		apiUrl = 'devices/partitions/'+panel_id+commands[command]
		if('STATUS' == command):
			apiMethod = 'GET'
			apiBody = ''
		else:
			apiMethod = 'POST'
			apiBody = '{"forceBypass":'+str(forceBypass)+',"noEntryDelay":'+str(noEntryDelay)+',"silentArming":'+str(silentArming)+',"statePollOnly":false}'

		result = self.api_call(apiUrl, apiMethod, apiBody)
		currentstate = result['data']['attributes']['state']
		self.state = states[currentstate]
		panel_id = result['data']['relationships']['stateInfo']['data']['id']
		log.debug ("Current state is "+states[currentstate])
		log.debug ("panel_id is "+panel_id)
		return self.state



def main():
	parser = argparse.ArgumentParser(description='Command line interface to alarm.com panels')
	parser.add_argument('-u', '--username', metavar='username', 
						help='alarm.com username')
	parser.add_argument('-p', '--password', metavar='password',
						help='alarm.com password')
	parser.add_argument('operation', choices = ['armstay', 'armaway', 'disarm', 'status'],
						help='panel operation command: armstay, armaway, disarm or status')
	parser.add_argument('-s', '--silent', action='store_true',
						help='enable silent arming')
	parser.add_argument('-b', '--bypass', action='store_false',
						help='force bypass of open sensors')
	parser.add_argument('-n', '--nodelay', action='store_false',
						help='enable arming with no entry delay')
	args = parser.parse_args()

	alarm = AlarmDotCom(args.username, args.password)
	alarm.command(args.operation, args.bypass, args.nodelay, args.silent)


if __name__ == '__main__':
	main()



