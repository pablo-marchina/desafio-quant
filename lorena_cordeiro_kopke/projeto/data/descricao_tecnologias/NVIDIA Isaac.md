NVIDIA Isaac

Resumo: robotics, simulação e autonomia.

Url: https://developer.nvidia.com/isaac

NVIDIA Isaac
Ready to jump-start your AI robot development? NVIDIA Isaac™ is the ideal place to start. This open robotics development platform consists of simulation and robot learning frameworks, NVIDIA® CUDA®-accelerated libraries, AI models, and reference workflows to create autonomous mobile robots (AMRs), robot arms, manipulators, and humanoids.

NVIDIA Isaac Libraries and AI Models
NVIDIA robotics full-stack CUDA-acceleration libraries and optimized AI models give you a better, more efficient way to develop, train, simulate, deploy, operate, and optimize robot systems.

NVIDIA Isaac for Manipulation
Motion Planning
NVIDIA cuMotion is an NVIDIA CUDA-accelerated library that helps solve robot motion planning problems at scale by running multiple trajectory optimizations simultaneously to return the best solution.

Pose Estimation and Tracking
FoundationPose is a foundation model for 6D pose estimation and tracking of novel objects. It tracks and estimates the pose of unseen objects and can handle challenging object properties (textureless, glossy, tiny) and scenes with fast motion or severe occlusions.

Depth Estimation
FoundationStereo is a foundation model designed to achieve strong zero-shot generalization for stereo matching.

Object Detection
SyntheticaDETR is a pretrained model for object detection in indoor environments. It can be used as a front end to pose estimators like FoundationPose, so it can localize objects using 2D bounding boxes before pose estimation.

Isaac TeleOp
Collect high-quality human demonstrations through teleoperation in the real- world and simulation.

NVIDIA Isaac for Mobility

Real-Time 3D Occupancy Grid
Enable robots to identify obstacles in 3D spaces up to five meters away and generate a 2D costmap using the NVIDIA nvblox CUDA-accelerated 3D reconstruction library. Get results 100x faster than with CPU-centric methods.


Accelerated Stereo Visual Odometry and SLAM
Get sub-1% trajectory errors for real-time, CUDA-accelerated visual SLAM across diverse sensors and platforms using NVIDIA cuVSLAM.
Seamlessly navigate environments with sparse visual features or repetitive patterns by fusing input from multiple viewpoints. Get started with pycuVSLAM.

Generalizable End-to-End Mobility
Train vision-based mobility foundation models using NVIDIA COMPASS, enabling navigation across robot types and changing environments.
The workflow includes synthetic data generation with NVIDIA Isaac Sim™ and Cosmos™ Transfer, model training and post-training in Isaac Lab, and deployment with NVIDIA Jetson Orin™ or Thor™.


NVIDIA Isaac ROS (Robot Operating System) is built on the open-source ROS 2. This collection of NVIDIA CUDA-accelerated computing packages and AI models streamlines and expedites the development of advanced AI robotics applications.

Simulation and Robot Learning
Design, simulate, test, and train your AI-based robots and autonomous machines in a physically based virtual environment.

NVIDIA Isaac Sim
NVIDIA Isaac Sim, built on NVIDIA Omniverse™, gives you a faster way to develop autonomous machines in a physically based virtual environment.

Together, NVIDIA Cosmos™ and Isaac Sim let you generate synthetic data from 3D scenes for training perception robots. 

NVIDIA Isaac Lab
This lightweight sample application is built on Isaac Sim and optimized for robot learning and robot foundation model training.

NVIDIA Isaac GR00T for Humanoid Robot Development
NVIDIA Isaac GR00T is an open reference platform for general-purpose humanoid robots that enables developers to build, train, test, and deploy AI-powered robots.

It comprises open data and data pipelines, an open robot foundation model, simulation frameworks, middleware, NVIDIA CUDA-X™ accelerated runtime libraries, and NVIDIA Jetson Thor™ for real-time robot inference and control.