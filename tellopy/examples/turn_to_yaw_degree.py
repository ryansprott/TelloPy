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

        target_yaw = 180.0
        while True:
            current_yaw = drone.log_data.imu.yaw

            current_neg = current_yaw < 0.0
            target_neg  = target_yaw < 0.0
            adj_current = 360.0 + current_yaw if current_neg else current_yaw
            adj_target  = 360.0 + target_yaw if target_neg else target_yaw

            delta = adj_target - adj_current
            abs_delta = abs(delta)

            if (abs_delta >= 180.0 and delta > 0.0):
                delta -= 360.0
            elif (abs_delta >= 180.0 and delta < 0.0):
                delta += 360.0

            print(str(delta) + " to " + str(adj_target))

            if (delta > 10.0):
                print("fast CW")
                drone.clockwise(70)
            elif (delta > 0.0):
                print("slow CW")
                drone.clockwise(10)
            elif (delta < -10.0):
                print("fast CCW")
                drone.counter_clockwise(70)
            elif (delta < 0.0):
                print("slow CCW")
                drone.counter_clockwise(10)

            if (math.isclose(0.0, delta, abs_tol=0.5)):
                # close enough for government work!
                drone.clockwise(0)
                print("done!")
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
