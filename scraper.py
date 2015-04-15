# -*- coding: utf-8 -*-

import mechanize
import json
import datetime
import turbotlib
import httplib
import urllib2
import urllib
import turbotlib
#import xlwt
import re
from bs4 import BeautifulSoup
import cookielib
from requests import session

# Banktype is also used to check progress and restart at the beginning of a bank type if the connection is interrupted
bankType = ""
# indexing to check if organization has already been printed out if connection is interrupted
organizations = []

def getChunk(stream, delimiter, identifier):
	newChunk = []
	chunks = stream.split(delimiter)
	for ch in chunks:
		if ch.find(identifier) is not -1:
			return ch

def unwrap(response, identifier):
	try:
		r1 = getChunk(response, "<fragment><![CDATA[", identifier)
	except:
		turbotlib.log("Didn't find fragment")
		return None
	try: 
		r2 = getChunk(r1, "]]></fragment>",identifier)
		return r2
	except:
		turbotlib.log("Didn't find fragment")
		return None


def extractList(html):
	theList = []
	soup = BeautifulSoup(html)
	p = soup.find("select",id="bnConnectionTemplate:r1:0:s11:registerType::content").find_all('option')
	for n in range(0,len(p)):
		txt = p[n].contents[0].strip().decode('utf8')
		if txt.find("Select One") is -1:
			theList.append(txt)
	return theList

def printResult(company, number, status, address):
	#check if organization data has already been printed
	if number not in organizations:
		# hold on to the licence number in case connection interrupts
		organizations.append(number)
		if address.find("Address Unknown") is not -1:
			address = ""
		data = {"number": number,
			"company_name": company,
			"type" : bankType.encode('latin-1'),
			"status" : status.encode('latin-1'),
			"message": "",
			"address" : address.encode('latin-1'),
			"address_country" : country,
			"sample_date": datetime.datetime.now().isoformat(),
			"source_url": start_url
			}
		print json.dumps(data)

def parseResult(html):
	# print html
	soup = BeautifulSoup(html)
	# For some horrible reason, if there is only one search result in the SMSF Auditor search, it goes straight to details, which is a completely different format.
	# Is a detail view?
	detailTable = soup.find(class_="detailTable")
	if detailTable is None:
		p = soup.find(class_="af_table_data-table").find_all('tr')

		for n in range(0,len(p)):
			company = p[n].find("a").contents[0].strip().replace("*","").encode('latin-1')
			columns = p[n].find_all("td")
			number = columns[2].span.contents[0].strip().encode('latin-1')
			status = columns[4].span.contents[0].strip()
			address = columns[5].span.contents[0].strip()
			printResult(company, number, status, address)
		# is there a next page?
		next = soup.find(True, {'class':['pageNavNextButton', 'p_AFDisabled']})
		if next is None:
			return True
		else:
			return False
		return next
	else:
		company = detailTable.find("th", text=re.compile("Name")).next_sibling.contents[0].strip().encode('latin-1')
		number = detailTable.find("th", text=re.compile("Registration number")).next_sibling.contents[0].strip().encode('latin-1')
		status = detailTable.find("th", text=re.compile("Status")).next_sibling.contents[0].strip().encode('latin-1')
		address = detailTable.find("th", text=re.compile("practice address")).next_sibling.contents[0].strip().encode('latin-1')
		printResult(company, number, status, address)	

