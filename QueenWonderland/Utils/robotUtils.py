import sys
import socket
import selectors
import subprocess

def get_ipv4():
  output = subprocess.check_output(["hostname", "-I"])
  output = output.decode('utf-8')
  ip4, ip6, nextLine = output.split(' ')
  return ip4

def create_request(name, value, listening_port):
  return dict(
    type="text/json",
    encoding="utf-8",
    content=dict(name=name, message=value, listenPort=listening_port),
  )

def start_connection(sel, host, port, request, msgClient):
  addr = (host, port)
  print(f"\t\tStarting connection to {addr}")
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.setblocking(False)
  sock.connect_ex(addr)
  events = selectors.EVENT_READ | selectors.EVENT_WRITE
  message = msgClient.ClientMessage(sel, sock, addr, request)
  sel.register(sock, events, data=message)

def initiate_connection(host, port, request, msgClient):
  sel = selectors.DefaultSelector()

  # request = create_request("execute", msg)
  start_connection(sel, host, port, request, msgClient)
  try:
    while True:
        events = sel.select(timeout=2)
        for key, mask in events:
            message = key.data
            try:
                message.process_events(mask)
            except Exception:
                print(
                    f"Main: Error: Exception for {message.addr}:\n"
                )
                message.close()
        # Check for a socket being monitored to continue.
        if not sel.get_map():
            break
  except KeyboardInterrupt:
      print("Caught keyboard interrupt, exiting")

def listen_for_director(host, port, msgClient):
  completed_connections = 0
  sel = selectors.DefaultSelector()

  def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    message = msgClient.ServerMessage(sel, conn, addr)
    sel.register(conn, selectors.EVENT_READ, data=message)

  lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

  # Avoid bind() exception: OSError: [Errno 48] Address already in use
  lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  lsock.bind((host, port))
  lsock.listen()
  print(f"Robot Listening on {(host, port)}")
  lsock.setblocking(False)
  sel.register(lsock, selectors.EVENT_READ, data=None)

  numConn = 0
  try:
    while numConn == 0:
      events = sel.select(timeout=None)
      for key, mask in events:
        if key.data is None:
          accept_wrapper(key.fileobj)
        else:
          message = key.data
          try:
              addrTuple, jsonMSG = message.process_events(mask)
              numConn = numConn + 1
          except Exception:
              print(
                  f"Main: Error: Exception for {message.addr}:\n"
                  f"{traceback.format_exc()}"
              )
              message.close()
  except KeyboardInterrupt:
      print("Caught keyboard interrupt, exiting")
  finally:
      sel.close()
      return jsonMSG