import sys
import selectors
import json
import io
import struct

from Protocol import message

class ServerMessage(message.Message):
    def __init__(self, selector, sock, addr):
        super().__init__(selector, sock, addr)
        self.request = None

    def read(self):
      super().read()

      if self.jsonheader:
        if self.request is None:
          self.process_request()

    def process_request(self):
        content_len = self.jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self.jsonheader["content-type"] == "text/json":
            encoding = self.jsonheader["content-encoding"]
            self.request = super()._json_decode(data, encoding)
            self.addr = (self.ip, self.request.get("listenPort"))
            print(f"Received request {self.request!r} from {self.addr}")
        else:
            # Unknown content-type
            self.request = data
            print(
                f"Received {self.jsonheader['content-type']} "
                f"request from {self.addr}"
            )

        self.close()
