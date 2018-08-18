#!/usr/bin/python

import re
import codecs
import mechanicalsoup
import argparse
import logging
import json
import sys

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
logging.basicConfig(filename="alarm.log")


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
			br = mechanicalsoup.StatefulBrowser(
				soup_config={'features': 'lxml'},
				raise_on_404=True,
				user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'
			)
			br.set_verbose(8)
			self.browser = br
		return self.browser


	def _login(self):
		if not self.logged_in:
			br = self._get_browser()
			response = br.open( "https://www.alarm.com/login.aspx" )
			location = br.get_url()
			content = br.get_current_page().decode("utf-8")
			session = re.search(r'\/(\(S[^\/]+)\/', location)
			if session:
				session = session.group(1)
			viewstate = re.search(r'name="__VIEWSTATE".*?value="([^"]*)"', content)
			if viewstate:
				viewstate = viewstate.group(1)
			log.debug("VIEWSTATE is %s", viewstate)
			viewstategenerator = re.search(r'name="__VIEWSTATEGENERATOR".*?value="([^"]*)"', content)
			if viewstategenerator:
				viewstategenerator = viewstategenerator.group(1)
			log.debug("VIEWSTATEGENERATOR is %s", viewstategenerator)
			eventval = re.search(r'name="__EVENTVALIDATION".*?value="([^"]*)"', content)
			if eventval:
				eventval = eventval.group(1)
			log.debug("EVENTVALIDATION is %s", eventval)
			self.logged_in = None
			try:
				postresponse = br.post('https://www.alarm.com/web/Default.aspx',
					data={'__VIEWSTATE': viewstate, '__EVENTVALIDATION': eventval, '__VIEWSTATEGENERATOR': viewstategenerator, 'IsFromNewSite': '1', 'JavaScriptTest': '1', 'ctl00$ContentPlaceHolder1$loginform$hidLoginID': '', 'ctl00$ContentPlaceHolder1$loginform$txtUserName': self.username, 'ctl00$ContentPlaceHolder1$loginform$txtPassword': self.password, 'ctl00$ContentPlaceHolder1$loginform$signInButton': 'Logging In...', 'ctl00$bottom_footer3$ucCLS_ZIP$txtZip': 'Zip Code'})
				log.debug("Post login URL is %s", postresponse.url)
				self.logged_in = True
			except:
				e = sys.exc_info()[0]
				log.debug("got an error %s", e)
		return self.logged_in


	def _get_panel(self):
		if not self.panel_id: 
			result = self.api_call('systems/availableSystemItems')
			user_id = result['data'][0]['id']
			log.debug('user id is '+user_id)
			result = self.api_call('systems/systems/'+user_id)
			panel_id = result['data']['relationships']['partitions']['data'][0]['id']
			log.debug('panel id is '+panel_id)
			self.panel_id = panel_id
		return self.panel_id

	def api_call(self, apiUrl, apiMethod='GET', apiBody=''):
		br = self._get_browser()
		if not self.logged_in:
			self._login()
		log.debug('Logged In: '+str(self.logged_in)) # True
		cookiejar = br.get_cookiejar()
		ajaxkey = None
		for cookie in cookiejar:
			# log.debug(cookie.name+': '+cookie.value)
			if 'afg' == cookie.name:
				ajaxkey = cookie.value
		log.debug("ajaxkey is %s", ajaxkey)
		result = None
		try:
			apiCall = br.request(method=apiMethod,
				url='https://www.alarm.com/web/api/'+apiUrl,
				data=apiBody,
				headers={'ajaxrequestuniquekey': ajaxkey, 'Accept': 'application/vnd.api+json', 'Content-Type': 'application/json; charset=UTF-8'}
			)
			responsecontent = apiCall.content.decode("utf-8")
			log.debug("Post command JSON is %s", responsecontent)
			result = json.loads(responsecontent)
			log.debug(result)
		except:
			log.debug('apiUrl: '+apiUrl)
			log.debug('apiBody: '+apiBody)
			e = sys.exc_info()[0]
			log.debug("got an error %s", e)
		return result


	def refresh(self):
		return self.command('STATUS')

	def disarm(self):
		return self.command('DISARM')

	def arm_stay(self, forceBypass=False, noEntryDelay=False, silentArming=True):
		return self.command('ARMSTAY', forceBypass, noEntryDelay, silentArming)

	def arm_away(self, forceBypass=False, noEntryDelay=False, silentArming=True):
		return self.command('ARMAWAY', forceBypass, noEntryDelay, silentArming)

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
			apiBody = '{"forceBypass":'+str(forceBypass).lower()+',"noEntryDelay":'+str(noEntryDelay).lower()+',"silentArming":'+str(silentArming).lower()+',"statePollOnly":false}'

		result = self.api_call(apiUrl, apiMethod, apiBody)
		currentstate = result['data']['attributes']['state']
		self.state = states[currentstate]
		panel_id = result['data']['relationships']['stateInfo']['data']['id']
		log.debug ("Current state is "+states[currentstate])
		log.debug ("panel_id is "+panel_id)
		return self.state



def main():
	parser = argparse.ArgumentParser(description='Command line interface to alarm.com panels')
	parser.add_argument('-u', '--username',
						metavar='username',
						help='alarm.com username')
	parser.add_argument('-p', '--password',
						metavar='password',
						help='alarm.com password')
	parser.add_argument('operation',
						choices = ['armstay', 'armaway', 'disarm', 'status'],
						help='panel operation command: armstay, armaway, disarm or status')
	parser.add_argument('-s', '--silent',
						action='store_true',
						help='enable silent arming')
	parser.add_argument('-b', '--bypass',
						action='store_true',
						help='force bypass of open sensors')
	parser.add_argument('-n', '--nodelay',
						action='store_true',
						help='enable arming with no entry delay')
	#production:
	args = parser.parse_args()
	#development:
	# args = parser.parse_args(['status','--username=username','--password=password'])

	alarm = AlarmDotCom(args.username, args.password)

	print("current status is " + alarm.command(args.operation, args.bypass, args.nodelay, args.silent))


if __name__ == '__main__':
	main()



