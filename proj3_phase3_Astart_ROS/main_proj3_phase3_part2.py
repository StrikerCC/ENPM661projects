#!/usr/bin/env python2

import sys
import argparse
import rospy
from geometry_msgs.msg import Twist


from utils.space import space2DWithObstacleAndClearance
from utils.planning import Astart
from utils.robot import turtlebot


# default input args
DEFAULT_START = [-4, -4, 0]
DEFAULT_GOAL = [4, 4]
DEFAULT_RPM = [100, 200]
DEFAULT_CLEARANCE = 0.01


def generate_trajectory(path, r, L):
    """Convert a given path to a fixed-timestep trajectory.
    """
    trajectory = []
    for node in path:
        action = node.parent_action

        # skip nodes without parent action (e.g. first)
        if action is None:
            continue

        msg = Twist()

        # compute twist message from given actions (convert to m/s, rad/s)
        msg.linear.x = r * (action[0] + action[1]) / 120.0
        msg.angular.z = r * (action[1] - action[0]) / (60.0 * L)
        trajectory.append(msg)
    return trajectory


if __name__ == "__main__":
    state_start = [-4, -4, 0]
    state_goal = [4, 4]
    timestep = 0.1

    # initialize as ROS node
    rospy.init_node('planner', anonymous=True)
    publisher = rospy.Publisher('cmd_vel', Twist, queue_size=10)
    sleep_time = timestep * 60.0

    # generate obstacle map
    map_ = space2DWithObstacleAndClearance()
    """add obstacle into map"""
    map_.add_circular_obstacle((90, 70), 70 / 2)
    # map_.add_rectangle_obstacle((48, 108), width=150, height=20, angle=35)
    # map_.add_polygon_obstacle([(200, 230), (230, 230), (230, 240), (210, 240),
    #                            (210, 270), (230, 270), (230, 280), (200, 280)])
    # map_.add_ellipsoid_obstacle((246, 145), 60 / 2, 120 / 2)


    robot_ = turtlebot()
    clearance = 10
    map_ = space2DWithObstacleAndClearance(clearance=clearance + robot_.get_radius())
    if map_.invalidArea(robot_.teleport(state_start)) or map_.invalidArea(robot_.teleport(state_goal)):
        print("start location and goal location is ok")

    """planing"""
    robot_.teleport(state_start)
    planning = Astart(retrieve_goal_node=True)
    success, optimal_path = planning.searc(state_start, state_goal, robot_, map_, tolerance=clearance, filepath=r'results/output.txt')
    if not success:
        print('cannot find a solution to the goal')
        sys.exit(1)

    # control to path
    traj = generate_trajectory(optimal_path, robot_.get_wheel_radius(), robot_.get_dis_wheel())

    # control to plan (open loop)
    print("Publishing desired velocity commands to /cmd_vel")
    for msg in traj:
        publisher.publish(msg)
        rospy.sleep(sleep_time)

    # publish stop message at the end
    publisher.publish(Twist())
    print("Finished commanded velocities.")

    rospy.spin()