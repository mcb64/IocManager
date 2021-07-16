#!/usr/bin/env python
import sys, argparse, socket, tempfile, stat, pwd, os
import utils
from psp.caput import caput

def match_hutch(h, hlist):
    h = h.split('-')
    if h[0] in hlist:
        return h[0]
    if h[1] in hlist:
        return h[1]
    return None

def get_hutch(ns):
    hlist = utils.getHutchList()
    # First, take the --hutch specified on the command line.
    if ns.hutch is not None:
        if not ns.hutch in hlist:
            raise Exception("Nonexistent hutch %s" % v)
        return ns.hutch
    # Second, try to match the current host.
    v = match_hutch(socket.gethostname(), hlist)
    # Finally, try to match the IOC name.
    if v is None and ns.ioc is not None:
        v = match_hutch(ns.ioc, hlist)
    return v

def usage():
    print "Usage: imgr IOCNAME [--hutch HUTCH] --reboot soft"
    print "       imgr IOCNAME [--hutch HUTCH] --reboot hard"
    print "       imgr IOCNAME [--hutch HUTCH] --enable"
    print "       imgr IOCNAME [--hutch HUTCH] --disable"
    print "       imgr IOCNAME [--hutch HUTCH] --upgrade RELEASE_DIR"
    print "       imgr IOCNAME [--hutch HUTCH] --move HOST"
    print "       imgr IOCNAME [--hutch HUTCH] --move HOST:PORT"
    print "       imgr [--hutch HUTCH] --list"
    sys.exit(1)

def soft_reboot(hutch, ioc):
    base = utils.getBaseName(ioc)
    if base is None:
        print "IOC %s not found!" % ioc
        sys.exit(1)
    caput(base + ":SYSRESET", 1)
    sys.exit(0)

def hard_reboot(hutch, ioc):
    (ft, cl, hl, vs) = utils.readConfig(hutch)
    for c in cl:
        if c['id'] == ioc:
            utils.restartProc(c['host'], c['port'])
            sys.exit(0)
    print "IOC %s not found in hutch %s!" % (ioc, hutch)
    sys.exit(1)

def do_commit(hutch, cl, hl, vs):
    file = tempfile.NamedTemporaryFile(dir=utils.TMP_DIR, delete=False)
    utils.writeConfig(hutch, hl, cl, vs, file)
    file.close()
    os.chmod(file.name, stat.S_IRUSR | stat.S_IRGRP |stat.S_IROTH)
    os.system("ssh %s %s %s %s" % (utils.COMMITHOST, utils.INSTALL, hutch, file.name))
    try:
        os.unlink(file.name)
    except:
        print "Error removing temporary file %s!" % file.name

def set_state(hutch, ioc, enable):
    if not utils.check_auth(pwd.getpwuid(os.getuid())[0], hutch):
        print "Not authorized!"
        sys.exit(1)
    (ft, cl, hl, vs) = utils.readConfig(hutch)
    try:
        utils.COMMITHOST = vs["COMMITHOST"]
    except:
        pass
    for c in cl:
        if c['id'] == ioc:
            c['newdisable'] = not enable
            do_commit(hutch, cl, hl, vs)
            utils.applyConfig(hutch, None, ioc)
            sys.exit(0)
    print "IOC %s not found in hutch %s!" % (ioc, hutch)
    sys.exit(1)

def upgrade(hutch, ioc, version):
    if not utils.check_auth(pwd.getpwuid(os.getuid())[0], hutch):
        print "Not authorized!"
        sys.exit(1)
    if not utils.validateDir(version, ioc):
        print "%s does not have an st.cmd for %s!" % (version, ioc)
        sys.exit(1)
    (ft, cl, hl, vs) = utils.readConfig(hutch)
    try:
        utils.COMMITHOST = vs["COMMITHOST"]
    except:
        pass
    for c in cl:
        if c['id'] == ioc:
            c['newdir'] = version
            do_commit(hutch, cl, hl, vs)
            utils.applyConfig(hutch, None, ioc)
            sys.exit(0)
    print "IOC %s not found in hutch %s!" % (ioc, hutch)
    sys.exit(1)

def move(hutch, ioc, hostport):
    if not utils.check_auth(pwd.getpwuid(os.getuid())[0], hutch):
        print "Not authorized!"
        sys.exit(1)
    (ft, cl, hl, vs) = utils.readConfig(hutch)
    try:
        utils.COMMITHOST = vs["COMMITHOST"]
    except:
        pass
    for c in cl:
        if c['id'] == ioc:
            hp = hostport.split(":")
            c['newhost'] = hp[0]
            if len(hp) > 1:
                c['newport'] = int(hp[1])
            if not utils.validateConfig(cl):
                print "Port conflict when moving %s to %s, not moved!" % (ioc, hostport)
                sys.exit(1)
            do_commit(hutch, cl, hl, vs)
            utils.applyConfig(hutch, None, ioc)
            sys.exit(0)
    print "IOC %s not found in hutch %s!" % (ioc, hutch)
    sys.exit(1)

def do_list(hutch):
    (ft, cl, hl, vs) = utils.readConfig(hutch)
    for c in cl:
        if c['alias'] != "":
            print("%s (%s)" % (c['id'], c['alias']))
        else:
            print("%s" % c['id'])
    sys.exit(0)

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(prog="imgr")
        parser.add_argument("ioc", nargs="?")
        parser.add_argument("--reboot")
        parser.add_argument("--disable", action='store_true')
        parser.add_argument("--enable", action='store_true')
        parser.add_argument("--upgrade")
        parser.add_argument("--move")
        parser.add_argument("--hutch")
        parser.add_argument("--list", action='store_true')
        ns = parser.parse_args(sys.argv[1:])
    except:
        usage()
    hutch = get_hutch(ns)
    if hutch is None:
        usage()
    if ns.list:
        do_list(hutch)
    if ns.ioc is None:
        usage()
    if ns.reboot is not None:
        if ns.reboot == 'hard':
            hard_reboot(hutch, ns.ioc)
        elif ns.reboot == 'soft':
            soft_reboot(hutch, ns.ioc)
        else:
            usage()
    elif ns.disable and ns.enable:
        usage()
    elif ns.disable or ns.enable:
        set_state(hutch, ns.ioc, ns.enable)
    elif ns.upgrade is not None:
        upgrade(hutch, ns.ioc, ns.upgrade)
    elif ns.move is not None:
        move(hutch, ns.ioc, ns.move)
    else:
        usage()
    sys.exit(0)
