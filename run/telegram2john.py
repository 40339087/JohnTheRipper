#!/usr/bin/env python3

"""Utility to extract "hashes" from Telegram Android app's userconfing.xml file(s)"""

# Tested with Telegram for Android v4.8.4 in February, 2018.
#
# Special thanks goes to https://github.com/Banaanhangwagen for documenting
# this hashing scheme.
#
# See "UserConfig.java" from https://github.com/DrKLO/Telegram/ for details on
# the hashing scheme.
#
# Written by Dhiru Kholia <dhiru at openwall.com> in February, 2018 for JtR
# project.
#
# This software is Copyright (c) 2018, Dhiru Kholia <dhiru at openwall.com> and
# it is hereby released to the general public under the following terms:
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted.
#
# pylint: disable=invalid-name,line-too-long


import os
import sys
import base64
import struct
import hashlib
import binascii
import traceback
from io import BytesIO
import xml.etree.ElementTree as ET

PY3 = sys.version_info[0] == 3

if not PY3:
    reload(sys)
    sys.setdefaultencoding('utf8')

AuthKeySize = 256
LocalEncryptIterCount = 4000
LocalEncryptNoPwdIterCount = 4
LocalEncryptSaltSize = 32


def tdfs_parser(filename):
    try:
        f = open(filename, "rb")
    except IOError:
        e = sys.exc_info()[1]
        sys.stderr.write("%s\n" % str(e))
        return

    magic = f.read(4)
    if magic != b'TDF$':
        return False

    version = f.read(4)  # AppVersion = 1003008 for Telegram Desktop 1.3.8

    data = f.read()
    actual_data = data[:-16]
    checksum = data[-16:]
    len_bytes = len(actual_data).to_bytes(4, byteorder='little')
    calculated_checksum = hashlib.md5(actual_data + len(actual_data).to_bytes(4, byteorder='little') + version + magic).digest()
    if calculated_checksum != checksum:
        f.close()
        return False

    f.close()
    return actual_data


# Derived partly from localstorage.cpp -> readFile()
def process_tdfs_file(base):
    """
    # read settings
    directory = os.path.join(base, "tdata")
    f = os.path.join(directory, "settings0")
    if os.path.exists(f):
        settings = os.path.join(directory, "settings0")
    else:
        settings = os.path.join(directory, "settings1")
    f = BytesIO(tdfs_parser(settings))
    length = f.read(4)
    length = struct.unpack(">I", length)[0]
    if length != LocalEncryptSaltSize:
        return False
    salt = f.read(length)
    length = f.read(4)
    length = struct.unpack(">I", length)[0]
    encrypted_settings = f.read(length)
    """

    # derive filename
    s = hashlib.md5(b"data").hexdigest().upper()[:16]
    user_path = ''.join([s[x:x+2][::-1] for x in range(0, len(s), 2)])  # swap character pairs

    # read encrypted data
    directory = os.path.join(base, "tdata", user_path)
    f = os.path.join(directory, "map0")
    if os.path.exists(f):
        full_path = os.path.join(directory, "map0")
    else:
        full_path = os.path.join(directory, "map1")
    f = BytesIO(tdfs_parser(full_path))
    length = f.read(4)
    length = struct.unpack(">I", length)[0]
    if length != LocalEncryptSaltSize:
        return False
    salt = f.read(length)
    length = f.read(4)
    length = struct.unpack(">I", length)[0]
    encrypted_key = f.read(length)

    salt = binascii.hexlify(salt)
    encrypted_key = binascii.hexlify(encrypted_key)
    if PY3:
        salt = salt.decode("ascii")
        encrypted_key = encrypted_key.decode("ascii")

    print("%s:$telegram$1*%s*%s*%s" % (full_path, LocalEncryptIterCount, salt, encrypted_key))

    return True


def process_xml_file(filename):
    tree = ET.parse(filename)
    root = tree.getroot()
    h = None
    salt = None

    for item in root:
        # the "user" key doesn't seem very useful without cleaning it up
        if item.tag == 'string':
            name = item.attrib['name']
            if name == "passcodeHash1":
                h = item.text
            if name == "passcodeSalt":
                salt = item.text
    if not h or not salt:
        return

    h = h.lower()
    salt = binascii.hexlify(base64.b64decode(salt))
    if PY3:
        salt = salt.decode("ascii")

    sys.stdout.write("$dynamic_1528$%s$HEX$%s\n" % (h, salt))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: %s <userconfing.xml file(s) / <path to Telegram data directory>\n" %
                         sys.argv[0])
        sys.stderr.write("\nExample: %s ~/.local/share/TelegramDesktop\n" %
                         sys.argv[0])
        sys.exit(-1)

    for j in range(1, len(sys.argv)):
        ret = process_tdfs_file(sys.argv[j])
        if not ret:
            process_xml_file(sys.argv[j])
