###############################################################################
#
# Copyright 2011 Chris Davis
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
###############################################################################

###############################################################################
# Imports
###############################################################################

import os
import socket
import sys

import ctypes
import ctypes.util


###############################################################################
# Constants
###############################################################################

SENDFILE_PLATFORMS = ("linux2", "darwin", "freebsd", "dragonfly")
SENDFILE_AMOUNT = 2 ** 16


###############################################################################
# Sendfile
###############################################################################

_sendfile = None
if sys.version_info >= (2,6) and sys.platform in SENDFILE_PLATFORMS:
    _libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    if hasattr(_libc, "sendfile"):
        _sendfile = _libc.sendfile
        
if _sendfile is None:
    def sendfile(file, channel, offset, bytes):
        if bytes == 0:
            to_read = SENDFILE_AMOUNT
        else:
            to_read = min(bytes, SENDFILE_AMOUNT)
        
        file.seek(offset)
        data = file.read(to_read)
        
        if len(data) == 0:
            return 0
        
        return channel._socket_send(data)

elif sys.platform == "linux2":
    _sendfile.argtypes = (
            ctypes.c_int, # file
            ctypes.c_int, # socket
            ctypes.POINTER(ctypes.c_uint64), # offset
            ctypes.c_size_t # len
            )
    
    def sendfile(file, channel, offset, bytes):
        _offset = ctypes.c_uint64(offset)
        
        result = _sendfile(file.fileno(), channel.fileno, _offset, bytes)
        
        if result == -1:
            e = ctypes.get_errno()
            raise socket.error(e, os.strerror(e))
        
        return result

elif sys.platform == "darwin":
    _sendfile.argtypes = (
            ctypes.c_int, # file
            ctypes.c_int, # socket
            ctypes.c_uint64, # offset
            ctypes.POINTER(ctypes.c_uint64), # len
            ctypes.c_voidp, # header/trailer
            ctypes.c_int # flags
            )
    
    def sendfile(file, channel, offset, bytes):
        _bytes = ctypes.c_uint64(bytes)
        
        result = _sendfile(file.fileno(), channel.fileno, offset, _bytes, None, 0)
        
        if result == -1:
            e = ctypes.get_errno()
            raise socket.error(e, os.strerror(e))
        
        return _bytes.value

elif sys.platform in ("freebsd", "dragonfly"):
    _sendfile.argtypes = (
            ctypes.c_int, # file
            ctypes.c_int, # socket
            ctypes.c_uint64, # offset
            ctypes.c_uint64, # len
            ctypes.c_voidp, # header/trailer
            ctypes.POINTER(ctypes.c_uint64), # bytes sent
            ctypes.c_int # flags
            )
    
    def sendfile(file, channel, offset, bytes):
        _bytes = ctypes.c_uint64()
        
        result = _sendfile(file.fileno(), channel.fileno, offset, bytes, None, _bytes, 0)
        
        if result == -1:
            e = ctypes.get_errno()
            raise socket.error(e, os.strerror(e))
        
        return _bytes.value