def openPage(browser, visit, controls, identifier, parse):
	browser.form.set_all_readonly(False)
	for cname in controls:
		c = controls[cname]
		if c is None:
			for control in browser.form.controls:
				if control.name == cname:
					browser.form.controls.remove(control)
	for cname in controls:
		c = controls[cname]
		if c is not None: 
			exists = True
			try:
				find_ctrl = browser.form.find_control(cname)				
			except mechanize._form.ControlNotFoundError:
				exists = False
			if exists is True and cname.find('bnConnectionTemplate:r1:0:s11:selectedStatuses') is -1:
				#find_ctrl.readonly = False
				try:
					#browser.form[cname] = c
					find_ctrl.value = c
				except Exception as e:
					#print e
					try: 
						#print find_ctrl
					except:
						turbotlib.log("did not find form input " + cname)

					#turbotlib.log("did not find form input " + cname)
					try: 
						#print find_ctrl
					except:
						turbotlib.log("did not find form input " + cname)
			else:
				if cname.find('bnConnectionTemplate:r1:0:s11:selectedStatuses') is not -1:
					browser.form.new_control('hidden','bnConnectionTemplate:r1:0:s11:selectedStatuses', {'value': c, 'checked': True})
				else:
					browser.form.new_control('hidden',cname, {'value': c})
	browser.form.fixup()
	turbotlib.log("Starting Request...")
	try:
		if visit is True:
			response = browser.open(browser.form.click(), timeout = 60)
			#print urllib.unquote(browser.request.get_data()).decode('utf8')
		else:
			response = browser.open_novisit(browser.form.click(), timeout = 60)
		response_content = response.read()
		#print response_content
	except:
		turbotlib.log("Bad Request. Starting over " + bankType + " Category")
		return False
	response.close()
	turbotlib.log("Response Received...")
	if parse is True:
		html = unwrap(response_content, identifier)
		if html is not None:
			result = parseResult(html)
			return result
		else:
			#print response_content
			return None
	return None


###########################


turbotlib.log("Starting run...") # Optional debug logging

country = "Australia"


# First, get the list of categories from the form search dropdown
user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
headers = { 
'User-Agent' : user_agent,
'Accept' : "*/*"
}
start_url = "https://connectonline.asic.gov.au/RegistrySearch/faces/landing/ProfessionalRegisters.jspx"
url_domain = 'https://connectonline.asic.gov.au'

browser = mechanize.Browser()
browser.set_handle_robots(False)   # ignore robots
browser.set_handle_refresh(False)  # can sometimes hang without this
browser.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'),
('Connection' , 'keep-alive')]

response = browser.open(start_url) 
response_content = response.read()
theList = extractList(response_content)

