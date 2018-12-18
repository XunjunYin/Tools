#!/usr/bin/python
# coding=utf-8
# filename: stack.py
##################################
# @author yinxj
# @date 2013-03-22

import os
import re
import sys
import optparse
import time
from datetime import datetime

times = 1
interval = 3


class Stack:
    def __init__(self, raw_lines):
        self.raw_lines = raw_lines
        self.info = []
        self.threads = []
        self.thread_groups = []
        #
        self.parse_raw_lines()
        self.merge_groups()

    def merge_groups(self):
        groups = {}
        for thread in self.threads:
            if thread.__hash__() not in groups:
                groups[thread.__hash__()] = ThreadGroup()
            groups[thread.__hash__()].add_thread(thread)
        self.thread_groups = sorted(groups.values(), key=lambda x: x.threads_count * 10000 + len(x.stacktrace),
                                    reverse=True)

    def parse_raw_lines(self):
        thread = None
        for line in self.raw_lines:
            line = line.strip('\n')
            if len(line.strip()) == 0:
                if thread:
                    self.threads.append(thread)
                thread = None
                continue
            if not thread:
                tid_nid = re.findall('tid=(\w+) nid=(\w+)', line)
                if len(tid_nid) > 0:
                    thread = Thread(tid_nid[0][0], tid_nid[0][1])
                    if 'runnable' in line.lower():
                        thread.state = 'runnable'
                    elif 'waiting on condition' in line.lower():
                        thread.state = 'waiting'
                    names = re.findall('"(.+?)"', line)
                    if len(names) > 0:
                        thread.name = re.sub('\d+', '*', names[0])
                        line = re.sub(names[0], thread.name, line)
                    # #123
                    line = re.sub('#(\d+)', '#***', line)
                    # [0x00007fe85d148000]
                    line = re.sub('\[(\w+)\]', '[****************]', line)
                    line = line.replace(thread.tid, '********').replace(thread.nid, '********')
                    thread.stacktrace.append(line)
                else:
                    self.info.append(line)
            else:
                if line.strip().startswith('at '):
                    pass
                elif 'java.lang.Thread.State' in line:
                    thread.state = 'runnable' if 'RUNNABLE' in line else 'waiting'
                elif 'wait for' in line:
                    waits = re.findall('<(\w+)>', line)
                    if len(waits) > 0:
                        thread.waiting_lock = waits[0]
                        line = re.sub(waits[0], '********', line)
                elif 'locked' in line:
                    locks = re.findall('<(\w+)>', line)
                    if len(locks) > 0:
                        thread.locking_lock.append(locks[0])
                        line = re.sub(locks[0], '********', line)
                thread.stacktrace.append(line)

    def to_string(self):
        content = []
        content.extend(self.info)
        for group in self.thread_groups:
            content.append('')
            content.append('')
            content.append('threads count=%s' % group.threads_count)
            content.append('name=%s' % group.name)
            content.append('state=%s' % group.state)
            if len(group.waiting_locks) > 0:
                content.append('waiting locks=%s' % ', '.join(group.waiting_locks))
            if len(group.locking_lock) > 0:
                content.append('locking lock=%s' % ', '.join(group.locking_lock))
            content.append('-' * 120)
            for i in group.stacktrace:
                content.append(i)
        return content


class Thread:
    def __init__(self, tid, nid):
        self.tid = tid
        self.nid = nid
        self.name = None
        self.state = None
        self.waiting_lock = None
        self.locking_lock = []
        self.stacktrace = []

    def __hash__(self):
        import hashlib
        return int(hashlib.sha1(','.join(self.stacktrace)).hexdigest(), 16) % (10 ** 18)


class ThreadGroup:
    def __init__(self):
        self.name = None
        self.state = None
        self.threads_count = 0
        self.stacktrace = []
        self.waiting_locks = set([])
        self.locking_lock = set([])
        # self.threads = []

    def add_thread(self, thread):
        self.name = thread.name
        self.state = thread.state
        self.stacktrace = thread.stacktrace
        if thread.waiting_lock:
            self.waiting_locks.add(thread.waiting_lock)
        self.locking_lock.update(thread.locking_lock)
        # self.threads.append(thread)
        self.threads_count += 1


def repeat(f, x):
    for i in range(times):
        if i > 0:
            time.sleep(interval)
        stack = f(x)
        filename = '/tmp/stack_%s.summary' % datetime.now().strftime("%Y%m%d%H%M%S")
        open(filename, 'w').write('\n'.join(stack.to_string()))
        print 'stack summary saved in file: %s' % filename


def process_filename(filename):
    return Stack(open(filename).readlines())


def process_pid(pid):
    command = '%s %s' % (get_jstack_command(pid), pid)
    return Stack(os.popen(command).readlines())


def process_regexp(reg):
    pids = []
    for line in os.popen('ps ax | grep java').readlines():
        if any(word in line for word in ['grep', 'stack.py']):
            continue
        process = re.findall(reg, line)
        if len(process) > 0:
            pid = re.findall('^\d+', line)
            pids.append(pid[0])
    if len(pids) == 0:
        print 'failed, no java process found'
        exit(-1)
    if len(pids) > 1:
        print 'failed, too many process found: %s' % ', '.join(pids)
        exit(-1)
    process_pid(pids[0])


def get_jstack_command(pid):
    ps = os.popen('ps -p %s' % pid).read()
    commands = re.findall('[^\s]+java', ps)
    return 'jstack' if len(commands) == 0 else re.sub('java', 'jstack', commands[0])


def main(argv):
    info = 'The stack tool is used to analyze stack dump for a given dump file or process, currently only support Java.'
    parser = optparse.OptionParser(usage=info)
    parser.add_option("-f", type="string", dest='filename', help="stack dump file to analyze")
    parser.add_option("-p", type="string", dest='pid', help="pid to fetch stack dump")
    parser.add_option("-r", type="string", dest='regexp', help="regular expression to fetch stack dump")
    parser.add_option("-d", type="string", dest='path', help="process path to fetch stack dump")
    parser.add_option("-t", type="string", dest='times', help="times to fetch stack multi times")
    parser.add_option("-n", type="string", dest='interval', help="interval in seconds, only valid with -t, default 3")
    options, args = parser.parse_args(sys.argv[1:])
    if args and len(args) == 1:
        filename = args[0]
        repeat(process_filename, filename)
        exit(0)
    if options.filename:
        repeat(process_filename, options.filename)
        exit(0)
    global times, interval
    if options.times and options.times.isdigit():
        times = int(options.times)
    if options.interval and options.interval.isdigit():
        interval = int(options.interval)
    if options.pid:
        repeat(process_pid, options.pid)
        exit(0)
    if options.regexp:
        repeat(process_regexp, options.regexp)
        exit(0)
    else:
        parser.print_help()
        exit(-1)


if __name__ == "__main__":
    main(sys.argv)
