import rclpy
from rclpy.node import Node
import numpy as np

from geometry_msgs.msg import PoseStamped, Pose, Twist, Quaternion
from art2d2.helper import euler_from_quaternion, quaternion_from_euler

import time

class DrawingNode(Node):

    current_angle = 0.
    target_angle = 0.
    current_point = np.array([0,0])
    target_point = np.array([0,0])
    target_direction = np.array([1, 0])
    waypt_index = 0
    angle_error = 0

    timer_period = 0.05
    timer = None
    vel_publisher = None

    state = "turning"

    waypoints = np.array([
        [0., 0.3],
        [0.3, 0.3],
        [0.3, 0.],
        [0., 0.]
    ])

    def __init__(self):
        super().__init__('drawing_node')

        self.pose_subscriber = self.create_subscription(PoseStamped, '/pose_estimate', self.pose_callback, 10)
        self.current_pose: Pose = Pose()
        # TODO: FIgure out the topic and message type
        
        self.timer = self.create_timer(self.timer_period, self.move)

        # Publish to cmd_vel topic
        self.vel_publisher = self.create_publisher(Twist, "cmd_vel", 10)

        # Pose target publisher
        self.pose_target_publisher = self.create_publisher(PoseStamped, "/pose_target", 10)
        
        # Initialize the first waypoint
        self.target_point = self.waypoints[self.waypt_index, :] #takes the whole row at this index
        delta = self.target_point-self.current_point
        self.target_angle = np.arctan2(delta[1], delta[0])
        self.target_direction = delta / np.linalg.norm(delta)

    def pose_callback(self, pose_msg):
        """
        Store the latest pose published by the localization node
        
        Args:
            self: node object
            pose_msg: Pose
        """
        current_pose = pose_msg.pose # takes pose from /pose_estimate

        current_roll, current_pitch, current_yaw = euler_from_quaternion(
            current_pose.orientation.x,
            current_pose.orientation.y,
            current_pose.orientation.z,
            current_pose.orientation.w
        )
        self.current_angle = current_yaw
        self.current_point = np.array([current_pose.position.x, current_pose.position.y])


    def rotate_to_angle(self):
        """
        Rotates from current angle to desired angle using proportional control
        
        Args:
            self: node object
            target_angle: pose object that represents desired angle
        
        Returns:
            angle_error: difference between desired angle and current angle
        """
        # 1. Find angle error
        # 2. Find how fast we should turn
        # 3. Publish the new velocity command
        # 4. return the angle error
        print(f"Target angle: {self.target_angle}")
        print(f"Current angle: {self.current_angle}")
        angle_error = self.target_angle - self.current_angle
        print(f"Angle error: {angle_error}")
        k_p = 0.3
        omega_out = k_p * angle_error
        max_omega = 0.3
        omega_out = np.clip(omega_out, -max_omega, max_omega)
        vel_out = Twist()
        vel_out.angular.z = omega_out
        self.vel_publisher.publish(vel_out)
        print(f"Turining at: {vel_out.angular.z}")
        return angle_error

    def drive_to_point(self):
        """
        Drives in a straight line from current point to desired point using
        proportional control

        Args:
            self: node object
            target_point: pose object that represents desired point
        
        Returns:
            position_error: difference between desired position and current
                position
        """
        print(f"Target point: {self.target_point}")
        print(f"Current point: {self.current_point}")
        position_error = self.target_point - self.current_point
        projected_position_error = np.dot(position_error, self.target_direction)
        k_p = 0.2
        vel_out = Twist()
        vel_out.linear.x = k_p * projected_position_error
        self.vel_publisher.publish(vel_out)

        print(f"Driving at :{vel_out.linear.x}")
        print(f"Proj. position error: {projected_position_error}m")
        return projected_position_error

    def move(self):
        """
        Moves robot to next waypoint by calling rotation and driving functions,
        loops on every timer tick
        """
        print(self.state)
        if self.state == "turning":
            angle_error = self.rotate_to_angle()
            
            if np.abs(angle_error) < 0.03:
                print("Switching state to driving")
                self.state = "driving"
                
        elif self.state=="driving":
            projected_position_error = self.drive_to_point()
            
            if np.abs(projected_position_error) < 0.03:
                if self.waypt_index < len(self.waypoints) - 1:
                    # Get next waypoint and turn
                    self.waypt_index += 1
                    self.recalculate_targets()
                    self.state = "turning"
                else:
                    # Set velocities to zero
                    # Kill the node
                    zero_vel = Twist()
                    self.vel_publisher.publish(zero_vel)
                    self.destroy_node()
                    print("Done!")
    
    def recalculate_targets(self):
        """
        Increments which waypoint the robot is moving towards.
        """
        print("Calculating new waypoint!")
        self.target_point = self.waypoints[self.waypt_index, :] #takes the whole row at this index
        delta = self.target_point-self.current_point
        self.target_angle = np.arctan2(delta[1], delta[0])
        
        self.target_direction = delta / np.linalg.norm(delta)

        print(f"Target point: {self.target_point}")
        print(f"Delta: {delta}")
        print(f"Target angle: {self.target_angle}")
        print(f"Target direction: {self.target_direction}")

        # make pose target message and publish it to plot in rviz
        pose_target_msg = PoseStamped() # poseStamped message has a header and a pose
        pose_target_msg.header.frame_id = "map"
        pose_target_msg.pose.position.x = self.target_point[0]
        pose_target_msg.pose.position.y = self.target_point[1]
        pose_target_msg.pose.position.z = 0.
        q_target = quaternion_from_euler(0, 0, self.target_angle)
        pose_target_msg.pose.orientation = Quaternion(
            x = q_target[0], y = q_target[1], z = q_target[2], w = q_target[3]
        )
        self.pose_target_publisher.publish(pose_target_msg)

def main(args=None):
    rclpy.init(args=args)
    node = DrawingNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()