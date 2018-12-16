#!/usr/bin/python
# coding=utf-8
# filename: deploy.py
##################################
# @author xjyin
# @date 2012-07-09
##################################
# auto deploy
# usage: python deploy.py -h
##################################

import string
import os
import sys
import re
import time
import logging
import getpass
import commands
import threading
import optparse
import readline

# tab complete for input
# reference: http://stackoverflow.com/questions/5637124/tab-completion-in-pythons-raw-input
COMMANDS = ['install', 'start', 'stop', 'rrestart', 'restart', 'status', 'remove', 'reload']
SERVICES = []
RE_SPACE = re.compile('.*\s+$', re.M)
CMD_SPLIT = re.compile(';|&')
COMPLETE_COMMANDS = ['install', 'start', 'stop', 'rrestart', 'restart', 'status', 'remove', 'reload', 'with', 'without',
                     'only', 'and', 'help', 'quit', 'exit']
# readline.parse_and_bind("tab: complete")
# readline.set_completer(wrapComplete)

# locks
antLock = threading.RLock()
consoleLock = threading.RLock()

# global vars
debug = False
user = ''
password = ''
# logger
logger = None


def complete(text, state):
    global COMPLETE_COMMANDS
    for cmd in COMPLETE_COMMANDS:
        if cmd.startswith(text):
            if not state:
                return cmd
            else:
                state -= 1


def complete_lisn(text, state):
    global COMMANDS
    global SERVICES
    # buffer = readline.get_line_buffer()
    # leave the last part after ; or &
    whole_line = readline.get_line_buffer()
    # syncPrint("whole_line="+whole_line)
    whole_split = CMD_SPLIT.split(whole_line)
    last_section = whole_split[-1]
    # syncPrint("last_section="+last_section)
    line = last_section.split()
    buffer = last_section
    # show all commands
    if not line:
        # syncPrint("not line")
        return [c + ' ' for c in COMMANDS][state]
    else:
        # syncPrint("line="+str(line))
        pass
    # account for last argument ending in a space
    if RE_SPACE.match(buffer):
        line.append('')
    # resolve command to the implementation function
    cmd = line[0].strip()
    # syncPrint("cmd="+str(cmd))
    try:
        if cmd in COMMANDS:
            args = line[1:]
        services = []
        if args:
            if args[0] in SERVICES:
                # should suggest numbers? the better solution is implement completor in Deploy
                return None
            else:
                # try find service
                services = [s for s in SERVICES if s.startswith(args[0])]
            if not services:
                services = SERVICES
        return (services + [None])[state]
    except:
        syncprint('>>> traceback <<<')
        traceback.print_exc()
        syncPrint('>>> end of traceback <<<')

    results = [c + ' ' for c in COMMANDS if c.startswith(cmd)] + [None]
    return results[state]


def wrapComplete(text, state):
    c = complete(text, state)
    # syncPrint("\ntext="+text+" state="+str(state) + " ret=" + c)
    return c


try:
    import readline
except Exception as e:
    print "failed to import readline: %s" % e
else:
    readline.parse_and_bind("tab: complete")
    readline.set_completer(wrapComplete)


def syncPrint(msg):
    global consoleLock
    consoleLock.acquire()
    print time.strftime('%Y-%m-%d %X') + ' ' + msg
    # save to log at same time
    logger.info(msg)
    consoleLock.release()


