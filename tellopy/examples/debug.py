import time
import sys
from .._internal import tello as tellopy
import pygame
import pygame.key
import pygame.locals
# from subprocess import Popen, PIPE
import threading
import av
import os
import datetime
import cv2.cv2 as cv2  # for avoidance of pylint error
import numpy
import traceback

prev_flight_data = None
run_recv_thread = True
new_image = None
flight_data = None
log_data = None
buttons = None
speed = 50
throttle = 0.0
yaw = 0.0
pitch = 0.0
roll = 0.0

date_fmt = '%Y-%m-%d_%H%M%S'
filename = '%s/Pictures/tello-%s.avi' % (os.getenv('HOME'), datetime.datetime.now().strftime(date_fmt))
out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc('M','J','P','G'), 25, (960, 720))

controls = {
    'w': 'forward',
    's': 'backward',
    'a': 'left',
    'd': 'right',
    'space': 'up',
    'left shift': 'down',
    'right shift': 'down',
    'q': 'counter_clockwise',
    'e': 'clockwise',
    # arrow keys for fast turns and altitude adjustments
    'left': lambda drone, speed: drone.counter_clockwise(speed*2),
    'right': lambda drone, speed: drone.clockwise(speed*2),
    'up': lambda drone, speed: drone.up(speed*2),
    'down': lambda drone, speed: drone.down(speed*2),
    'tab': lambda drone, speed: drone.takeoff(),
    'backspace': lambda drone, speed: drone.land(),
    # 'p': palm_land,
    # 'r': toggle_recording,
    # 'z': toggle_zoom,
    'enter': lambda drone: drone.take_picture(),
    'return': lambda drone: drone.take_picture(),
}

def handler(event, sender, data, **args):
    global prev_flight_data
    global flight_data
    global log_data
    drone = sender
    if event is drone.EVENT_FLIGHT_DATA:
        if prev_flight_data != str(data):
        # print(data)
            prev_flight_data = str(data)
            flight_data = data
    elif event is drone.EVENT_LOG_DATA:
        log_data = data
    else:
        print('event="%s" data=%s' % (event.getname(), str(data)))

def handle_file_received(event, sender, data):
    global date_fmt
    # Create a file in ~/Pictures/ to receive image data from the drone.
    path = '%s/Pictures/tello-%s.jpeg' % (
        os.getenv('HOME'),
        datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'))
    with open(path, 'wb') as fd:
        fd.write(data)
    print('Saved photo to %s' % path)

def handle_input_event(drone, e):
    global speed
    global throttle
    global yaw
    global pitch
    global roll
    if e.type == pygame.locals.KEYDOWN:
        keyname = pygame.key.name(e.key)
        print('+' + keyname)
        if keyname == 'escape':
            drone.set_roll(0)
            drone.set_pitch(0)
            drone.set_yaw(0)
            drone.set_throttle(0)
            print("PANIC!")
            # drone.quit()
            # exit(0)
        if keyname in controls:
            key_handler = controls[keyname]
            if type(key_handler) == str:
                getattr(drone, key_handler)(speed)
            else:
                key_handler(drone, speed)
    elif e.type == pygame.locals.KEYUP:
        keyname = pygame.key.name(e.key)
        print('-' + keyname)
        if keyname in controls:
            key_handler = controls[keyname]
            if type(key_handler) == str:
                getattr(drone, key_handler)(0)
            else:
                key_handler(drone, 0)

def draw_text(image, text, row):
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    font_size = 24
    font_color = (255,255,255)
    bg_color = (0,0,0)
    d = 2
    height, width = image.shape[:2]
    left_mergin = 10
    if row < 0:
        pos =  (left_mergin, height + font_size * row + 1)
    else:
        pos =  (left_mergin, font_size * (row + 1))
    cv2.putText(image, text, pos, font, font_scale, bg_color, 6)
    cv2.putText(image, text, pos, font, font_scale, font_color, 1)

def recv_thread(drone):
    global run_recv_thread
    global new_image
    global flight_data
    global log_data

    print('start recv_thread()')
    try:
        container = av.open(drone.get_video_stream())

        # skip first 300 frames
        frame_skip = 300
        while True:
            try:
                for frame in container.decode(video=0):
                    if 0 < frame_skip:
                        frame_skip = frame_skip - 1
                        continue
                    start_time = time.time()
                    image = cv2.cvtColor(numpy.array(frame.to_image()), cv2.COLOR_RGB2BGR)

                    out.write(image)

                    if flight_data:
                        draw_text(image, 'Flight data ' + str(flight_data), 0)
                    if log_data:
                        draw_text(image, 'MVO: ' + str(log_data.mvo), -2)
                        draw_text(image, 'IMU: ' + str(log_data.imu), -1)
                    new_image = image
                    if frame.time_base < 1.0/60:
                        time_base = 1.0/60
                    else:
                        time_base = frame.time_base
                    frame_skip = int((time.time() - start_time)/time_base)
            except av.AVError as ex:
                container = av.open(drone.get_video_stream())
                print("resetting container. exception while decoding! " + ex)
                continue

    except Exception as ex:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        print("exception in recv thread!" + ex)

def main():
    global buttons
    global run_recv_thread
    global new_image
    pygame.init()
    current_image = None

    drone = tellopy.Tello()
    drone.record_log_data()
    drone.connect()
    drone.subscribe(drone.EVENT_FLIGHT_DATA, handler)
    drone.subscribe(drone.EVENT_LOG_DATA, handler)
    drone.subscribe(drone.EVENT_FILE_RECEIVED, handle_file_received)

    threading.Thread(target=recv_thread, args=[drone]).start()

    try:
        while True:
            pygame.time.delay(50)
            for e in pygame.event.get():
                handle_input_event(drone, e)
            if current_image is not new_image:
                cv2.imshow('Tello', new_image)
                current_image = new_image
                cv2.waitKey(1)
    except KeyboardInterrupt as e:
        print(e)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        print(e)

    run_recv_thread = False
    out.release()
    cv2.destroyAllWindows()
    drone.quit()
    sys.exit(1)

if __name__ == '__main__':
    main()
