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

import errno
import os
import socket

from pants.engine import Engine


###############################################################################
# Logging
###############################################################################

import logging
log = logging.getLogger("pants")


###############################################################################
# Constants
###############################################################################

#: The socket families supported by Channel.
SUPPORTED_FAMILIES = (socket.AF_INET,)
#: The socket types supported by Channel.
SUPPORTED_TYPES = (socket.SOCK_STREAM, socket.SOCK_DGRAM)


###############################################################################
# Channel Class
###############################################################################

class Channel(object):
    """
    A simple interface for a socket wrapper class.
    
    Channel is intended to be subclassed rather than instantiated directly.
    As such, many of its public methods (and some of its private methods)
    will raise a :exc:`NotImplementedError` if they are called. Subclasses
    should override these methods and ensure that their behaviour conforms
    to the specification in this class.
    
    =================  ============
    Keyword Argument   Description
    =================  ============
    family             *Optional.* A supported socket family. By default, is :const:`socket.AF_INET`.
    type               *Optional.* A supported socket type. By default, is :const:`socket.SOCK_STREAM`.
    socket             *Optional.* A pre-existing socket to wrap.
    =================  ============
    """
    def __init__(self, **kwargs):
        # Keyword arguments
        sock_family = kwargs.get("family", socket.AF_INET)
        sock_type = kwargs.get("type", socket.SOCK_STREAM)
        sock = kwargs.get("socket", None)
        if sock is None:
            sock = socket.socket(sock_family, sock_type)
        
        # Socket
        self._socket = None
        self.fileno = None
        self._socket_set(sock)
        
        # Socket state
        self._wait_for_read_event = True
        self._wait_for_write_event = True
        
        # I/O attributes
        self._recv_amount = 4096
        self._recv_buffer = None
        self._send_buffer = None
        self._sendfile_amount = 2 ** 16
        
        # Events
        self._events = Engine.ALL_EVENTS
        Engine.instance().add_channel(self)
    
    ##### Status Methods ######################################################
    
    def closed(self):
        """
        Check if the channel is closed.
        
        Returns True if the channel is closed, False otherwise.
        """
        return self._socket is None
    
    ##### Control Methods #####################################################
    
    def connect(self):
        """
        Connect the channel to a remote socket.
        
        Returns the channel.
        
        Not implemented in :class:`~pants.channel.Channel`.
        """
        raise NotImplementedError
    
    def listen(self):
        """
        Begin listening for connections made to the channel.
        
        Returns the channel.
        
        Not implemented in :class:`~pants.channel.Channel`.
        """
        raise NotImplementedError
    
    def close(self):
        """
        Close the channel.
        """
        if self._socket is None:
            return
        
        Engine.instance().remove_channel(self)
        self._socket_close()
        self._safely_call(self.on_close)
    
    def end(self):
        """
        Close the channel after writing is finished.
        """
        if self._socket is None:
            return
        
        if not self._send_buffer:
            self.close()
        else:
            self.on_write = self.close
    
    ##### I/O Methods #########################################################
    
    def write(self):
        """
        Write data to the channel.
        
        Not implemented in :class:`~pants.channel.Channel`.
        """
        raise NotImplementedError
    
    ##### Public Event Handlers ###############################################
    
    def on_read(self, data):
        """
        Placeholder. Called when data is read from the channel.
        
        =========  ============
        Argument   Description
        =========  ============
        data       A chunk of data received from the socket.
        =========  ============
        """
        pass
    
    def on_write(self):
        """
        Placeholder. Called after the channel has finished writing data.
        """
        pass
    
    def on_connect(self):
        """
        Placeholder. Called after the channel has connected to a remote
        socket.
        """
        pass
    
    def on_accept(self, sock, addr):
        """
        Placeholder. Called after the channel has accepted a new
        connection.
        
        =========  ============
        Argument   Description
        =========  ============
        sock       The newly connected socket object.
        addr       The new socket's address.
        =========  ============
        """
        pass
    
    def on_close(self):
        """
        Placeholder. Called after the channel has finished closing.
        """
        pass
    
    ##### Socket Method Wrappers ##############################################
    
    def _socket_set(self, sock):
        """
        Set the channel's current socket and update channel details.
        
        =========  ============
        Argument   Description
        =========  ============
        sock       A socket for this channel to wrap.
        =========  ============
        """
        if self._socket is not None:
            raise RuntimeError("Cannot replace existing socket.")
        if sock.family not in SUPPORTED_FAMILIES:
            raise ValueError("Unsupported socket family.")
        if sock.type not in SUPPORTED_TYPES:
            raise ValueError("Unsupported socket type.")
        
        sock.setblocking(False)
        self.fileno = sock.fileno()
        self._socket = sock
    
    def _socket_connect(self, addr):
        """
        Connect the socket to a remote socket at the given address.
        
        Returns True if the connection was immediate, False otherwise.
        
        =========  ============
        Argument   Description
        =========  ============
        addr       The remote address to connect to.
        =========  ============
        """
        try:
            result = self._socket.connect_ex(addr)
        except socket.error, err:
            result = err[0]
        
        if not result or result == errno.EISCONN:
            return True
        
        if result in (errno.EWOULDBLOCK, errno.EINPROGRESS, errno.EALREADY):
            # TODO Check for EAGAIN here?
            self._wait_for_write_event = True
            return False
        
        try:
            errstr = os.strerror(result)
        except ValueError:
            if result in errno.errorcode:
                errstr = errno.errorcode[result]
            else:
                errstr = "Unknown error %d." % result
        
        raise socket.error(result, errstr)
    
    def _socket_bind(self, addr):
        """
        Bind the socket to the given address.
        
        =========  ============
        Argument   Description
        =========  ============
        addr       The local address to bind to.
        =========  ============
        """
        self._socket.bind(addr)
    
    def _socket_listen(self, backlog):
        """
        Begin listening for connections made to the socket.
        
        =========  ============
        Argument   Description
        =========  ============
        backlog    The size of the connection queue.
        =========  ============
        """
        if os.name == "nt" and backlog > 5:
            log.warning("Setting backlog to 5 due to OS constraints.")
            backlog = 5
        
        self._socket.listen(backlog)
        self._wait_for_read_event = True
    
    def _socket_close(self):
        """
        Close the socket.
        """
        try:
            self._socket.close()
        except (AttributeError, socket.error):
            return
        finally:
            self._socket = None
            self.fileno = None
    
    def _socket_accept(self):
        """
        Accept a new connection to the socket.
        
        Returns a 2-tuple containing the new socket and its remote address.
        """
        try:
            return self._socket.accept()
        except socket.error, err:
            if err[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                self._wait_for_read_event = True
                return None, () # sock, addr placeholders.
            else:
                raise
    
    def _socket_recv(self):
        """
        Receive data from the socket.
        
        Returns a string of data read from the socket. The data is None if
        the socket has been closed.
        """
        try:
            data = self._socket.recv(self._recv_amount)
        except socket.error, err:
            if err[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                self._wait_for_read_event = True
                return ''
            elif err[0] == errno.ECONNRESET:
                return None
            else:
                raise
        
        if not data:
            return None
        else:
            return data
    
    def _socket_recvfrom(self):
        """
        Receive data from the socket.
        
        Returns a 2-tuple containing a string of data read from the socket
        and the address of the sender. The data is None if reading failed.
        The data and address are None if no data was received.
        """
        try:
            data, addr = self._socket.recvfrom(self._recv_amount)
        except socket.error, err:
            if err[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                self._wait_for_read_event = True
                return '', None
            else:
                raise
        
        # TODO Is this section necessary?
        if not data:
            return None, None
        else:
            return data, addr
    
    def _socket_send(self, data):
        """
        Send data to the socket.
        
        Returns the number of bytes that were sent to the socket.
        
        =========  ============
        Argument   Description
        =========  ============
        data       The string of data to send.
        =========  ============
        """
        try:
            return self._socket.send(data)
        except socket.error, err:
            if err[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                self._wait_for_write_event = True
                return 0
            else:
                raise
    
    def _socket_sendto(self, data, addr, flags=0):
        """
        Send data to a remote socket.
        
        Returns the number of bytes that were sent to the socket.
        
        =========  ============
        Argument   Description
        =========  ============
        data       The string of data to send.
        addr       The remote address to send to.
        flags      *Optional.* Flags to pass to the sendto call.
        =========  ============
        """
        try:
            return self._socket.sendto(data, flags, addr)
        except socket.error, err:
            if err[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                self._wait_for_write_event = True
                return 0
            else:
                raise
    
    def _socket_sendfile(self, file, offset, bytes):
        """
        =========  ============
        Argument   Description
        =========  ============
        file       The file to send.
        offset     
        bytes      
        =========  ============
        """
        if bytes is None:
            to_read = self._sendfile_amount
        else:
            to_read = min(bytes, self._sendfile_amount)
        file.seek(offset)
        data = file.read(to_read)
        if len(data) == 0:
            return 0
        
        return self._socket_send(data)
    
    ##### Internal Methods ####################################################
    
    def _safely_call(self, thing_to_call, *args, **kwargs):
        """
        Safely execute a callable.
        
        The callable is wrapped in a try block and executed. If an
        exception is raised it is logged.
        
        ==============  ============
        Argument        Description
        ==============  ============
        thing_to_call   The callable to execute.
        *args           The positional arguments to be passed to the callable.
        **kwargs        The keyword arguments to be passed to the callable.
        ==============  ============
        """
        try:
            return thing_to_call(*args, **kwargs)
        except Exception:
            log.exception("Exception raised on %s #%d." %
                    (self.__class__.__name__, self.fileno))
            # TODO Close the channel here?
    
    def _get_socket_error(self):
        """
        Get the most recent error that occured on the socket.
        
        Returns a 2-tuple containing the error code and the error message.
        """
        err = self._socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        errstr = ""
        
        if err != 0:
            errstr = "Unknown error %d" % err
            try:
                errstr = os.strerror(err)
            except (NameError, OverflowError, ValueError):
                if err in errno.errorcode:
                    errstr = errno.errorcode[err]
        
        return err, errstr
    
    ##### Internal Event Handler Methods ######################################
    
    def _handle_events(self, events):
        """
        Handle events raised on the channel.
        
        =========  ============
        Argument   Description
        =========  ============
        events     The events in the form of an integer.
        =========  ============
        """
        if self._socket is None:
            log.warning("Received events for closed %s #%d." %
                    (self.__class__.__name__, self.fileno))
            return
        
        if events & Engine.READ:
            self._wait_for_read_event = False
            self._handle_read_event()
            if self._socket is None:
                return
        
        if events & Engine.WRITE:
            self._wait_for_write_event = False
            self._handle_write_event()
            if self._socket is None:
                return
        
        if events & Engine.ERROR:
            err, errstr = self._get_socket_error()
            if err != 0:
                log.error("Error on %s #%d: %s (%d)" %
                        (self.__class__.__name__, self.fileno, errstr, err))
            self.close()
            return
        
        if events & Engine.HANGUP:
            log.debug("Hang up on %s #%d." %
                    (self.__class__.__name__, self.fileno))
            self.close()
            return
        
        events = Engine.ERROR | Engine.HANGUP
        if self._wait_for_read_event == True:
            events |= Engine.READ
        if self._wait_for_write_event == True:
            events |= Engine.WRITE
        if events != self._events:
            self._events = events
            Engine.instance().modify_channel(self)
    
    def _handle_read_event(self):
        """
        Handle a read event raised on the channel.
        
        Not implemented in :class:`~pants.channel.Channel`.
        """
        raise NotImplementedError
    
    def _handle_write_event(self):
        """
        Handle a write event raised on the channel.
        
        Not implemented in :class:`~pants.channel.Channel`.
        """
        raise NotImplementedError