###################################################
class Deploy:
    def __init__(self, confFile):
        self.vars = {}
        self.confFile = confFile
        self.getsvninfo()
        self.reload()

    # reread the config file after modified
    def reload(self):
        self.vars = {}
        self.services = []
        global SERVICES
        global COMPLETE_COMMANDS
        SERVICES = []
        self.serviceNames = []
        self.readConf()

    # get svn user and password
    def getsvninfo(self):
        global password
        global user
        if user != '' and password != '':
            return
        fConf = open(self.confFile)
        while True:
            line = fConf.readline()
            if line == '':
                break
            if line.startswith('#') or line == '':
                continue
            if line.strip().startswith('svn'):
                while True:
                    user = raw_input("please input svn user and password:\nuser: ")
                    if user.strip() != '':
                        user = user.strip()
                        break
                while True:
                    # input twice to insure correct
                    password = getpass.getpass()
                    print "confirm the password"
                    if getpass.getpass() == password:
                        break
                    print "confirm fail, try again."
                break
        fConf.close()

    # make sure password and user are corrent
    # not in use currently
    def checksvninfo(self):
        if False:
            return False
        return True

    # parse config file
    def readConf(self):
        global COMPLETE_COMMANDS
        fConf = open(self.confFile)
        function_start = False
        while True:
            line = fConf.readline()
            if line == '':
                break
            if line.startswith('#') or line == '':
                continue
            elif line.startswith('DEFINE'):
                while True:
                    line = fConf.readline()
                    if line == '':
                        syncPrint('DEFINE exception: "DEFINE" should match with "ENDDEFINE"')
                        exit(-1)
                    line = line.strip()
                    if line.startswith('#') or line == '':
                        continue
                    line = self.replace(line)
                    if line == 'ENDDEFINE':
                        break
                    if '=' not in line:
                        syncPrint('DEFINE exception, should match the pattern: ([^=]+)=(.+), as key=value')
                        exit(-1)
                    self.vars[line[0:line.find('=')]] = self.replace(line[line.find('=') + 1:])
            elif line.startswith('SERVICE'):
                service = Service()
                if '=' not in line:
                    syncPrint('SERVICE exception, should match the pattern: SERVICE=\w+')
                    exit(-1)
                name = line[line.find('=') + 1:].strip()
                if name in self.serviceNames:
                    syncPrint("service name conflict: %s" % name)
                    exit(-1)
                service.setName(name)
                global SERVICES
                self.serviceNames.append(name)
                SERVICES.append(name)
                COMPLETE_COMMANDS.append(name)
                while True:
                    line = fConf.readline()
                    if line == '':
                        syncPrint('SERVICE exception: "SERVICE" should match with "ENDSERVICE"')
                        exit(-1)
                    line = line.strip()
                    if line.startswith('#') or line == '':
                        continue
                    line = self.replace(line)
                    if line.startswith('HOST'):
                        service.setHost(line[line.find('=') + 1:])
                    if line.startswith('LEVEL'):
                        service.setLevel(int(line[line.find('=') + 1:]))
                    elif line.startswith('START'):
                        service.setStartCmd(line[line.find('=') + 1:])
                    elif line.startswith('STOP'):
                        service.setStopCmd(line[line.find('=') + 1:])
                    elif line.startswith('STATUS'):
                        service.setStatusCmd(line[line.find('=') + 1:])
                    elif line.startswith('REMOVE'):
                        service.setRemoveCmd(line[line.find('=') + 1:])
                    elif line == 'INSTALL':
                        function_start = False
                        while True:
                            line = fConf.readline()
                            if line == '':
                                syncPrint('INSTALL exception: "INSTALL" should match with "ENDINSTALL"')
                                exit(-1)
                            line = line.strip()
                            if line.startswith('#') or line == '':
                                continue
                            line = self.replace(line)
                            # end of install
                            if line == 'ENDINSTALL':
                                break
                            # function define
                            if line.startswith('FUNCTION'):
                                if function_start:
                                    syncPrint('FUNCTION exception: "FUNCTION" should match with "ENDFUNCTION"')
                                    exit(-1)
                                function_start = True
                                if '=' not in line:
                                    syncPrint('FUNCTION exception: should match FUNCTION=.+')
                                    exit(-1)
                                function = line[line.find('=') + 1:]
                                COMPLETE_COMMANDS.append(function)
                                service.addInstallCmd('%%FUNCTION%%' + function)
                                continue
                            # end of function
                            if line == 'ENDFUNCTION':
                                if function_start == False:
                                    syncPrint('FUNCTION exception: "ENDFUNCTION" should follow "FUNCTION"')
                                    exit(-1)
                                function_start = False
                                service.addInstallCmd('%%ENDFUNCTION%%')
                                continue
                            # modify file
                            if line.startswith('MODFILE'):
                                file = line[line.find('=') + 1:]
                                service.addInstallModCmd(file, '%%MODFILE%%')
                                while True:
                                    line = fConf.readline()
                                    if line == '':
                                        syncPrint('MODFILE exception: "MODFILE" should match with "ENDMODFILE"')
                                        exit(-1)
                                    line = line.strip()
                                    if line.startswith('#') or line == '':
                                        continue
                                    line = self.replace(line)
                                    if line == 'ENDMODFILE':
                                        service.addInstallModCmd(file, '%%ENDMODFILE%%')
                                        break
                                    service.addInstallModCmd(file, line)
                            # shell cmd
                            else:
                                if line.startswith('svn'):
                                    line = self.addSVNInfo(line)
                                elif line.startswith('ant'):
                                    line = self.addAntLockTag(line)
                                service.addInstallCmd(line)
                    elif line == 'ENDSERVICE':
                        self.services += [service]
                        break
        if function_start:
            syncPrint('FUNCTION exception: "FUNCTION" should match with "ENDFUNCTION"')
            exit(-1)
        fConf.close()

    # to avoid mulit-"ant resolve" at same time by same user
    def addAntLockTag(self, line):
        return line + '%%ANTLOCK%%'

    # add svn user and password
    def addSVNInfo(self, line):
        global password
        global user
        res = line + ' '  # avoid line.find(' ',svnPathPos+4) returns -1
        svnPathPos = res.find('http')
        svnPath = res[svnPathPos:res.find(' ', svnPathPos + 4)]
        res = res.replace(svnPath, svnPath + ' --username ' + user + ' --password ' + password)
        return res.strip()

    # lspath=/disk4/armani
    # line='./run/service.sh start index $[0,1,2] @@${lspath}/index'
    # return './run/service.sh start index $[0,1,2] @@/disk4/armani/index'
    def replace(self, line):
        while True:
            s = line.find('${')
            e = line.find('}', s + 2)
            if s == -1 or e == -1:
                break
            line = line.replace(line[s:e + 1], self.vars[line[s + 2:e]])
        return line

    def interaction(self):
        self.help()
        while True:
            # self.deploy(raw_input(">> "))
            # self.deploy(sys.stdin.readline());
            #
            self.deploy(raw_input('>>'))

    # rawIn='install index 0-1 & install summary & start ds'
    def deploy(self, rawCmdIn):
        preCmdType = ''

        # step1: split ";"
        for cmdsIn in rawCmdIn.split(';'):
            tasks = []

            # step2: split "&"
            for cmdIn in cmdsIn.split('&'):
                cmd = re.split(r' |,', cmdIn.strip())
                if "exit" == cmd[0] or "quit" == cmd[0]:
                    syncPrint("bye!")
                    exit(0)
                if "help" == cmd[0]:
                    if len(cmd) == 2:
                        # print service's info
                        if cmd[1] in self.serviceNames:
                            currentService = self.services[self.serviceNames.index(cmd[1])]
                            if len(currentService.functions) > 0:
                                print 'functions: ',
                                print currentService.functions
                            print 'number: ',
                            print currentService.number
                        else:
                            print cmdIn + ": invalid command for service name"
                    else:
                        self.help()
                    return
                if "reload" == cmd[0]:
                    self.reload()
                    return

                # step3: get parameters
                global COMMANDS
                if cmd[0] in COMMANDS:
                    cmdType = cmd[0]
                    preCmdType = cmdType
                    cmdPara = cmd[1:]
                else:
                    if preCmdType == '':
                        syncPrint(cmdIn + ": invalid command type")
                        return
                    else:
                        cmdType = preCmdType
                        cmdPara = cmd

                # step4: get service name
                # no service name means all services
                if len(cmdPara) == 0:
                    for service in self.services:
                        tasks.append((service, cmdType, [], [], [], []))
                    continue
                if len(cmdPara) > 0 and (cmdPara[0] not in self.serviceNames):
                    syncPrint(cmdIn + ": invalid command for service name")
                    return
                currentService = self.services[self.serviceNames.index(cmdPara[0])]

                # step5: parse function list
                withoutList = []
                if 'without' in cmdPara:
                    startPos = cmdPara.index('without') + 1
                    while True:
                        if cmdPara[startPos] not in currentService.functions:
                            syncPrint(cmdIn + ": invalid command for undefined function")
                            return
                        withoutList.append(cmdPara[startPos])
                        if startPos < len(cmdPara) - 2 and cmdPara[startPos + 1] == 'and':
                            startPos += 2
                        else:
                            break
                withList = []
                if 'with' in cmdPara:
                    startPos = cmdPara.index('with') + 1
                    while True:
                        if cmdPara[startPos] not in currentService.functions:
                            syncPrint(cmdIn + ": invalid command for undefined function")
                            return
                        withList.append(cmdPara[startPos])
                        if startPos < len(cmdPara) - 2 and cmdPara[startPos + 1] == 'and':
                            startPos += 2
                        else:
                            break
                onlyList = []
                if 'only' in cmdPara:
                    startPos = cmdPara.index('only') + 1
                    while True:
                        if cmdPara[startPos] not in currentService.functions:
                            syncPrint(cmdIn + ": invalid command for undefined function")
                            return
                        onlyList.append(cmdPara[startPos])
                        if startPos < len(cmdPara) - 2 and cmdPara[startPos + 1] == 'and':
                            startPos += 2
                        else:
                            break
                funListNumber = 0
                if len(onlyList) > 0:
                    funListNumber += 1
                if len(withList) > 0:
                    funListNumber += 1
                if len(withoutList) > 0:
                    funListNumber += 1
                if funListNumber > 0 and cmdType != 'install':
                    syncPrint(cmdIn + ": function(s) only for install")
                    return
                if funListNumber > 1:
                    syncPrint(cmdIn + ": two many type given, only one needed")
                    return

                # step6: parse number list of slice
                numberParaList = []
                numberStarted = False
                for para in cmdPara:
                    if para[0].isdigit():
                        numberStarted = True
                        numberParaList.append(para)
                    elif numberStarted == True:
                        break
                numberList = []
                if len(numberParaList) > 0:
                    numberList = self.getNumberList(numberParaList)
                    if numberList == [] or max(numberList) > currentService.number - 1:
                        syncPrint(cmdIn + ": invalid command for slice list")
                        return
                tasks.append((currentService, cmdType, numberList, withList, withoutList, onlyList))

            # step7: no error, execute commands
            levels = {}
            for task in tasks:
                if levels.has_key(task[0].level):
                    levels[task[0].level].append(task)
                else:
                    levels[task[0].level] = [task]
            for level in sorted(levels.keys()):
                threads = []
                for task in levels[level]:
                    t = threading.Thread(target=task[0].run, args=(task[1], task[2], task[3], task[4], task[5]))
                    threads.append(t)
                for t in threads:
                    t.start()
                # check threads every 1s, whether all stopped
                while True:
                    finish = True
                    for t in threads:
                        if t.isAlive() == True:
                            finish = False
                            break
                    if finish == True:
                        break
                    time.sleep(0.1)
                if len(levels.keys()) > 1:
                    syncPrint(cmdsIn + ' [level ' + str(level) + ']: task finished')
            syncPrint(cmdsIn + ': task finished')
        if len(rawCmdIn.split(';')) > 1:
            syncPrint(rawCmdIn + ': task finished')

    # input: ['0','2-4','7']
    # return: [0,2,3,4,7]
    @staticmethod
    def getNumberList(nl):
        res = []
        for n in nl:
            if n.isdigit():
                res.append(int(n))
            else:
                n_split = n.split('-')
                if len(n_split) != 2 or not (n_split[0].isdigit() and n_split[1].isdigit()):
                    return []
                if int(n_split[0]) > int(n_split[1]):
                    return []
                res += range(int(n_split[0]), int(n_split[1]) + 1)
        return res

    def help(self):
        print "\nyour services:"
        for service in self.services:
            print "%s:" % service.name,
            if 1 == service.number:
                print "0"
            else:
                print "0-%s" % (service.number - 1)
        print '''
commands: 
install: install service
start: start service
stop: stop service
status: get service status
remove: remove code directory and install directory of service
restart: stop;start
rrestart: stop;install;start
reload: reload config file, this is useful when changing config file without quit program

usage:
install ${serviceName1};install ${serviceName2};start ${serviceName2}: will execute one after another
install ${serviceName1} & ${serviceName2} -- command type can be omitted if same as the previous
install ${serviceName0} 0-1 & install ${serviceName2} & start ${serviceName3}: will execute parallel
install ${serviceName1}&status ${serviceName2};stop ${serviceName1};remove ${serviceName3}
install ${serviceName0} with ${functionName0} and ${functionName2}
install ${serviceName1} 0-3 without ${functionName1}
install ${serviceName1} only ${functionName1} 2-4

arguments:
no parameters: all services
${serviceName}: service name
${serviceName},${n0},${n1}-${n2}: service name, but only the given NO(s)
with function0: in the function list, only function0 will be executed
without function0: in the function list, function0 will not be executed
only function0: in install commands, only function0 will be executed

type "help" to get help
or type "help ${serviceName}" to get information of service
or type "exit" to exits.

see@https://dev.corp.youdao.com/outfoxwiki/XunjunYin/AutoDeployTool
			'''


