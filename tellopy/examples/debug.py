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
import math
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
offset_x = 0.0
offset_y = 0.0

date_fmt = '%Y-%m-%d_%H%M%S'
filename = '%s/Pictures/tello-%s.avi' % (os.getenv('HOME'), datetime.datetime.now().strftime(date_fmt))
out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc('M','J','P','G'), 15, (960, 720))

class JoystickDualAction:
    # d-pad
    UP = -1  # UP
    DOWN = -1  # DOWN
    ROTATE_LEFT = -1  # LEFT
    ROTATE_RIGHT = -1  # RIGHT

    # bumper triggers
    LAND = 4  # L1
    TAKEOFF = 5  # R1
    PANO_L = 6 #L2
    PANO_R = 7 #R2

    # buttons
    LEFT = 0  # X
    BACKWARD = 1  # A
    RIGHT = 2  # B
    FORWARD = 3  # Y
    SPEED_DOWN = 8 #BACK
    SPEED_UP = 9 #START
    # UNUSED = 10 #L_JOY
    # UNUSED = 11 #R_JOY

    # axis
    LEFT_X = 0
    LEFT_Y = 1
    RIGHT_X = 2
    RIGHT_Y = 3
    LEFT_X_REVERSE = 1.0
    LEFT_Y_REVERSE = -1.0
    RIGHT_X_REVERSE = 1.0
    RIGHT_Y_REVERSE = -1.0
    DEADZONE = 0.01

class Waypoint:
    def __init__(self, tgt_x, tgt_y):
        self.tgt_x = tgt_x
        self.dx = 0.0
        self.at_x = False

        self.tgt_y = tgt_y
        self.dy = 0.0
        self.at_y = False

    def get_dx_dy(self, cur_yaw, cur_x, cur_y):
        adj_yaw = cur_yaw * (math.pi / 180.0)
        self.dx = (math.cos(adj_yaw) * (self.tgt_x - cur_x)) - (math.sin(adj_yaw) * (self.tgt_y - cur_y))
        self.dy = (math.sin(adj_yaw) * (self.tgt_x - cur_x)) + (math.cos(adj_yaw) * (self.tgt_y - cur_y))
        return (round(self.dx, 2), round(self.dy, 2))

    def get_dx(self, cur_x):
        self.dx = self.tgt_x - cur_x
        return self.dx

    def get_dy(self, cur_y):
        self.dy = self.tgt_y - cur_y
        return self.dy

    def arrived(self):
        return self.at_x and self.at_y

