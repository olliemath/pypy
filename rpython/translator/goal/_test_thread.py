from __future__ import print_function
import thread

class MonitorList(list):
    def append(self, obj):
        list.append(self, obj)
        print("running grown to %r\n" % self, end=' ')
    def remove(self, obj):
        list.remove(self, obj)
        print("running shrunk to %r\n" % self, end=' ')

running = MonitorList()

def f(name, count, modulus):
    running.append(name)
    print("starting %s %d %d\n" % (name, count, modulus), end=' ')
    for i in xrange(count):
        if i % modulus == 0:
            print("%s %d\n" % (name, i), end=' ')
    running.remove(name)

thread.start_new_thread(f, ("eins", 10000000, 12345))
thread.start_new_thread(f, ("zwei", 10000000, 13579))
thread.start_new_thread(f, ("drei", 10000000, 14680))
thread.start_new_thread(f, ("vier", 10000000, 15725))

while not running:
    pass
print("waiting for %r to finish\n" % running, end=' ')
while running:
    pass
print("finished waiting.\n", end=' ')