# we don't automatically loop through each category because we will want to repeat the category if it throws an error somewhere in the middle
counter = 0
while counter < len(theList): 
	bankType = theList[counter]
	turbotlib.log("Starting scraping for " + bankType + " Category")
	# Set register type and get statuses
	browser = mechanize.Browser()
	browser.set_handle_robots(False)   # ignore robots
	browser.set_handle_refresh(False)  # can sometimes hang without this
	browser.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36')]

	# Set Register Type in the form
	response = browser.open(start_url) 
	response_content = response.read()
	formcount=0
	for frm in browser.forms():  
	  if str(frm.attrs["name"])=="f1":
	    break
	  formcount=formcount+1
	browser.select_form(nr=formcount)
	browser.addheaders = [('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'),
	('Accept' , '*/*'),
	('Accept-Language' , 'en-US,en;q=0.8'),
	('Content-Type' , 'application/x-www-form-urlencoded; charset=UTF-8'),
	('Adf-Ads-Page-Id' , '1'),
	('Adf-Rich-Message' , 'true'),
	('Connection' , 'keep-alive'),
	('Origin' , 'https://connectonline.asic.gov.au'),
	('Referer' , browser.form.action)]

	controls = {
		'bnConnectionTemplate:r1:0:s11:it1' : 'Licence or Registration Number',
		'bnConnectionTemplate:r1:0:s11:it2' : '*',
		'bnConnectionTemplate:r1:0:s11:registerType' : [str(counter)],
		'bnConnectionTemplate:pt_s5:templateSearchTypesListOfValuesId' : ['0'],
		'bnConnectionTemplate:pt_s5:searchSurname' : "",
		'bnConnectionTemplate:pt_s5:searchFirstName' : "",
		'bnConnectionTemplate:pt_s5:templateSearchInputText' : 'Name or Number',
		'bnConnectionTemplate:pt_s5:searchName' : "",
		'bnConnectionTemplate:pt_s5:searchNumber' : "",
		'bnConnectionTemplate:r1:0:s11:selectAllRoles' : ['t'],
		'oracle.adf.view.rich.PROCESS' : "bnConnectionTemplate:r1:0:s11:registerType",
		'event' : "bnConnectionTemplate:r1:0:s11:registerType",
		'event.bnConnectionTemplate:r1:0:s11:registerType' : '<m xmlns="http://oracle.com/richClient/comm"><k v="autoSubmit"><b>1</b></k><k v="suppressMessageShow"><s>true</s></k><k v="type"><s>valueChange</s></k></m>'
	}
	openPage(browser, False, controls, "af_panelGroupLayout", False)

	#Now that register type is set, you can search for everything (*) in category (counter)
	turbotlib.log("search for everything (*) in category")
	controls = {
		'event.bnConnectionTemplate:r1:0:s11:registerType' : None,
		'event' : None,
		'oracle.adf.view.rich.PROCESS' : None,
		'bnConnectionTemplate:r1:0:s11:selectedStatuses' : None,
		'bnConnectionTemplate:r1:0:s11:it2' : '*',
		'bnConnectionTemplate:r1:0:s11:registerType' : [str(counter)],
		'bnConnectionTemplate:pt_s5:templateSearchTypesListOfValuesId' : ['0'],
		'bnConnectionTemplate:pt_s5:searchSurname' : "",
		'bnConnectionTemplate:pt_s5:searchFirstName' : "",
		'bnConnectionTemplate:pt_s5:templateSearchInputText' : 'Name or Number',
		'bnConnectionTemplate:pt_s5:searchName' : "",
		'bnConnectionTemplate:pt_s5:searchNumber' : "",
		'bnConnectionTemplate:r1:0:s11:it1' : 'Licence or Registration Number',
		'bnConnectionTemplate:r1:0:s11:registerType' : ['1'],
		'bnConnectionTemplate:r1:0:s11:selectAllRoles' : ['t'],
		'bnConnectionTemplate:r1:0:s11:selectedStatuses:0' : 0,
		'bnConnectionTemplate:r1:0:s11:selectedStatuses:1' : 1,
		'bnConnectionTemplate:r1:0:s11:selectedStatuses:2' : 2,
		'oracle.adf.view.rich.RENDER' : "bnConnectionTemplate:r1",
		'oracle.adf.view.rich.PROCESS' : "bnConnectionTemplate:r1",
		'event' : "bnConnectionTemplate:r1:0:s11:searchButton",
		'event.bnConnectionTemplate:r1:0:s11:searchButton' : '<m xmlns="http://oracle.com/richClient/comm"><k v="type"><s>action</s></k></m>'
	}
	openPage(browser, False, controls, "af_table_data-table", False)

	# Change from 10 results per page to 50 results per page
	turbotlib.log("Change from 10 results per page to 50 results per page")

	controls = {
		'bnConnectionTemplate:pt_s5:templateSearchTypesListOfValuesId':['0'],
		'bnConnectionTemplate:pt_s5:searchSurname' : '',
		'bnConnectionTemplate:pt_s5:searchFirstName' : '',
		'bnConnectionTemplate:pt_s5:templateSearchInputText' : 'Name or Number',
		'bnConnectionTemplate:pt_s5:searchName' : '',
		'bnConnectionTemplate:pt_s5:searchNumber' : '',
		'bnConnectionTemplate:r1:1:mainContentWrapperFragment:totalItemsSelected': 0,
		'bnConnectionTemplate:r1:1:mainContentWrapperFragment:searchTypesLovId':0,
		'bnConnectionTemplate:r1:1:mainContentWrapperFragment:searchSurname' : '',
		'bnConnectionTemplate:r1:1:mainContentWrapperFragment:searchFirstName' : '',
		'bnConnectionTemplate:r1:1:mainContentWrapperFragment:searchForTextId' : '',
		'bnConnectionTemplate:r1:1:mainContentWrapperFragment:searchForName' : '',
		'bnConnectionTemplate:r1:1:mainContentWrapperFragment:searchForNumber' : '',
		'bnConnectionTemplate:r1:1:mainContentWrapperFragment:fetchsize' : 0,
		'bnConnectionTemplate:r1:1:mainContentWrapperFragment:fetchsizeTwin' : 2,
		'org.apache.myfaces.trinidad.faces.FORM' : 'f1',
		'oracle.adf.view.rich.DELTAS' : '{bnConnectionTemplate:r1:1:mainContentWrapperFragment:t1={viewportSize=11}}',
		'event' : 'bnConnectionTemplate:r1:1:mainContentWrapperFragment:fetchsize',
		'event.bnConnectionTemplate:r1:1:mainContentWrapperFragment:fetchsize' : '<m xmlns="http://oracle.com/richClient/comm"><k v="autoSubmit"><b>1</b></k><k v="suppressMessageShow"><s>true</s></k><k v="type"><s>valueChange</s></k></m>',
		'oracle.adf.view.rich.PROCESS' : 'bnConnectionTemplate:r1:1:mainContentWrapperFragment:fetchsize'
	}

	openPage(browser, False, controls, "af_table_data-table", True)

	# Paginate
	paginate = True
	gotSomething = False
	while paginate is not None and paginate is not False:
		turbotlib.log("Retrieve Next Page")
		controls = {
			'bnConnectionTemplate:r1:0:s11:it2' : None,
			'bnConnectionTemplate:r1:0:s11:it1' : None,
			'bnConnectionTemplate:r1:0:s11:registerType' : None,
			'bnConnectionTemplate:r1:0:s11:selectAllRoles' : None,
			'event.bnConnectionTemplate:r1:0:s11:searchButton' : None,
			'oracle.adf.view.rich.RENDER' : None,
			'bnConnectionTemplate:r1:0:s11:selectedStatuses' : None,
			"bnConnectionTemplate:pt_s5:templateSearchTypesListOfValuesId" : [str(counter)],
			"bnConnectionTemplate:pt_s5:searchSurname" : "",
			"bnConnectionTemplate:pt_s5:searchFirstName" : "",
			"bnConnectionTemplate:pt_s5:templateSearchInputText" : "Name or Number",
			"bnConnectionTemplate:pt_s5:searchName" : "",
			"bnConnectionTemplate:pt_s5:searchNumber" : "",
			"bnConnectionTemplate:r1:1:mainContentWrapperFragment:totalItemsSelected" : "0",
			"bnConnectionTemplate:r1:1:mainContentWrapperFragment:generalSearchPanelFragment:s4:searchTypesLovId" : "0", 
			"bnConnectionTemplate:r1:1:mainContentWrapperFragment:generalSearchPanelFragment:s4:searchSurname" : "",
			"bnConnectionTemplate:r1:1:mainContentWrapperFragment:generalSearchPanelFragment:s4:searchFirstName" : "",
			"bnConnectionTemplate:r1:1:mainContentWrapperFragment:generalSearchPanelFragment:s4:searchForTextId" : "",
			"bnConnectionTemplate:r1:1:mainContentWrapperFragment:generalSearchPanelFragment:s4:searchForName" : "",
			"bnConnectionTemplate:r1:1:mainContentWrapperFragment:generalSearchPanelFragment:s4:searchForNumber" : "",
			"bnConnectionTemplate:r1:1:mainContentWrapperFragment:fetchsize" :"2",
			"bnConnectionTemplate:r1:1:mainContentWrapperFragment:fetchsizeTwin" :"2",
			"org.apache.myfaces.trinidad.faces.FORM" : "f1",
			"oracle.adf.view.rich.DELTAS" : "{bnConnectionTemplate:r1:1:mainContentWrapperFragment:t1={viewportSize=51}}",
			"event":"bnConnectionTemplate:r1:1:mainContentWrapperFragment:pagingNextButtonTwin",
			"event.bnConnectionTemplate:r1:1:mainContentWrapperFragment:pagingNextButtonTwin" : '<m xmlns="http://oracle.com/richClient/comm"><k v="type"><s>action</s></k></m>',
			"oracle.adf.view.rich.PROCESS" : "bnConnectionTemplate:r1"
		}
		paginate = openPage(browser, False, controls, "af_table_data-table", True)
		if paginate is not False:
			gotSomething = True
		turbotlib.log("Done Retrieving Next Page")
	if paginate is not False and gotSomething is True:
		counter = counter + 1
	browser.close()

