# import github3
import json, os, requests, base64


def fetch_repo_name_from_url(repo_url):
    """
    Help function to parse git repo url and return git repository name
    """
    url_name = repo_url.split('/')[-1]
    if url_name.endswith('.git'):
        url_name = url_name[:-4]
    return url_name


class githubService(object):


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


    def listOrgRepos(self):
        github = github3.login(token=os.environ['GIT_TOKEN'])
        honey = github.organization('honeyscience')
        return list(honey.iter_repos(type='all'))


    # https://stackoverflow.com/questions/3207219/how-do-i-list-all-files-of-a-directory
    def getFullFilePathsOfDirectory(self, directory, ignoreDirectories, ignoreFiles, repoIgnores):
        file_paths = []
        repoIgnoreFiles = [directory + s for s in repoIgnores[0]]
        repoIgnoreDirs  = [directory + s for s in repoIgnores[1]]

        for root, directories, files in os.walk(directory):
            directories[:] = [d for d in directories if d not in ignoreDirectories]
            files[:] = [f for f in files if f not in ignoreFiles]
            for filename in files:
                filepath = os.path.join(root, filename)
                if filepath not in repoIgnoreFiles and root not in repoIgnoreDirs:
                    file_paths.append(filepath)

        return file_paths


    def getTopicsForRepo(self, repoName):
        header ={
            "Authorization": "token %s" % os.environ['GIT_TOKEN'],
            "Accept": "application/vnd.github.mercy-preview+json"
        }
        r = requests.get("https://api.github.com/repos/honeyscience/%s/topics" % repoName, headers=header)
        return json.loads(r.text)


    def getRepoOwnersFromTags(self, repoName):
        tags = self.getTopicsForRepo(repoName).get('names')
        return "None Declared" if tags is None or not any('owner' in tag for tag in tags) else next(tag for tag in tags if 'owner' in tag).replace('owner-', '')


    def getTopContributors(self, repoName):
        r = requests.get("https://api.github.com/repos/honeyscience/%s/stats/contributors" % repoName, headers=self.basicHeader)
        if(r.status_code == 200):
            contributions = json.loads(r.text)
            contributors = {}
            for contribution in contributions:
                additions = 0
                for week in contribution['weeks']:
                    additions += week['a']
                contributors[contribution['author']['login']] = additions
            return sorted(contributors, key=contributors.get, reverse=True)[:3]
        return ["NOT POPULATED"]


    def checkRepoForKubernetesViaApi(self, repoName):
        kubeFile = requests.get("https://api.github.com/repos/honeyscience/%s/contents/kubernetes.yml" % repoName, headers=self.basicHeader).status_code == 200
        kubeDirectory = requests.get("https://api.github.com/repos/honeyscience/%s/contents/deploy" % repoName, headers=self.basicHeader).status_code == 200
        return (kubeFile or kubeDirectory)


    def checkJustForRootKubernetesFile(self, repoName):
        requests.get("https://api.github.com/repos/honeyscience/%s/contents/kubernetes.yml" % repoName, headers=self.basicHeader).status_code == 200


    def checkRepoForDockerFileViaApi(self, repoName):
        return requests.get("https://api.github.com/repos/honeyscience/%s/contents/Dockerfile" % repoName, headers=self.basicHeader).status_code == 200


    def getDockerImageFromRepo(self, repoName):
        fileLocations = [ '', 'deploy/', 'deploy/default' ]
        for location in fileLocations:
            url = "https://api.github.com/repos/honeyscience/%s/contents/%sDockerfile" % (repoName, location)
            response = requests.get(url, headers=self.basicHeader)
            if response.status_code == 200:
                json_content = json.loads(response.text)
                file_content = base64.b64decode(json_content['content']).decode('utf-8')
                lines = file_content.split('\n')
                if 'FROM ' in lines[0]:
                    return lines[0][5:]


    def hasDockerOrKubernetes(self, repoName):
        return self.checkRepoForKubernetesViaApi(repoName) or self.checkRepoForDockerFileViaApi(repoName)


    def checkForPackageJson(self, directory):
        return 'package.json' in os.listdir(directory)

    def checkFileForContent(self, repoName, pathAndFile, lineNumber, content):
        r = requests.get("https://raw.githubusercontent.com/honeyscience/%s/master/%s" % (repoName, pathAndFile), headers=self.basicHeader)
        if(r.status_code == 200):
            contents = r.text.split('\n')
            return "Found match!" if content in contents[lineNumber] else "No match found or search not accurate enough."
        return "Something messed up."


    def checkAllDockerFilesInRepo(self, repoName, lineNumber, content):
        dockerFileDict = {}
        if self.checkRepoForDockerFileViaApi(repoName):
            dockerFileDict['Dockerfile'] = self.checkFileForContent(repoName, 'Dockerfile', lineNumber, content)
        newDeployCheck = requests.get("https://api.github.com/repos/honeyscience/%s/contents/deploy/" % repoName, headers=self.basicHeader)
        if newDeployCheck.status_code == 200:
            for directory in json.loads(newDeployCheck.text):
                path = directory['path'] + '/Dockerfile'
                dockerFileDict[path] = self.checkFileForContent(repoName, path, lineNumber, content)
        return dockerFileDict


    def is_pr_merged(self, repo, pr_num):
        response = newDeployCheck = requests.get("https://api.github.com/repos/honeyscience/%s/pulls/%s" % (repo, pr_num), headers=self.basicHeader)
        if response.status_code == 200:
            json_content = json.loads(response.text)
            return json_content['merged_at'] != None
        return False


    # This is an all or nothing operation!!!  You can't just delete and create topics. You can view them all or update them all.
    # Closest thing you can do is get all of the topics, update what you need, then re-post.
    # If you need help running this, please reach out to the Security or Operations teams.
    def updateTopicOwnersInRepos(self, repoName, owner):
        currentRepoTopics = self.getTopicsForRepo(repoName)
        header = {
            "Authorization": "token %s" % os.environ['GIT_TOKEN'],
            "Accept": "application/vnd.github.mercy-preview+json",
            "Content-Type": "application/json"
        }
        newOwner = "owner-" + owner
        newTopics = [newOwner]
        if currentRepoTopics['names'] != []:
            newTopics = [topic for topic in currentRepoTopics['names'] if 'owner' not in topic]
            newTopics = [topic for topic in newTopics if 'heidi' not in topic]
            newTopics.append(newOwner)
        currentRepoTopics['names'] = newTopics
        r = requests.put("https://api.github.com/repos/honeyscience/%s/topics" % repoName, headers=header, data=json.dumps(currentRepoTopics))
        print("%s, %s" % (repoName, r.status_code))
