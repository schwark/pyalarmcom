#!/usr/bin/python

import re
import mechanize
import argparse
import logging

def main():
	parser = argparse.ArgumentParser(description='Command line interface to alarm.com panels')
	parser.add_argument('-u', '--username', metavar='username', 
						help='alarm.com username')
	parser.add_argument('-p', '--password', metavar='password',
						help='alarm.com password')
	parser.add_argument('operation', choices = ['armstay', 'armaway', 'disarm'],
						help='panel operation command: armstay, armaway or disarm')
	parser.add_argument('-s', '--silent', action='store_true',
						help='enable silent arming')
	parser.add_argument('-b', '--bypass', action='store_false',
						help='force bypass of open sensors')
	parser.add_argument('-n', '--nodelay', action='store_false',
						help='enable arming with no entry delay')
	args = parser.parse_args()

	commands = {'armstay': 'armStay', 'armaway': 'armAway', 'disarm': 'disarm'}
	if args.operation:
		args.operation = commands[args.operation.lower()]
	execute_command(args)

def execute_command(args):
	br = get_browser()
	login(br, args)
	panel_id = get_panel(br)
	api_call(br, panel_id, args)

def get_browser():
	br = mechanize.Browser()

	br.set_handle_equiv(True)
	#br.set_handle_gzip(True)
	br.set_handle_redirect(True)
	br.set_handle_referer(True)
	br.set_handle_robots(False)
	br.set_debug_http(True)
	br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

	br.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'),
	('Accept','text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
			('Accept-Language','en-US,en;q=0.5')]

	return br


def login(br, args):
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
		data={'__VIEWSTATE': viewstate, '__EVENTVALIDATION': eventval, '__VIEWSTATEGENERATOR': viewstategenerator, 'IsFromNewSite': '1', 'JavaScriptTest': '1', 'ctl00$ContentPlaceHolder1$loginform$hidLoginID': '', 'ctl00$ContentPlaceHolder1$loginform$txtUserName': args.username, 'ctl00$ContentPlaceHolder1$loginform$txtPassword': args.password, 'ctl00$ContentPlaceHolder1$loginform$signInButton': 'Logging In...', 'ctl00$bottom_footer3$ucCLS_ZIP$txtZip': 'Zip Code'}, method='POST')
	response = br.open(post)
	log.debug("Post login URL is  %s", response.geturl())

def get_panel(br):	
	response = br.open('https://www.alarm.com/web/History/EventHistory.aspx')
	content = response.read()
	dataunit = re.search(r'data-unit-id="(\d+)"', content)
	if dataunit:
		dataunit = dataunit.group(1)
	log.debug("DATAUNITID is  %s", dataunit)
	extension = re.search(r'<option value="(\-\d+)">Panel<\/option>', content)
	if extension:
		extension = extension.group(1)
	log.debug("panel extension is  %s",extension)
	return dataunit+extension


def api_call(br, panel_id, args):
	cookiejar = br.cookiejar
	ajaxkey = None
	for cookie in cookiejar:
		if 'afg' == cookie.name:
			ajaxkey = cookie.value
	if ajaxkey:
		log.debug('ajaxkey is  %s', ajaxkey)
		apiCall = mechanize.Request('https://www.alarm.com/web/api/devices/partitions/'+panel_id+'/'+args.operation,data='{"forceBypass":'+str(args.bypass)+',"noEntryDelay":'+str(args.nodelay)+',"silentArming":'+str(args.silent)+',"statePollOnly":false}', method='POST')
		apiCall.add_header('ajaxrequestuniquekey', ajaxkey)
		apiCall.add_header('Accept', 'application/vnd.api+json')
		response = br.open(apiCall)
		content = response.read()
		log.debug("Post command JSON is  %s", content)

if __name__ == '__main__':
	log = logging.getLogger(__name__)
	log.setLevel(logging.DEBUG)
	logging.basicConfig()
	main()