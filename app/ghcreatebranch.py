# from https://gist.github.com/auwsome/123ae1f493dfd9b08434

def createBranch(NEW_BRANCH_NAME=None, HASH_TO_BRANCH_FROM=None, targetuser=None, repo=None,
				targetbranch=None, username=None, password=None, baseurl='https://api.github.com'):
				
	import urllib, urllib2, json
	import getpass, base64

	if username is None:
		username = raw_input('Username: ')
	if targetuser is None:
		username = raw_input('targetuser: ')
	if repo is None:
		repo = raw_input('repo: ')
	if password is None:
		password = getpass.getpass()

	data = {
	  "ref": 'refs/heads/'+NEW_BRANCH_NAME,
	  "sha": HASH_TO_BRANCH_FROM
	}
	#data = {"ref": "refs/heads/test4", "sha": "9b5b208fb7e12c69e33b27f249706a1c540d6c1e"}
	#print data
	datajson = json.dumps(data)
	#print datajson

	#suburl = 'repos/{user}/{repo}/pulls'.format(user=targetuser, repo=repo)
	suburl = 'repos/%s/%s/git/refs/heads' % (targetuser, repo)
	url = urllib.basejoin(baseurl, suburl)
	#print url
	
	req = urllib2.Request(url)
	#req.add_data(datajson)
	req = urllib2.Request("https://api.github.com/repos/%s/%s/git/refs" % (username, repo))

	base64string = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
	req.add_header("Authorization", "Basic "+base64string) 
	#token = <token> ###########################################
	#req.add_header("Authorization", "token %s" % token)
	
	result = urllib2.urlopen(req, datajson)
	result = json.loads('\n'.join(result.readlines()))
	print result
	
	try:
		response = urllib2.urlopen(req)
	except urllib2.HTTPError, e:
		print('HTTP Error', e)
		res = e.fp.read()
		return json.loads(res), str(e)
	res = response.read()
	return json.loads(res)

	
	
createBranch(NEW_BRANCH_NAME=None, HASH_TO_BRANCH_FROM=None, targetuser=None, repo=None,
				targetbranch=None, username=None, password=None,)