############################################################################
class Service:
    def __init__(self):
        self.name = ''
        self.host = []
        self.startCmd = []
        self.stopCmd = []
        self.statusCmd = []
        self.removeCmd = []
        self.installCmds = []
        self.functions = []
        # default level=1
        self.level = 1
        self.number = 1
        self.globalPath = '/home/' + commands.getoutput('whoami')

    def setName(self, name):
        self.name = name

    def setLevel(self, level):
        self.level = level

    def setHost(self, host):
        hosts = self.separate(host)
        self.setNumber(hosts)
        self.host = hosts

    def getSlice(self, listin, n):
        if len(listin) == 1:
            return listin[0]
        else:
            return listin[n]

    def setStartCmd(self, cmd):
        # 先resolveWorkDir再separate
        cmds = self.separate(self.resolveWorkDir(cmd))
        self.setNumber(cmds)
        self.startCmd = cmds

    def setStopCmd(self, cmd):
        cmds = self.separate(self.resolveWorkDir(cmd))
        self.setNumber(cmds)
        self.stopCmd = cmds

    def setStatusCmd(self, cmd):
        cmds = self.separate(self.resolveWorkDir(cmd))
        self.setNumber(cmds)
        self.statusCmd = cmds

    def setRemoveCmd(self, cmd):
        cmds = self.separate(self.resolveWorkDir(cmd))
        self.setNumber(cmds)
        self.removeCmd = cmds

    def addInstallCmd(self, cmd):
        if '%%FUNCTION%%' in cmd:
            self.functions.append(cmd.replace('%%FUNCTION%%', ''))
        cmds = self.separate(self.resolveWorkDir(cmd))
        self.setNumber(cmds)
        self.installCmds.append(cmds)

    def addInstallModCmd(self, file, cmd):
        cmds = []
        if '%%MODFILE%%' in cmd or '%%ENDMODFILE%%' in cmd:
            self.installCmds.append(self.separate(cmd + file))
            return
        # pattern like a||||b||||c1<<<<>>>>c2
        if '||||' in cmd:
            s = re.split(r'\|\|\|\||<<<<>>>>', cmd)
            # matchPattern=<!-- The http port -->.*<http server-id="" host="\*" port=".*"\/>
            # prePattern=<!-- The http port -->.*
            # source=<http server-id="" host="\*" port=".*"\/>
            # target=<http server-id="" host="\*" port="53214"\/>
            # command: sed -n '1h;1!{;/matchPattern/ !H;g;/matchPattern/ {;s/\(prePattern\)source/\1target/g;p;n;h;};h;};$p;'
            res = "sed -n '1h;1!{;/matchPattern/ !H;g;/matchPattern/ {;s/\(prePattern\)source/\\1target/g;p;n;h;};h;};$p;'"
            prePattern = ''
            if len(s) < 3:
                syncPrint(cmd + ' is invalid')
                exit(-1)
            pos = 0
            while pos < len(s) - 2:
                prePattern += s[pos] + '.*'
                pos += 1
            matchPattern = prePattern + s[pos]
            source = s[pos]
            target = s[pos + 1]
            res = res.replace('matchPattern', self.regReplace(matchPattern)).replace('prePattern', self.regReplace(
                prePattern)).replace('source', self.regReplace(source)).replace('target', self.regReplace(target))
        # pattern like c1<<<<>>>>c2
        elif '<<<<>>>>' in cmd:
            # command: sed -i 's/install.dir=.*/install.dir=target/'
            st = cmd.split('<<<<>>>>')
            res = "sed -i 's/" + self.regReplace(st[0]) + '/' + self.regReplace(st[1]) + "/'"
        else:
            syncPrint(cmd + ' is invalid')
            exit(-1)
        cmds = self.separate(res)
        self.setNumber(cmds)
        self.installCmds.append(cmds)

    def regReplace(self, si):
        # '/' is special in sed
        # '&' in sed means the matched content
        replaceChar = '/&'
        so = ''
        for char in si:
            if char in replaceChar:
                so += '\\' + char
            else:
                so += char
        return so

    # reset number with cmds, number!=1 if cmds contains "$[x,x,x]"
    def setNumber(self, cmds):
        if len(cmds) == 1 or len(cmds) == self.number:
            return
        if len(cmds) > 1 and self.number == 1:
            self.number = len(cmds)
            return
        print "error config: slice number not agreed -- " + str(self.number) + ' != ' + str(len(cmds))
        exit(-1)

    # numberList=[] means all slices
    # withList means list of functions to be exec
    # withoutList means list of function no to be exec
    def run(self, cmd, numberList, withList, withoutList, onlyList):
        if cmd == 'install':
            f = self.install
        elif cmd == 'start':
            f = self.start
        elif cmd == 'stop':
            f = self.stop
        elif cmd == 'status':
            f = self.status
        elif cmd == 'remove':
            f = self.remove
        elif cmd == 'restart':
            self.run('stop', numberList, withList, withoutList, onlyList)
            f = self.start
        elif cmd == 'rrestart':
            self.run('stop', numberList, withList, withoutList, onlyList)
            self.run('install', numberList, withList, withoutList, onlyList)
            f = self.start
        if len(numberList) == 0:
            nl = range(self.number)
        else:
            nl = numberList
        # multi threads to execute tasks
        threads = []
        for n in nl:
            if cmd == 'install':
                t = threading.Thread(target=f, args=(n, withList, withoutList, onlyList))
            else:
                t = threading.Thread(target=f, args=(n,))
            threads.append(t)
        for c in range(len(nl)):
            threads[c].start()
        # check threads every 1s, whether all stopped
        while True:
            finish = True
            for c in range(len(nl)):
                if threads[c].isAlive() == True:
                    finish = False
                    break
            if finish == True:
                break
            time.sleep(1)
        syncPrint("%s: %s finished" % (self.name, cmd))
        return "finished"

    def install(self, n, withList, withoutList, onlyList):
        # step1: check
        info = "install " + self.name + '(' + str(n) + ')@' + self.getSlice(self.host, n)
        syncPrint(info)
        if len(self.installCmds) == 0:
            syncPrint(info + ": install command not set")
            return

        # step2: exec all install commands
        count = 0
        useOnly = len(onlyList) > 0
        inOnlyMode = False
        while count < len(self.installCmds):
            installCmd = self.getSlice(self.installCmds[count], n)

            # step3: if function
            if '%%FUNCTION%%' in installCmd:
                function = installCmd.replace('%%FUNCTION%%', '')

                # step4: if use "with"
                if len(withList) > 0:
                    if function in withList:
                        count += 1
                        continue
                    else:
                        # jump to the function finish
                        while True:
                            count += 1
                            if '%%ENDFUNCTION%%' in self.getSlice(self.installCmds[count], n):
                                break
                        count += 1
                        continue

                # step5: if use "without"
                elif len(withoutList) > 0:
                    if function in withoutList:
                        # jump to the function finish
                        while True:
                            count += 1
                            if '%%ENDFUNCTION%%' in self.getSlice(self.installCmds[count], n):
                                break
                        count += 1
                        continue
                    else:
                        count += 1
                        continue

                # step6: if use "only"
                elif len(onlyList) > 0:
                    if function in onlyList:
                        inOnlyMode = True
                        count += 1
                        continue
                    else:
                        # jump to the function finish
                        while True:
                            count += 1
                            if '%%ENDFUNCTION%%' in self.getSlice(self.installCmds[count], n):
                                break
                        count += 1
                        continue
                else:
                    count += 1
                    continue
            if '%%ENDFUNCTION%%' in installCmd:
                if useOnly == True:
                    inOnlyMode = False
                count += 1
                continue

            # step7: if "only"
            if useOnly != inOnlyMode:
                count += 1
                continue

            # step8: whether file modify: cp and modify file, then cp back
            if '%%MODFILE%%' in installCmd:
                # cp file to tmpFile1
                file = installCmd.replace('%%MODFILE%%', '')
                tmpFile1 = self.globalPath + '/' + self.name + str(n) + '.tmp1'
                tmpFile2 = self.globalPath + '/' + self.name + str(n) + '.tmp2'
                shellCmd = 'cp ' + file + ' ' + tmpFile1
                if (self.execRemoteShellCmd(info, shellCmd, n) == "break"):
                    return
                # modify file
                while True:
                    count += 1
                    installCmd = self.getSlice(self.installCmds[count], n)
                    if '%%ENDMODFILE%%' in installCmd:
                        # end modify file, cp back
                        shellCmd = 'cp ' + tmpFile1 + ' ' + file + ';' + 'rm ' + tmpFile1
                        if (self.execRemoteShellCmd(info, shellCmd, n) == "break"):
                            return
                        break
                    else:
                        # 'sed -i' is different from 'sed -n'
                        if 'sed -i' in installCmd:
                            shellCmd = installCmd + ' ' + tmpFile1
                        else:
                            shellCmd = installCmd + ' ' + tmpFile1 + '>' + tmpFile2 + ';mv ' + tmpFile2 + ' ' + tmpFile1
                        if (self.execRemoteShellCmd(info, shellCmd, n) == "break"):
                            return
                count += 1
                continue

            # not file modify commands
            # step9: whether "ant"
            needAntLock = False
            # acquire ant lock
            if '%%ANTLOCK%%' in installCmd:
                needAntLock = True
                antLock.acquire()
                installCmd = installCmd.replace('%%ANTLOCK%%', '')
            shellCmd = installCmd
            if (self.execRemoteShellCmd(info, shellCmd, n) == "break"):
                return
            # release ant lock
            if needAntLock:
                antLock.release()
            count += 1

    def start(self, n):
        if len(self.startCmd) == 0:
            syncPrint(self.name + str(n) + ": start command not set")
            return
        info = "start " + self.name + str(n) + '@' + self.getSlice(self.host, n)
        shellCmd = self.getSlice(self.startCmd, n)
        if (self.execRemoteShellCmd(info, shellCmd, n) == "break"):
            return

    def stop(self, n):
        if len(self.stopCmd) == 0:
            syncPrint(self.name + str(n) + ": stop command not set")
            return
        info = "stop " + self.name + str(n) + '@' + self.getSlice(self.host, n)
        shellCmd = self.getSlice(self.stopCmd, n)
        if (self.execRemoteShellCmd(info, shellCmd, n) == "break"):
            return

    def status(self, n):
        if len(self.statusCmd) == 0:
            syncPrint(self.name + str(n) + ": status command not set")
            return
        info = "status " + self.name + str(n) + '@' + self.getSlice(self.host, n)
        shellCmd = self.getSlice(self.statusCmd, n)
        if (self.execRemoteShellCmd(info, shellCmd, n) == "break"):
            return

    def remove(self, n):
        if len(self.removeCmd) == 0:
            syncPrint(self.name + str(n) + ": remove command not set")
            return
        info = "remove " + self.name + str(n) + '@' + self.getSlice(self.host, n)
        shellCmd = self.getSlice(self.removeCmd, n)
        if (self.execRemoteShellCmd(info, shellCmd, n) == "break"):
            return

    # write shellCmd to /global/home/${ldap}/server+n.sh,
    # then ssh to the host and execute the global shell file
    def execRemoteShellCmd(self, info, shellCmd, n):
        global password
        # confirm step by step
        infoToPrint = info + ' (' + shellCmd.replace('--password ' + password,
                                                     '--password ' + '*' * len(password)) + ')'
        if debug:
            syncPrint(infoToPrint)
            if raw_input("continue: y/n") not in 'yY':
                return "break"
        globalShellFile = self.globalPath + '/' + self.name + str(n) + '.sh'
        f = open(globalShellFile, 'w')
        f.write(shellCmd + '\n')
        f.close()
        commands.getoutput('chmod +x ' + globalShellFile)
        sshCmd = 'ssh ' + self.getSlice(self.host, n) + ' "' + globalShellFile + '"'
        syncPrint(infoToPrint + ': please wait...')
        output = commands.getoutput(sshCmd)
        # output="test"
        syncPrint(infoToPrint + ':\t' + output)
        commands.getoutput('rm ' + globalShellFile)
        return "success"

    # cmd=./run/service.sh start index $[0,1-2] @@/disk4/armani/index
    # return ['./run/service.sh start index 0 @@/disk4/armani/index','./run/service.sh start index 1 @@/disk4/armani/index','./run/service.sh start index 2 @@/disk4/armani/index']
    def separate(self, cmd):
        res = []
        group = []
        NO = 1
        while True:
            s = cmd.find('$[')
            e = cmd.find(']', s + 2)
            if s == -1 or e == -1:
                break
            if s != 0:
                group.append([cmd[0:s]])
            l = cmd[s + 2:e].split(',')  # ['0','1-2']
            # whether means a range
            nl = Deploy.getNumberList(l)
            if len(nl) == 0:
                g = l
            else:
                nltmp = []
                for nln in nl:
                    nltmp.append(str(nln))
                g = nltmp
            #
            if NO != 1 and NO != len(g):
                syncPrint(cmd + " -- error config: slice number not agreed")
                exit(-1)
            else:
                NO = len(g)
            group.append(g)
            cmd = cmd[e + 1:]
        if cmd != '':
            group.append([cmd])
        for n in range(NO):
            r = ''
            for g in group:
                if len(g) == 1:
                    r += g[0]
                else:
                    r += g[n].strip()
            res.append(r)
        return res

    # cmd='./run/service.sh start index $[0,1,2] @@/disk4/armani/index'
    # return 'cd /disk4/armani/index;./run/service.sh start index $[0,1,2]'
    def resolveWorkDir(self, cmd):
        pos = cmd.rfind('@@')
        if pos == -1:
            return cmd
        return 'cd ' + cmd[pos + 2:] + ' && ' + cmd[0:pos].strip()


