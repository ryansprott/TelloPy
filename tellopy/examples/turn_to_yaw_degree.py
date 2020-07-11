from time import sleep
from .._internal import tello as tellopy
import os
import datetime
import math

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

        drone.connect()
        drone.wait_for_connection(60.0)
        drone.takeoff()
        sleep(2)

        target_yaw = 0.0
        yaws = [0.0, 45.0, 90.0, 135.0, -179.0, -135.0, -90.0, -45.0, 0.0]
        while True:
            current_yaw = drone.log_data.imu.yaw

            adj_current = 360.0 + current_yaw if current_yaw < 0.0 else current_yaw
            adj_target  = 360.0 + target_yaw if target_yaw < 0.0 else target_yaw

            delta = round(adj_target - adj_current, 2)

            if (abs(delta) >= 180.0 and delta > 0.0):
                delta -= 360.0
            elif (abs(delta) >= 180.0 and delta < 0.0):
                delta += 360.0

            direction = ""

            if (delta > 10.0):
                direction = "fast CW "
                drone.clockwise(60)
            elif (delta > 0.0):
                direction = "slow CW "
                drone.clockwise(10)
            elif (delta < -10.0):
                direction = "fast CCW "
                drone.counter_clockwise(60)
            elif (delta < 0.0):
                direction = "slow CCW "
                drone.counter_clockwise(10)

            print(direction + str(delta) + " from " + str(adj_current) + " to " + str(adj_target))

            if (math.isclose(0.0, delta, abs_tol=1.0)):
                # close enough for government work!
                print("done!")
                drone.clockwise(0)
                sleep(1) # stabilize
                drone.take_picture()
                sleep(4)
                target_yaw = yaws.pop()

            if (len(yaws) == 0):
                break

            sleep(0.1)

        sleep(2)
        drone.land()
    except Exception as ex:
        print(ex)
    finally:
        drone.quit()

if __name__ == '__main__':
    test()
