import sys
import socket
import selectors
import traceback
import multiprocessing
import time
import keyboard 
import argparse

from Protocol import libserver
from Protocol import libclient

from Utils.robotUtils import get_ipv4

import csv

HOST = get_ipv4()  # Standard loopback interface address (localhost). When in production, it should match the assigned IP Addr.
PORT = 65432  # Port to listen on (non-privileged ports are > 1023). Make sure this port is open

def create_request(action, value):
  return dict(
    type="text/json",
    encoding="utf-8",
    content=dict(action=action, value=value),
  )

def start_connection(sel, host, port, request):
  addr = (host, port)
  print(f"\t\tStarting connection to {addr}")
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.setblocking(False)
  sock.connect_ex(addr)
  events = selectors.EVENT_READ | selectors.EVENT_WRITE
  message = libclient.ClientMessage(sel, sock, addr, request)
  sel.register(sock, events, data=message)

def initiate_connection(host, port, msg):
  sel = selectors.DefaultSelector()

  request = create_request("execute", msg)
  start_connection(sel, host, port, request)
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
                    f"{traceback.format_exc()}"
                )
                message.close()
        # Check for a socket being monitored to continue.
        if not sel.get_map():
            break
  except KeyboardInterrupt:
      print("Caught keyboard interrupt, exiting")

def registration(host, port, registered_robot_map):

  sel = selectors.DefaultSelector()

  def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    message = libserver.ServerMessage(sel, conn, addr)
    sel.register(conn, selectors.EVENT_READ, data=message)

  lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  # Avoid bind() exception: OSError: [Errno 48] Address already in use
  lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  lsock.bind((host, port))
  lsock.listen()

  print('###############################################################')
  print(f"Director Listening on {(host, port)} for registration")
  print('###############################################################\n\n')
  lsock.setblocking(False)
  sel.register(lsock, selectors.EVENT_READ, data=None)

  try:
    while True:
      events = sel.select(timeout=None)
      for key, mask in events:
        if key.data is None:
          accept_wrapper(key.fileobj)
        else:
          message = key.data
          try:
            addrTuple, jsonMSG = message.process_events(mask)
            if (jsonMSG.get("message") == "Register"):
              registered_robot_map[jsonMSG.get("name")] = addrTuple

              print('\n\n###############################################################')
              print('Added ', jsonMSG.get("name"), ' from ', addrTuple)
              print('There are now ', len(registered_robot_map.keys()), ' robots registered')
              for robot in registered_robot_map.keys():
                print(f"\tRobot Name: {robot}\tIPv4: {registered_robot_map[robot][0]} ")

              print('Press Q key after all robots have registered')
              print('###############################################################\n\n')
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

def key():
  while True: 
      keyboard.wait("q")
      print('Robot Registration Completed')
      print('Starting the show...')
      break 

def csv_parser(csv_file_path, registered_robot):
  robot_order = []
  
  csv_reader = csv.reader(open(csv_file_path))
  for name_ip_exet_command in csv_reader:
    rob_name_csv = name_ip_exet_command[0]
    if rob_name_csv in registered_robot: 
      robot_order_element = dict(
        robot_name = name_ip_exet_command[0],
        execution_time = float(name_ip_exet_command[1]),
        command = name_ip_exet_command[2]
      )
      robot_order.append(robot_order_element)

  return robot_order

if __name__ == "__main__":
   # Parse command line arguments
  parser = argparse.ArgumentParser(description='Enter CSV File with Robot Order')
  parser.add_argument('csv_file_path', type=str, help='A required integer positional argument')
  args = parser.parse_args()

  # Create a shared dictionary even though not neccessary since only one process (Registration) will access it
  # But here for good practice since we're using multiprocessing
  Registered_Robots_Map = multiprocessing.Manager().dict()
  
  print('Creating Registration and Key Process')
  Registration = multiprocessing.Process(target=registration, args=(HOST, PORT, Registered_Robots_Map,))
  KeyPress = multiprocessing.Process(target=key)

  print('Starting Registration and Key Process')

  Registration.start()
  KeyPress.start()

  KeyPress.join()
  print('KeyPress Proc finished')

  time.sleep(1)

  Registration.terminate()

  print('Finished Registration Process. Listing all registered robots')
  print(Registered_Robots_Map)

  print('Generating Robot Order List...')
  robot_order = csv_parser(args.csv_file_path, Registered_Robots_Map)
  print(robot_order)

  print('\n\n###############################################################\n\n')
  print('Initiating connection with registered robot order')

  for robot in robot_order:
    print('\tInitiating connection with ',
      robot['robot_name'], ' at addr ',
      Registered_Robots_Map.get(robot['robot_name'])[0]
    )

    initiate_connection(
      Registered_Robots_Map.get(robot['robot_name'])[0],  # robot is csv file
      Registered_Robots_Map.get(robot['robot_name'])[1],
      robot['command']
    )

    time.sleep(robot['execution_time'])

  # 'broadcast' to all the robot to break
  for robotName in Registered_Robots_Map.keys():
    initiate_connection(
      Registered_Robots_Map.get(robotName)[0], 
      Registered_Robots_Map.get(robotName)[1],
      'break'
    )

  print('Finished')