################################################################################
def main(argv):
    parser = optparse.OptionParser()
    parser.add_option("-f", "--filename", action="store", type="string", dest="filename")
    parser.add_option("-p", "--pid", action="store", type="string", dest="pid")
    parser.add_option("-r", "--regexp", action="store", type="string", dest="regexp")
    parser.add_option("-d", "--path", action="store", type="string", dest="process_path")
    parser.add_option("-t", "--times", action="store", type="string", dest="times")
    parser.add_option("-n", "--interval", action="store", type="string", dest="interval")
    (options, args) = parser.parse_args(sys.argv[1:])
    if len(args) == 0:
        parser.print_help()
        return
    if args != None and len(args) == 1:
        confFile = args[0]
    else:
        if (options.config != None):
            confFile = options.config
        else:
            parser.print_help()
            exit(-1)
        if (options.svnuser != None):
            global user
            user = options.svnuser
        if (options.svnpass != None):
            global password
            password = options.svnpass
    if confFile == None:
        parser.print_help()
        exit(-1)
    # logger
    if confFile.endswith('.conf'):
        logFile = confFile[0:-5] + '.log'
    else:
        logFile = confFile + '.log'
    global logger
    logger = logging.getLogger()
    hdlr = logging.FileHandler(logFile)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG)

    d = Deploy(confFile)
    if options.command == None:
        d.interaction()
    else:
        d.deploy(options.command)


if __name__ == "__main__":
    main(sys.argv)
