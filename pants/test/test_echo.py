###############################################################################
#
# Copyright 2012 Pants Developers (see AUTHORS.txt)
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

import socket
import unittest

import pants

from pants.test._pants_util import *

class Echo(pants.Stream):
    def on_read(self, data):
        self.write(data)

class TestEcho(PantsTestCase):
    def setUp(self):
        self.server = pants.Server(ConnectionClass=Echo).listen(('127.0.0.1', 4040))
        PantsTestCase.setUp(self)

    def test_echo_with_one_client(self):
        sock = socket.socket()
        sock.settimeout(1.0)
        sock.connect(('127.0.0.1', 4040))
        request = repr(sock)
        sock.send(request)
        response = sock.recv(1024)
        self.assertEquals(response, request)
        sock.close()

    def test_echo_with_two_sequential_clients(self):
        sock1 = socket.socket()
        sock1.settimeout(1.0)
        sock1.connect(('127.0.0.1', 4040))
        request1 = repr(sock1)
        sock1.send(request1)
        response1 = sock1.recv(1024)
        self.assertEquals(response1, request1)
        sock1.close()

        sock2 = socket.socket()
        sock2.settimeout(1.0)
        sock2.connect(('127.0.0.1', 4040))
        request2 = repr(sock2)
        sock2.send(request2)
        response2 = sock2.recv(1024)
        self.assertEquals(response2, request2)
        sock2.close()

    def test_echo_with_two_concurrent_clients(self):
        sock1 = socket.socket()
        sock1.settimeout(1.0)
        sock2 = socket.socket()
        sock2.settimeout(1.0)
        sock1.connect(('127.0.0.1', 4040))
        sock2.connect(('127.0.0.1', 4040))
        request1 = repr(sock1)
        request2 = repr(sock2)
        sock1.send(request1)
        sock2.send(request2)
        response1 = sock1.recv(1024)
        response2 = sock2.recv(1024)
        self.assertEquals(response1, request1)
        self.assertEquals(response2, request2)
        sock1.close()
        sock2.close()

    def tearDown(self):
        PantsTestCase.tearDown(self)
        self.server.close()
