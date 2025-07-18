#!/usr/bin/env python
############################################################################
#
# Ours
#
###############################################
import rclpy
from rclpy.node import Node
import numpy as np
from rclpy.clock import Clock
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy

from px4_msgs.msg import OffboardControlMode
from px4_msgs.msg import TrajectorySetpoint
from px4_msgs.msg import VehicleStatus
from px4_msgs.msg import VehicleAttitude
from px4_msgs.msg import VehicleOdometry
from px4_msgs.msg import VehicleCommand
from px4_msgs.msg import VehicleTorqueSetpoint, VehicleThrustSetpoint
from geometry_msgs.msg import Twist, Vector3
from math import pi
from std_msgs.msg import Bool


class OffboardControl(Node):

    def __init__(self):
        super().__init__('minimal_publisher')
        self.start_time = Clock().now().nanoseconds / 1e9

        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )

        qos_profile_odom = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )

        #Create subscriptions
        self.status_sub = self.create_subscription(
            VehicleStatus,
            '/fmu/out/vehicle_status',
            self.vehicle_status_callback,
            qos_profile)
        
        self.offboard_velocity_sub = self.create_subscription(
            Twist,
            '/offboard_velocity_cmd',
            self.offboard_velocity_callback,
            qos_profile)

        self.odometry_sub = self.create_subscription(
            VehicleOdometry,
            '/fmu/out/vehicle_odometry',
            self.odometry_callback,
            qos_profile_odom)
        
        self.attitude_sub = self.create_subscription(
            VehicleAttitude,
            '/fmu/out/vehicle_attitude',
            self.attitude_callback,
            qos_profile)
        
        self.my_bool_sub = self.create_subscription(
            Bool,
            '/arm_message',
            self.arm_message_callback,
            qos_profile)


        #Create publishers
        self.publisher_offboard_mode = self.create_publisher(OffboardControlMode, '/fmu/in/offboard_control_mode', qos_profile)
        #self.publisher_velocity = self.create_publisher(Twist, '/fmu/in/setpoint_velocity/cmd_vel_unstamped', qos_profile)
        self.publisher_trajectory = self.create_publisher(TrajectorySetpoint, '/fmu/in/trajectory_setpoint', qos_profile)
        self.vehicle_command_publisher_ = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", 10)

        self.publisher_thrust = self.create_publisher(VehicleThrustSetpoint, '/fmu/in/vehicle_thrust_setpoint', qos_profile)
        self.publisher_torque = self.create_publisher(VehicleTorqueSetpoint, '/fmu/in/vehicle_torque_setpoint', qos_profile)


        
        #creates callback function for the arm timer
        # period is arbitrary, just should be more than 2Hz
        arm_timer_period = .1 # seconds
        self.arm_timer_ = self.create_timer(arm_timer_period, self.arm_timer_callback)

        # creates callback function for the command loop
        # period is arbitrary, just should be more than 2Hz. Because live controls rely on this, a higher frequency is recommended
        # commands in cmdloop_callback won't be executed if the vehicle is not in offboard mode
        timer_period = 0.001  # seconds

        self.timer = self.create_timer(timer_period, self.cmdloop_callback)

        self.nav_state = VehicleStatus.NAVIGATION_STATE_MAX
        self.arm_state = VehicleStatus.ARMING_STATE_ARMED
        self.velocity = Vector3()
        self.velocity.x = 0.0
        self.velocity.y = 0.0
        self.velocity.z = 0.0
        self.yaw = 0.0  #yaw value we send as command
        self.trueYaw = 0.0  #current yaw value of drone
        self.offboardMode = False
        self.flightCheck = False
        self.myCnt = 0
        self.arm_message = False
        self.failsafe = False
        self.current_state = "IDLE"
        self.last_state = self.current_state
        self.trajectory_time_offset = None



    def arm_message_callback(self, msg):
        self.arm_message = msg.data
        self.get_logger().info(f"Arm Message: {self.arm_message}")

    #callback function that arms, takes off, and switches to offboard mode
    #implements a finite state machine
    def arm_timer_callback(self):

        match self.current_state:
            case "IDLE":
                if(self.flightCheck and self.arm_message == True):
                    self.current_state = "ARMING"
                    self.get_logger().info(f"Arming")

            case "ARMING":
                if(not(self.flightCheck)):
                    self.current_state = "IDLE"
                    self.get_logger().info(f"Arming, Flight Check Failed")
                elif(self.arm_state == VehicleStatus.ARMING_STATE_ARMED and self.myCnt > 10):
                    self.current_state = "TAKEOFF"
                    self.get_logger().info(f"Arming, Takeoff")
                self.arm() #send arm command

            case "TAKEOFF":
                if(not(self.flightCheck)):
                    self.current_state = "IDLE"
                    self.get_logger().info(f"Takeoff, Flight Check Failed")
                elif(self.nav_state == VehicleStatus.NAVIGATION_STATE_AUTO_TAKEOFF):
                    self.current_state = "LOITER"
                    self.get_logger().info(f"Takeoff, Loiter")
                self.arm() #send arm command
                self.take_off() #send takeoff command

            # waits in this state while taking off, and the 
            # moment VehicleStatus switches to Loiter state it will switch to offboard
            case "LOITER": 
                if(not(self.flightCheck)):
                    self.current_state = "IDLE"
                    self.get_logger().info(f"Loiter, Flight Check Failed")
                elif(self.nav_state == VehicleStatus.NAVIGATION_STATE_AUTO_LOITER):
                    self.current_state = "OFFBOARD"
                    self.get_logger().info(f"Loiter, Offboard")
                self.arm()

            case "OFFBOARD":
                if(not(self.flightCheck) or self.arm_state != VehicleStatus.ARMING_STATE_ARMED or self.failsafe == True):
                    self.current_state = "IDLE"
                    self.get_logger().info(f"Offboard, Flight Check Failed")
                self.state_offboard()

        if(self.arm_state != VehicleStatus.ARMING_STATE_ARMED):
            self.arm_message = False

        if (self.last_state != self.current_state):
            self.last_state = self.current_state
            self.get_logger().info(self.current_state)

        self.myCnt += 1

    def state_offboard(self):
        self.myCnt = 0
        self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1., 6.)
        self.offboardMode = True   

    # Arms the vehicle
    def arm(self):
        self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
        self.get_logger().info("Arm command send")

    # Takes off the vehicle to a user specified altitude (meters)
    def take_off(self):
        self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_TAKEOFF, param1 = 1.0, param7=5.0) # param7 is altitude in meters
        self.get_logger().info("Takeoff command send")

    #publishes command to /fmu/in/vehicle_command
    def publish_vehicle_command(self, command, param1=0.0, param2=0.0, param7=0.0):
        msg = VehicleCommand()
        msg.param1 = param1
        msg.param2 = param2
        msg.param7 = param7    # altitude value in takeoff command
        msg.command = command  # command ID
        msg.target_system = 1  # system which should execute the command
        msg.target_component = 1  # component which should execute the command, 0 for all components
        msg.source_system = 1  # system sending the command
        msg.source_component = 1  # component sending the command
        msg.from_external = True
        msg.timestamp = int(Clock().now().nanoseconds / 1000) # time in microseconds
        self.vehicle_command_publisher_.publish(msg)

    #receives and sets vehicle status values 
    def vehicle_status_callback(self, msg):

        if (msg.nav_state != self.nav_state):
            self.get_logger().info(f"NAV_STATUS: {msg.nav_state}")
        
        if (msg.arming_state != self.arm_state):
            self.get_logger().info(f"ARM STATUS: {msg.arming_state}")

        if (msg.failsafe != self.failsafe):
            self.get_logger().info(f"FAILSAFE: {msg.failsafe}")
        
        if (msg.pre_flight_checks_pass != self.flightCheck):
            self.get_logger().info(f"FlightCheck: {msg.pre_flight_checks_pass}")

        self.nav_state = msg.nav_state
        self.arm_state = msg.arming_state
        self.failsafe = msg.failsafe
        self.flightCheck = msg.pre_flight_checks_pass


    #receives Twist commands from Teleop and converts NED -> FLU
    def offboard_velocity_callback(self, msg):
        #implements NED -> FLU Transformation
        # X (FLU) is -Y (NED)
        self.velocity.x = -msg.linear.y
        # Y (FLU) is X (NED)
        self.velocity.y = msg.linear.x
        # Z (FLU) is -Z (NED)
        self.velocity.z = -msg.linear.z
        # A conversion for angular z is done in the attitude_callback function(it's the '-' in front of self.trueYaw)
        self.yaw = msg.angular.z

    #receives current trajectory values from drone and grabs the yaw value of the orientation
    def attitude_callback(self, msg):
        orientation_q = msg.q

        #trueYaw is the drones current yaw value
        self.trueYaw = -(np.arctan2(2.0*(orientation_q[3]*orientation_q[0] + orientation_q[1]*orientation_q[2]), 
                                  1.0 - 2.0*(orientation_q[0]*orientation_q[0] + orientation_q[1]*orientation_q[1])))

    def odometry_callback(self,msg):
    
        self.current_position = np.array([msg.position[0], msg.position[1], msg.position[2]])
        self.current_velocity = np.array([msg.velocity[0], msg.velocity[1], msg.velocity[2]])
        
        # self.get_logger().info(
        #     f"Pos [x y z]: [{msg.position[0]:.2f} {msg.position[1]:.2f} {msg.position[2]:.2f}] | "
        #     f"Vel [vx vy vz]: [{msg.velocity[0]:.2f} {msg.velocity[1]:.2f} {msg.velocity[2]:.2f}]" )
        
    #publishes offboard control modes and velocity as trajectory setpoints
    def cmdloop_callback(self):
        if(self.offboardMode == True):
            # Publish offboard control modes

            # If both position and thust/torque are set to True the position controller would keep the omni stabilized in orientation
            # The omni will NOT listen to any position references. Instead it would take Thrust inputs.

            times = Clock().now().nanoseconds / 1e9 - self.start_time
            # self.get_logger().info(f"Elapsed time: {times}")

            # Starts a timer at zero to use as argument for time dependent trajectories (40 is enough after takeoff)
            # Trajectory time is zero until times is > 40. Make sure to compute controller knowing this.
            if times > 40:
                self.trajectory_time_offset = self.trajectory_time_offset or Clock().now().nanoseconds / 1e9
                trajectory_time = Clock().now().nanoseconds / 1e9 - self.trajectory_time_offset
                # self.get_logger().info(f"Elapsed trajectory time: {trajectory_time:.2f}")    
            else:
                trajectory_time = 0.0   

            self.get_logger().info(f"Elapsed trajectory time: {trajectory_time:.2f}")     
           
         


            offboard_msg = OffboardControlMode()
            offboard_msg.timestamp = int(Clock().now().nanoseconds / 1000)

            offboard_msg.position = True
            offboard_msg.velocity = False
            offboard_msg.acceleration = False
            offboard_msg.attitude = False
            offboard_msg.body_rate = False
            offboard_msg.thrust_and_torque = True

            self.publisher_offboard_mode.publish(offboard_msg)            


            # Controller would be performed here:

            #yaw = some time * 0.5/2 + np.sin(4)

            # Compute velocity in the world frame
            cos_yaw = np.cos(self.trueYaw)
            sin_yaw = np.sin(self.trueYaw)
            velocity_world_x = (self.velocity.x * cos_yaw - self.velocity.y * sin_yaw)
            velocity_world_y = (self.velocity.x * sin_yaw + self.velocity.y * cos_yaw)

            # Create and publish TrajectorySetpoint message with NaN values for position and acceleration
            trajectory_msg = TrajectorySetpoint()
            trajectory_msg.timestamp = int(Clock().now().nanoseconds / 1000)

            trajectory_msg.velocity[0] = float('nan')
            trajectory_msg.velocity[1] = float('nan')
            trajectory_msg.velocity[2] = float('nan')

            trajectory_msg.position[0] = 0.0#float('nan')#0#velocity_world_x
            trajectory_msg.position[1] = 0.0#float('nan')#0#velocity_world_y
            trajectory_msg.position[2] = 0.0#float('nan')#-50#self.velocity.z

            trajectory_msg.acceleration[0] = float('nan')
            trajectory_msg.acceleration[1] = float('nan')
            trajectory_msg.acceleration[2] = float('nan')

            trajectory_msg.jerk[0] = float('nan')
            trajectory_msg.jerk[1] = float('nan')
            trajectory_msg.jerk[2] = float('nan')

            # trajectory_msg.thrust[0] = float('nan')
            # trajectory_msg.thrust[1] = float('nan')
            # trajectory_msg.thrust[2] = float('nan')
            trajectory_msg.yaw = float('nan')
            trajectory_msg.yawspeed = float('nan')

            thrust_msg = VehicleThrustSetpoint()
            thrust_msg.timestamp = int(Clock().now().nanoseconds / 1000)
            thrust_msg.xyz[0] = 0.0  # Thrust in body-X (N)
            thrust_msg.xyz[1] = 0.0#500  # Thrust in body-Y (N)
            thrust_msg.xyz[2] = -self.velocity.z  # Thrust in body-Z (N)
            self.publisher_thrust.publish(thrust_msg)

            torque_msg = VehicleTorqueSetpoint()
            torque_msg.timestamp = int(Clock().now().nanoseconds / 1000)

            # Set desired torques in body frame (normalized, typically between -1 and 1)
            torque_msg.xyz[0] = 0.0  # roll torque
            torque_msg.xyz[1] = -self.velocity.x    # pitch torque
            torque_msg.xyz[2] = 0.0  # yaw torque

            self.publisher_torque.publish(torque_msg)

            #self.publisher_trajectory.publish(trajectory_msg)

            #Note: Setting up a thrust command instead of a position command makes the drone land right after taking off with an error


def main(args=None):
    rclpy.init(args=args)

    offboard_control = OffboardControl()

    rclpy.spin(offboard_control)

    offboard_control.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
