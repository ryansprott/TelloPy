from time import sleep
from .._internal import tello as tellopy
import os
import datetime
import math

class Waypoint:
    def __init__(self, tgt_w, tgt_x, tgt_y, tgt_z):
        self.tgt_w = tgt_w
        self.dw = 0.0
        self.at_w = False

        self.tgt_x = tgt_x
        self.dx = 0.0
        self.at_x = False

        self.tgt_y = tgt_y
        self.dy = 0.0
        self.at_y = False

        self.tgt_z = tgt_z
        self.dz = 0.0
        self.at_z = False

    def get_yaw_delta(self, cur_w):
        adj_current = 360.0 + cur_w if cur_w < 0.0 else cur_w
        adj_target  = 360.0 + self.tgt_w if self.tgt_w < 0.0 else self.tgt_w

        self.dw = round(adj_target - adj_current, 2)

        if (abs(self.dw) >= 180.0 and self.dw > 0.0):
            self.dw -= 360.0
        elif (abs(self.dw) >= 180.0 and self.dw < 0.0):
            self.dw += 360.0

        return round(self.dw, 2)

    def get_yaw_speed(self):
        speed = (abs(self.dw) / 180.0) * 100.0
        adj_spd = speed if speed >= 10.0 else 10.0
        return round(adj_spd, 2)

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
        return self.at_w and self.at_x and self.at_y

def update(old, new, max_delta=0.3):
    if abs(old - new) <= max_delta:
        res = new
    else:
        res = 0.0
    return res

def handler(event, sender, data, **args):
    drone = sender
    if event is drone.EVENT_FLIGHT_DATA:
        print(data)
    if event is drone.EVENT_FILE_RECEIVED:
        # Create a file in ~/Pictures/ to receive image data from the drone.
        path = '%s/Pictures/tello-%s.jpeg' % (
            os.getenv('HOME'),
            datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'))
        with open(path, 'wb') as fd:
            fd.write(data)
        print('Saved photo to %s' % path)

def test():
    drone = tellopy.Tello()
    try:
        # drone.subscribe(drone.EVENT_FLIGHT_DATA, handler)
        drone.subscribe(drone.EVENT_FILE_RECEIVED, handler)
        drone.record_log_data()
        drone.connect()
        drone.wait_for_connection(60.0)
        drone.takeoff()
        sleep(5)

        offset_x = drone.log_data.mvo.pos_x
        offset_y = drone.log_data.mvo.pos_y

        waypoints = [
            Waypoint(0.0, 0.0, 0.0, 0.0),
            Waypoint(0.0, 0.0, 4.0, 0.0),
            Waypoint(0.0, 4.0, 4.0, 0.0),
            Waypoint(0.0, 4.0, 0.0, 0.0),
            Waypoint(0.0, 0.0, 0.0, 0.0),
        ]

        wp = waypoints.pop()

        while True:
            # direction = ""
            current_yaw = drone.log_data.imu.yaw
            yaw_delta = wp.get_yaw_delta(current_yaw)
            yaw_speed = wp.get_yaw_speed()

            if (yaw_delta > 0.0):
                direction = "turning CW, delta "
                drone.clockwise(yaw_speed)
            elif (yaw_delta < 0.0):
                direction = "turning CCW, delta "
                drone.counter_clockwise(yaw_speed)
            # print(direction + str(yaw_delta) + " at " + str(yaw_speed) + " cm/s from " + str(current_yaw) + " to " + str(wp.tgt_w))
            if (math.isclose(0.0, yaw_delta, abs_tol=1.0)):
                # close enough for government work!
                print("at yaw")
                drone.set_yaw(0.0)
                wp.at_w = True

            adj_x = drone.log_data.mvo.pos_x - offset_x
            adj_y = drone.log_data.mvo.pos_y - offset_y
            # print(adj_x, adj_y)

            # dx = wp.get_dx(adj_x)
            # dy = wp.get_dy(adj_y)
            dx, dy = wp.get_dx_dy(current_yaw, adj_x, adj_y)
            print(dx, dy)

            if (dx <= 0.1 and dx >= -0.1):
                drone.set_roll(0.0)
                print("at X")
                wp.at_x = True
            elif (dx >= 3.0):
                drone.set_roll(1.0)
            elif (dx <= 3.0):
                drone.set_roll(-1.0)
            elif (dx > 0.3):
                drone.set_roll(0.5)
            elif (dx < 0.3):
                drone.set_roll(-0.5)

            if (dy <= 0.1 and dy >= -0.1):
                drone.set_pitch(0.0)
                print("at Y")
                wp.at_y = True
            elif (dy >= 3.0):
                print("fast fwd")
                drone.set_pitch(1.0)
            elif (dy <= 3.0):
                print("fast back")
                drone.set_pitch(-1.0)
            elif (dy > 0.3):
                print("slow fwd")
                drone.set_pitch(0.5)
            elif (dy < 0.3):
                print("slow back")
                drone.set_pitch(-0.5)

            if (wp.arrived()):
                print("arrived!")
                drone.set_roll(0.0)
                drone.set_pitch(0.0)
                drone.set_yaw(0.0)
                drone.set_throttle(0.0)
                sleep(1.0)
                if (len(waypoints) == 0):
                    break
                else:
                    wp = waypoints.pop()

            sleep(0.1)

        sleep(2)
        drone.land()
        sleep(5)
    except Exception as ex:
        print(ex)
    finally:
        drone.quit()

if __name__ == '__main__':
    test()
