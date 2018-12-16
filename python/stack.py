#!/usr/bin/python
# coding=utf-8
# filename: stack.py
##################################
# @author yinxj
# @date 2013-03-22

import re
import sys
import optparse


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
        self.thread_groups = sorted(groups.values(), key=lambda x: x.threads_count * 10000 + len(x.stacktrace), reverse=True)

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


def process_filename(filename):
    stack = Stack(open(filename).readlines())
    print '\n'.join(stack.to_string())


def main(argv):
    info = '''
python stack.py fileName

TODO:
    -p: pid to fetch stack dump
    -r: regular expression to fetch stack dump
    -d: process path to fetch stack dump
    -t: times to fetch stack multi times
    -n: interval in seconds, only valid with -t, default 3 seconds
'''
    parser = optparse.OptionParser(usage=info)
    parser.add_option("-f", "--filename", action="store", type="string", dest="filename")
    parser.add_option("-p", "--pid", action="store", type="string", dest="pid")
    parser.add_option("-r", "--regexp", action="store", type="string", dest="regexp")
    parser.add_option("-d", "--path", action="store", type="string", dest="process_path")
    parser.add_option("-t", "--times", action="store", type="string", dest="times")
    parser.add_option("-n", "--interval", action="store", type="string", dest="interval")
    options, args = parser.parse_args(sys.argv[1:])
    if len(args) == 0 and not options.filename:
        parser.print_help()
        exit(-1)
    if args and len(args) == 1:
        filename = args[0]
        process_filename(filename)
    elif options.filename:
        process_filename(options.filename)
    else:
        parser.print_help()
        exit(-1)


if __name__ == "__main__":
    main(sys.argv)

