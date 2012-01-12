###############################################################################
#
# Copyright 2011 Pants Developers (see AUTHORS.txt)
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
"""
A convenient collection of high-level network channels.
"""

###############################################################################
# Imports
###############################################################################

import socket
import weakref

from pants.stream import Stream, StreamServer


###############################################################################
# Client Class
###############################################################################

class Client(Stream):
    """
    A simple streaming client.
    """
    def __init__(self, family=socket.AF_INET):
        # This dummy method prevents keyword arguments from finding
        # their way up to the Stream/_Channel constructors.
        Stream.__init__(self, family=family)

    ##### Control Methods #####################################################

    def connect(self, addr):
        """
        Connect the channel to a remote socket.

        Returns the channel.

        ==========  ============
        Arguments   Description
        ==========  ============
        addr        The remote address to connect to. Should be a valid address for the chosen socket family.
        ==========  ============
        """
        return Stream.connect(self, addr)


###############################################################################
# Connection Class
###############################################################################

class Connection(Stream):
    """
    A simple streaming connection to a server.

    =========  ============
    Argument   Description
    =========  ============
    socket     A pre-existing socket that this channel should wrap.
    server     The server to which this channel is connected.
    =========  ============
    """
    def __init__(self, socket, server):
        Stream.__init__(self, socket=socket)

        self.server = server


###############################################################################
# Server Class
###############################################################################

class Server(StreamServer):
    """
    A simple streaming server.

    ================  ============
    Argument          Description
    ================  ============
    ConnectionClass   *Optional.* A :obj:`pants.simple.Connection` subclass with which to wrap newly connected sockets.
    ================  ============
    """
    #: A :obj:`pants.simple.Connection` subclass with which to wrap newly connected sockets.
    ConnectionClass = Connection

    def __init__(self, ConnectionClass=None, family=socket.AF_INET):
        StreamServer.__init__(self, family=family)

        # Sets instance attribute, NOT class attribute.
        if ConnectionClass:
            self.ConnectionClass = ConnectionClass

        self.channels = weakref.WeakValueDictionary()  # fd : channel

    ##### Control Methods #####################################################

    def listen(self, addr=('', 8080), backlog=1024):
        """
        Begin listening for connections made to the channel.

        Returns the channel.

        ==========  ============
        Arguments   Description
        ==========  ============
        addr        *Optional.* The local address to listen for connections on. By default, is ('', 8080).
        backlog     *Optional.* The size of the connection queue. By default, is 1024.
        ==========  ============
        """
        if isinstance(addr, (int, long)):
            addr = ('', addr)
        
        return StreamServer.listen(self, addr, backlog)

    ##### Public Event Handlers ###############################################

    def on_accept(self, socket, addr):
        """
        Called after the channel has accepted a new connection.

        Create a new instance of :attr:`ConnectonClass` to wrap the socket
        and add it to the server.

        =========  ============
        Argument   Description
        =========  ============
        sock       The newly connected socket object.
        addr       The new socket's address.
        =========  ============
        """
        connection = self.ConnectionClass(socket, self)
        self.channels[connection.fileno] = connection
        connection._handle_connect_event()

    def on_close(self):
        """
        Called after the channel has finished closing.

        Close all active connections to the server.
        """
        for channel in self.channels.values():
            channel.close()