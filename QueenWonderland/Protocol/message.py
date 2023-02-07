import sys
import selectors
import json
import io
import struct

class Message(object):

  def __init__(self, selector, sock, addr):
    self.selector = selector
    self.sock = sock
    self.ip = addr[0]
    self.addr = None
    self._recv_buffer = b""
    self._send_buffer = b""
    self._jsonheader_len = None
    self.jsonheader = None

    self.closed_connections = 0

  def _set_selector_events_mask(self, mode):
    """Set selector to listen for events: mode is 'r', 'w', or 'rw'."""
    if mode == "r":
        events = selectors.EVENT_READ
    elif mode == "w":
        events = selectors.EVENT_WRITE
    elif mode == "rw":
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
    else:
        raise ValueError(f"Invalid events mask mode {mode!r}.")
    self.selector.modify(self.sock, events, data=self)

  def _json_encode(self, obj, encoding):
    return json.dumps(obj, ensure_ascii=False).encode(encoding)

  def _json_decode(self, json_bytes, encoding):
    tiow = io.TextIOWrapper(
        io.BytesIO(json_bytes), encoding=encoding, newline=""
    )
    obj = json.load(tiow)
    tiow.close()
    return obj

  def _create_message(
    self, *, content_bytes, content_type, content_encoding
  ):
    jsonheader = {
        "byteorder": sys.byteorder,
        "content-type": content_type,
        "content-encoding": content_encoding,
        "content-length": len(content_bytes),
    }
    jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
    message_hdr = struct.pack(">H", len(jsonheader_bytes))
    message = message_hdr + jsonheader_bytes + content_bytes
    return message

  def process_events(self, mask):
    if mask & selectors.EVENT_READ:
      self.read()
    if mask & selectors.EVENT_WRITE:
      self.write()
    # return self.closed_connections
    return self.addr, self.request

  def _read(self):
    try:
      # Should be ready to read
      data = self.sock.recv(4096)
    except BlockingIOError:
        # Resource temporarily unavailable (errno EWOULDBLOCK)
      pass
    else:
      if data:
        self._recv_buffer += data
      else:
        raise RuntimeError("Peer closed.")

  def read(self):
    self._read()

    if self._jsonheader_len is None:
      self.process_protoheader()

    if self._jsonheader_len is not None:
      if self.jsonheader is None:
        self.process_jsonheader()

    # if self.jsonheader:
    #   if self.request is None:
    #     self.process_request()

  def process_protoheader(self):
    hdrlen = 2
    if len(self._recv_buffer) >= hdrlen:
      self._jsonheader_len = struct.unpack(
        ">H", self._recv_buffer[:hdrlen]
      )[0]
      self._recv_buffer = self._recv_buffer[hdrlen:]

  def process_jsonheader(self):
    hdrlen = self._jsonheader_len
    if len(self._recv_buffer) >= hdrlen:
      self.jsonheader = self._json_decode(
        self._recv_buffer[:hdrlen], "utf-8"
      )
      self._recv_buffer = self._recv_buffer[hdrlen:]
      for reqhdr in (
        "byteorder",
        "content-length",
        "content-type",
        "content-encoding",
      ):
        if reqhdr not in self.jsonheader:
            raise ValueError(f"Missing required header '{reqhdr}'.")

  def close(self):
    print(f"\t\tClosing connection to {self.ip}")
    try:
      self.selector.unregister(self.sock)
    except Exception as e:
      print(
          f"\t\tError: selector.unregister() exception for "
          f"{self.addr}: {e!r}"
      )

    try:
      self.sock.close()
    except OSError as e:
      print(f"\t\tError: socket.close() exception for {self.addr}: {e!r}")
    finally:
      # Delete reference to socket object for garbage collection
      self.sock = None
      self.closed_connections = self.closed_connections + 1