import sys
import socket
import selectors
import traceback
import multiprocessing
import time

from Protocol import libserver
from Protocol import libclient

from Utils.robotUtils import get_ipv4, create_request, listen_for_director, start_connection, initiate_connection

ROBOT_NAME = "Tester"
DIRECTOR_HOST = "143.215.188.102"
PORT = 4456

SELF_HOST = get_ipv4()
LISTEN_PORT = 8000

if __name__ == "__main__":
  print('Register with director...')

  registration_request = create_request(ROBOT_NAME, "Register", LISTEN_PORT) 
  initiate_connection(DIRECTOR_HOST, PORT, registration_request, libclient)

  print('Finished registration, booting up server to listen...')

  while True:
    msg = listen_for_director(SELF_HOST, LISTEN_PORT, libserver)

    print(msg)
    if msg['value'] == 'break':
      break

    print('Main Loop recieved ', msg, ' so will start to do corresponding task')

    # READ THE MESSAGE AND DO WHATEVER YOUR ROBOT WILL DO.