def update(old, new, max_delta=0.3):
    if abs(old - new) <= max_delta:
        res = new
    else:
        res = 0.0
    return res

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
    global offset_x
    global offset_y
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
        elif keyname == 'l':
            drone.land()
    elif e.type == pygame.locals.KEYUP:
        keyname = pygame.key.name(e.key)
        print('-' + keyname)
        if keyname == 't':
            drone.takeoff()
        elif keyname == 'p':
            drone.take_picture()
        elif keyname == 'f':
            if speed <= 90:
                speed += 5
            print("speed up to " + str(speed))
        elif keyname == 's':
            if speed > 5:
                speed -= 5
            print("speed down to " + str(speed))
    elif e.type == pygame.locals.JOYAXISMOTION:
        # ignore small input values (Deadzone)
        if -buttons.DEADZONE <= e.value and e.value <= buttons.DEADZONE:
            e.value = 0.0
        if e.axis == buttons.LEFT_Y:
            throttle = update(throttle, e.value * buttons.LEFT_Y_REVERSE)
            drone.set_throttle(throttle)
        if e.axis == buttons.LEFT_X:
            yaw = update(yaw, e.value * buttons.LEFT_X_REVERSE)
            drone.set_yaw(yaw)
        if e.axis == buttons.RIGHT_Y:
            pitch = update(pitch, e.value *
                           buttons.RIGHT_Y_REVERSE)
            drone.set_pitch(pitch)
        if e.axis == buttons.RIGHT_X:
            roll = update(roll, e.value * buttons.RIGHT_X_REVERSE)
            drone.set_roll(roll)
    elif e.type == pygame.locals.JOYHATMOTION:
        if e.value[0] < 0:
            drone.counter_clockwise(speed)
        if e.value[0] == 0:
            drone.clockwise(0)
        if e.value[0] > 0:
            drone.clockwise(speed)
        if e.value[1] < 0:
            drone.down(speed)
        if e.value[1] == 0:
            drone.up(0)
        if e.value[1] > 0:
            drone.up(speed)
    elif e.type == pygame.locals.JOYBUTTONDOWN:
        if e.button == buttons.LAND:
            drone.land()
        elif e.button == buttons.UP:
            drone.up(speed)
        elif e.button == buttons.DOWN:
            drone.down(speed)
        elif e.button == buttons.ROTATE_RIGHT:
            drone.clockwise(speed)
        elif e.button == buttons.ROTATE_LEFT:
            drone.counter_clockwise(speed)
        elif e.button == buttons.FORWARD:
            drone.forward(speed)
        elif e.button == buttons.BACKWARD:
            drone.backward(speed)
        elif e.button == buttons.RIGHT:
            drone.right(speed)
        elif e.button == buttons.LEFT:
            drone.left(speed)
        elif e.button == buttons.PANO_L:
            drone.counter_clockwise(30)
        elif e.button == buttons.PANO_R:
            drone.clockwise(30)
    elif e.type == pygame.locals.JOYBUTTONUP:
        if e.button == buttons.TAKEOFF:
            if throttle != 0.0:
                print('###')
                print('### throttle != 0.0 (This may hinder the drone from taking off)')
                print('###')
            drone.takeoff()
        elif e.button == buttons.UP:
            drone.up(0)
        elif e.button == buttons.DOWN:
            drone.down(0)
        elif e.button == buttons.ROTATE_RIGHT:
            drone.clockwise(0)
        elif e.button == buttons.ROTATE_LEFT:
            drone.counter_clockwise(0)
        elif e.button == buttons.FORWARD:
            drone.forward(0)
        elif e.button == buttons.BACKWARD:
            drone.backward(0)
        elif e.button == buttons.RIGHT:
            drone.right(0)
        elif e.button == buttons.LEFT:
            drone.left(0)
        elif e.button == buttons.PANO_L:
            drone.counter_clockwise(0)
        elif e.button == buttons.PANO_R:
            drone.clockwise(0)
            #offset_x = drone.log_data.mvo.pos_x
            #offset_y = drone.log_data.mvo.pos_y
        elif e.button == buttons.SPEED_UP:
            if speed <= 90:
                speed += 5
            print("speed up to " + str(speed))
        elif e.button == buttons.SPEED_DOWN:
            if speed > 5:
                speed -= 5
            print("speed down to " + str(speed))

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
                # container = av.open(drone.get_video_stream())
                print("exception while decoding! " + ex)
                continue

    except Exception as ex:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        print("exception in recv thread!" + ex)

def main():
    global buttons
    global run_recv_thread
    global new_image
    global offset_x
    global offset_y
    pygame.init()
    pygame.joystick.init()
    current_image = None

    try:
        js = pygame.joystick.Joystick(0)
        js.init()
        buttons = JoystickDualAction
    except pygame.error:
        pass

    wp = Waypoint(4.0, 4.0)
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
            # current_yaw = drone.log_data.imu.yaw
            # adj_x = drone.log_data.mvo.pos_x - offset_x
            # adj_y = drone.log_data.mvo.pos_y - offset_y
            # dx = wp.get_dx(adj_x)
            # dy = wp.get_dy(adj_y)
            # dx, dy = wp.get_dx_dy(current_yaw, adj_x, adj_y)
            # print(dx, dy)

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