##################

# Second Scraper Section for endpoint: https://connectonline.asic.gov.au/RegistrySearch/faces/landing/SearchSmsfRegister.jspx

start_url = "https://connectonline.asic.gov.au/RegistrySearch/faces/landing/SearchSmsfRegister.jspx"

# Set register type and get statuses
for counter in range(97,122):
	#chr(counter) 
	browser = mechanize.Browser()
	browser.set_handle_robots(False)   # ignore robots
	browser.set_handle_refresh(False)  # can sometimes hang without this
	browser.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36')]
	bankType = "SMSF Auditor"
	response = browser.open(start_url) 
	response_content = response.read()
	formcount=0
	for frm in browser.forms():  
	  if str(frm.attrs["name"])=="f1":
	    break
	  formcount=formcount+1
	browser.select_form(nr=formcount)
	browser.addheaders = [('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'),
	('Accept' , '*/*'),
	('Accept-Language' , 'en-US,en;q=0.8'),
	('Content-Type' , 'application/x-www-form-urlencoded; charset=UTF-8'),
	('Adf-Ads-Page-Id' , '1'),
	('Adf-Rich-Message' , 'true'),
	('Connection' , 'keep-alive'),
	('Origin' , 'https://connectonline.asic.gov.au'),
	('Referer' , browser.form.action)]

	controls = {
		'bnConnectionTemplate:pt_s5:templateSearchTypesListOfValuesId' : 0,
		'bnConnectionTemplate:pt_s5:searchSurname': '',
		'bnConnectionTemplate:pt_s5:searchFirstName' : '',
		'bnConnectionTemplate:pt_s5:templateSearchInputText' : 'Name or Number',
		'bnConnectionTemplate:pt_s5:searchName' : '',
		'bnConnectionTemplate:pt_s5:searchNumber' : '',
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchTypesLovId' : ['1'],
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchSurname' : '',
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchFirstName' : '',
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchForName' : '',
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchForNumber' : 'Number',
		#'org.apache.myfaces.trinidad.faces.FORM' : 'f1',
		'event' : 'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchTypesLovId',
		'event.bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchTypesLovId' : '<m xmlns="http://oracle.com/richClient/comm"><k v="autoSubmit"><b>1</b></k><k v="suppressMessageShow"><s>true</s></k><k v="type"><s>valueChange</s></k></m>',
		'oracle.adf.view.rich.PROCESS' : 'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchTypesLovId'
	}
	organizations = []

	openPage(browser, False, controls, "af_panelGroupLayout", False)

	#turbotlib.log("Starting scraping for SMSF Auditors with letter " + chr(counter))



	#for counter in range(97,122):
	#
	#	turbotlib.log("Starting scraping for SMSF Auditors with letter " + chr(counter))
	#	controls = {
	#		'bnConnectionTemplate:pt_s5:templateSearchTypesListOfValuesId' : 0,
	#		'bnConnectionTemplate:pt_s5:searchSurname' : '',
	#		'bnConnectionTemplate:pt_s5:searchFirstName' : '',
	#		'bnConnectionTemplate:pt_s5:templateSearchInputText' : 'Name or Number',
	#		'bnConnectionTemplate:pt_s5:searchName' : '',
	#		'bnConnectionTemplate:pt_s5:searchNumber' : '',
	#		'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchForTextId' : chr(counter-1),
	#		'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchTypesLovId' : ['1'],
	#		'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchSurname' : '',
	#		'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchFirstName' : '',
	#		'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchForName' : chr(counter),
	#		'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchForNumber' : 'Number',
	#		#'org.apache.myfaces.trinidad.faces.FORM' : 'f1',
	#		#'javax.faces.ViewState:!-zbzlqt7va' : '',
	#		'oracle.adf.view.rich.RENDER' : 'bnConnectionTemplate:r1',
	#		'event' : 'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchButtonId',
	#		'event.bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchButtonId' : '<m xmlns="http://oracle.com/richClient/comm"><k v="type"><s>action</s></k></m>',
	#		'oracle.adf.view.rich.PROCESS' : 'bnConnectionTemplate:r1'
	#	}
	#	openPage(browser, False, controls, "af_table_data-table", False)
	#for counter in range(97,122):
	turbotlib.log("Starting scraping for SMSF Auditors with letter " + chr(counter))
	#chr(counter)
	controls = {
	'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchTypesLovId' : None,
	'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchSurname' : None,
	'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchFirstName' : None,
	'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchForName' : None,
	'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchForNumber' : None,
	'event.bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchTypesLovId' : None,
		'bnConnectionTemplate:pt_s5:templateSearchTypesListOfValuesId' : 0,
		'bnConnectionTemplate:pt_s5:searchSurname' : '',
		'bnConnectionTemplate:pt_s5:searchFirstName' : '',
		'bnConnectionTemplate:pt_s5:templateSearchInputText' : 'Name or Number',
		'bnConnectionTemplate:pt_s5:searchName' : '',
		'bnConnectionTemplate:pt_s5:searchNumber' : '',
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchTypesLovId' : 1,
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchSurname' : '',
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchFirstName' : '',
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchForName' : chr(counter),
		'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchForNumber' : '',
		'oracle.adf.view.rich.RENDER' : 'bnConnectionTemplate:r1',
		'event' : 'bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchButtonId',
		'event.bnConnectionTemplate:r1:searchPanelLanding:dc1:s1:searchButtonId' : '<m xmlns="http://oracle.com/richClient/comm"><k v="type"><s>action</s></k></m>',
		'oracle.adf.view.rich.PROCESS' : 'bnConnectionTemplate:r1'
	}
	openPage(browser, False, controls, "af_table_data-table", True)

	# Paginate
	paginate = True
	while paginate is not None and paginate is not False:
		controls = {
			'bnConnectionTemplate:pt_s5:templateSearchTypesListOfValuesId' : 0,
			'bnConnectionTemplate:pt_s5:searchSurname' : '',
			'bnConnectionTemplate:pt_s5:searchFirstName' : '',
			'bnConnectionTemplate:pt_s5:templateSearchInputText' : 'Name or Number',
			'bnConnectionTemplate:pt_s5:searchName' : '',
			'bnConnectionTemplate:pt_s5:searchNumber' : '',
			'bnConnectionTemplate:r1:1:totalItemsSelected' : 0,
			'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchTypesLovId' : 1,
			'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchSurname' : '',
			'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchFirstName' : '',
			'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchForTextId' : chr(counter),
			'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchForName' : chr(counter),
			'bnConnectionTemplate:r1:generalSearchPanelFragment:s4:searchForNumber' : '',
			'bnConnectionTemplate:r1:1:fetchsize' : 0,
			'bnConnectionTemplate:r1:1:fetchsizetwin' : 0,
			'org.apache.myfaces.trinidad.faces.FORM' : 'f1',
			'oracle.adf.view.rich.DELTAS' : '{bnConnectionTemplate:r1:1:t1={viewportSize=4}}',
			'event' : 'bnConnectionTemplate:r1:1:pagingNextButtonTwin',
			'event.bnConnectionTemplate:r1:1:pagingNextButtonTwin' : '<m xmlns="http://oracle.com/richClient/comm"><k v="type"><s>action</s></k></m>',
			'oracle.adf.view.rich.PROCESS' : 'bnConnectionTemplate:r1'
		}
		paginate = openPage(browser, False, controls, "af_table_data-table", True)



