import sys
import selectors
import json
import io
import struct

from Protocol import message

class ClientMessage(message.Message):
    def __init__(self, selector, sock, addr, request):
        super().__init__(selector, sock, addr)
        self.request = request
        self._request_queued = False
        self.response = None

    def _write(self):
        if self._send_buffer:
            print(f"\t\tSending {self._send_buffer!r} to {self.ip}")
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]

    def write(self):
        if not self._request_queued:
            self.queue_request()

        self._write()

        if self._request_queued:
            if not self._send_buffer:
                super().close()


    def queue_request(self):
      content = self.request["content"]
      content_type = self.request["type"]
      content_encoding = self.request["encoding"]
      if content_type == "text/json":
        req = {
          "content_bytes": super()._json_encode(content, content_encoding),
          "content_type": content_type,
          "content_encoding": content_encoding,
        }
      else:
        req = {
          "content_bytes": content,
          "content_type": content_type,
          "content_encoding": content_encoding,
        }
      message = super()._create_message(**req)
      self._send_buffer += message
      self._request_queued = True