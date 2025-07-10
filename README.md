# PX4-ROS2-Gazebo-Omni
An architechture to design and test controllers in PX4 controlling a simulation of the Omnicopter in Gazebo

## Overview
This tutorial shows how to install the simulation environment to run omnicopter simulations in Gazebo using PX4 and ROS2.

This repo is a derivative of Jaeyoung Lim's Offboard example and ARK/Electronics
https://github.com/Jaeyoung-Lim/px4-offboard
https://github.com/ARK-Electronics/ROS2_PX4_Offboard_Example


### Prerequisites
* ROS2 Humble
* PX4 Autopilot
* Micro XRCE-DDS Agent
* px4_msgs
* Ubuntu 22.04
* Python 3.10


## Setup Steps

### Install PX4 Autopilot
To [Install PX4](https://docs.px4.io/main/en/dev_setup/dev_env_linux_ubuntu.html#simulation-and-nuttx-pixhawk-targets) run this code 
```
git clone https://github.com/PX4/PX4-Autopilot.git --recursive -b release/1.15
```

Run this script in a bash shell to install everything

```
bash ./PX4-Autopilot/Tools/setup/ubuntu.sh
```

You will now need to restart your computer before continuing.


### Install ROS2 Humble
To install ROS2 Humble follow the steps [here](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html)

### Install Dependencies

Install Python dependencies as mentioned in the [PX4 Docs](https://docs.px4.io/main/en/ros/ros2_comm.html#install-ros-2) with this code

```
pip3 install --user -U empy pyros-genmsg setuptools
```

I also found that without these packages installed Gazebo has issues loading

```
pip3 install kconfiglib
pip install --user jsonschema
pip install --user jinja2
```

### Build Micro DDS
As mentioned in the [PX4 Docs](https://docs.px4.io/main/en/ros/ros2_comm.html#setup-micro-xrce-dds-agent-client) run this code in order to build MicroDDS on your machine

```
git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent
mkdir build
cd build
cmake ..
make
sudo make install
sudo ldconfig /usr/local/lib/
```

### Setup Workspace
This git repo is intended to be a ROS2 package that is cloned into a ROS2 workspace.

We're going to create a workspace in our home directory, and then clone in this repo and also the px4_msgs repo. 

For more information on creating workspaces, see [here](https://docs.ros.org/en/humble/Tutorials/Workspace/Creating-A-Workspace.html)

Run this code to create a workspace in your home directory

```
mkdir -p ~/offboard_control_ws/src
cd ~/offboard_control_ws/src
```

*offboard_control_ws* is just a name I chose for the workspace. You can name it whatever you want. But after we run *colcon build* you might have issues changing your workspace name so choose wisely.

We are now in the src directory of our workspace. This is where ROS2 packages go, and is where we will clone in our two repos.

### Clone in Packages
We first will need the px4_msgs package. Our ROS2 nodes will rely on the message definitions in this package in order to communicate with PX4. Read [here](https://docs.px4.io/main/en/ros/ros2_comm.html#overview:~:text=ROS%202%20applications,different%20PX4%20releases) for more information.

Be sure you're in the src directory of your workspace and then run this code to clone in the px4_msgs repo

```
git clone https://github.com/PX4/px4_msgs.git -b release/1.15
```

Once again be sure you are still in the src directory of your workspace. Run this code to clone in our example package

```
git clone https://github.com/OmarAGarciaA/PX4-ROS2-Gazebo-Omni.git
```

Run this code to clone the repo



### Building the Workspace
The two packages in this workspace are px4_msgs and px4_offboard. px4_offboard is a ROS2 package that contains the code for the offboard control node that we will implement. It lives inside the ROS2_PX4_Offboard_Example directory.

Before we build these two packages, we need to source our ROS2 installation. Run this code to do that

```
source /opt/ros/humble/setup.bash
```

This will need to be run in every terminal that wants to run ROS2 commands. An easy way to get around this, is to add this command to your .bashrc file. This will run this command every time you open a new terminal window.

To build these two packages, you must be in workspace directory not in src, run this code to change directory from src to one step back i.e. root of your workspace and build the packages

```
cd ..
colcon build
```

If you get the error:
	user@user-G7-7790:~/offboard_control_ws$ colcon build
	Starting >>> px4_msgs
	--- stderr: px4_msgs                         
	CMake Error at /opt/ros/humble/share/rosidl_adapter/cmake/rosidl_adapt_interfaces.cmake:59 (message):
	  execute_process(/usr/bin/python3 -m rosidl_adapter --package-name px4_msgs
	  --arguments-file
	  /home/user/offboard_control_ws/build/px4_msgs/rosidl_adapter__arguments__px4_msgs.json
	  --output-dir
	  /home/user/offboard_control_ws/build/px4_msgs/rosidl_adapter/px4_msgs
	  --output-file
	  /home/user/offboard_control_ws/build/px4_msgs/rosidl_adapter/px4_msgs.idls)
	  returned error code 1:

	  AttributeError processing template 'msg.idl.em'

	  Traceback (most recent call last):

	    File "/opt/ros/humble/local/lib/python3.10/dist-packages/rosidl_adapter/resource/__init__.py", line 51, in evaluate_template
	      em.BUFFERED_OPT: True,

	  AttributeError: module 'em' has no attribute 'BUFFERED_OPT'
	  
	  
You need to:
	pip3 uninstall empy
	pip3 install empy==3.3.4
	cd {your workspace_ws}
	rm -rf build install log
	colcon build --symlink-install

When launching the file, if you get the following error:
	user@user-G7-7790:~/offboard_control_ws$ ros2 launch px4_offboard offboard_velocity_control.launch.py
	Package 'px4_offboard' not found: "package 'px4_offboard' not found, searching: ['/home/user/offboard_control_ws/install/px4_msgs', '/opt/ros/humble']"

You might need to:
	user@user-G7-7790:~/offboard_control_ws$ source install/setup.bash 

As mentioned in Jaeyoung Lim's [example](https://github.com/Jaeyoung-Lim/px4-offboard/blob/master/doc/ROS2_PX4_Offboard_Tutorial.md) you will get some warnings about setup.py but as long as there are no errors, you should be good to go.


After this runs, we should never need to build px4_msgs again. However, we will need to build px4_offboard every time we make changes to the code. To do this, and save time, we can run
```
colcon build --packages-select px4_offboard
```

If you tried to run our code now, it would not work. This is because we need to source our current workspace. This is always done after a build. To do this, be sure you are in the src directory, and then run this code

```
source install/setup.bash
```

We will run this every time we build. It will also need to be run in every terminal that we want to run ROS2 commands in.


### Running the Code
This example has been designed to run from one launch file that will start all the necessary nodes. The launch file will run a python script that uses gnome terminal to open a new terminal window for MicroDDS and Gazebo.

Run this code to start the example

```
ros2 launch px4_offboard offboard_control.launch.py
```

This will run numerous things. In no particular order, it will run:

* processes.py in a new window
   * MicroDDS in a new terminal window
   * Gazebo will open in a second tab in the same terminal window
      * Gazebo GUI will open in it's own window
* control.py in a new window
   * Sends ROS2 Teleop commands to the /offboard_velocity_cmd topic based on keyboard input
* RVIZ could be open in a new window if it is uncommented from the launch file
* velocity_control.py runs as it's own node, and is the main node of this example

Once everything is running, you should be able to focus into the control.py terminal window, arm, and takeoff. The controls are only Throttle in z axis using "s" key with apply a positive throttle
* W: - z Throttle
* S: + z Throttle
* A: N/A
* D: N/A
* Up Arrow: N/A
* Down Arrow: N/A
* Left Arrow: N/A
* Right Arrow: N/A
* Space: Arm/Disarm

Pressing *Space* will arm the drone. Wait a moment and it will takeoff and switch into offboard mode. You can now control it using the above keys. If you land the drone, it will disarm and to takeoff again you will need to toggle the arm switch off and back on with the space bar. 


## Closing Simulation *IMPORTANT*
When closing the simulation, it is very tempting to just close the terminal windows. However, this will leave Gazebo running in the background, potentially causing issues when you run Gazebo in the future. To correctly end the Gazebo simulation, go to it's terminal window and click *Ctrl+C*. This will close Gazebo and all of it's child processes. Then, you can close the other terminal windows.
 

## Side Notes
/home/omarg/PX4-Autopilot/Tools/simulation/gz/worlds
Location of the file to change solver parameters
	
	
	
	
	
	
