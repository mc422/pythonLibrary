# import github3
import json, os, requests, base64


def helper_fun(repo_url):
    """
    Help function to parse git repo url and return git repository name
    """
    url_name = repo_url.split('/')[-1]
    if url_name.endswith('.git'):
        url_name = url_name[:-4]
    return url_name


class githubClass(object):
    def __init__(self, tempDirectory=''):
        self.tempDirectory    = tempDirectory
        if os.getenv('SSH_KEY_FILE') is None:
            print('Please add the SSH_KEY_FILE env var as stated in the README.')
        if os.environ['GIT_TOKEN'] is None:
            print('Please add the GIT_TOKEN env var as stated in the README.')
        self.ssh_command  = {'GIT_SSH_COMMAND':'ssh -i ' + os.getenv('SSH_KEY_FILE')}
        self.basicHeader = {
            "Authorization": "token %s" % os.environ['GIT_TOKEN']
        }
