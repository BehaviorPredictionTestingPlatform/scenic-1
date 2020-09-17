
try:
	import carla
except ImportError as e:
	raise ModuleNotFoundError('CARLA scenarios require the "carla" Python package') from e

import math

from scenic.syntax.translator import verbosity
if verbosity == 0:	# suppress pygame advertisement at zero verbosity
	import os
	os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
import pygame

from carla import ColorConverter as cc

from scenic.domains.driving.simulators import DrivingSimulator, DrivingSimulation
from scenic.core.simulators import SimulationCreationError
from scenic.syntax.veneer import verbosePrint
import scenic.simulators.carla.utils.utils as utils
import scenic.simulators.carla.utils.visuals as visuals
import scenic.simulators.carla.utils.recording_utils as rec_utils

import numpy as np

class CarlaSimulator(DrivingSimulator):
	def __init__(self, carla_map, address='127.0.0.1', port=2000, timeout=10,
		         render=True, record=False, timestep=0.1):
		super().__init__()
		verbosePrint('Connecting to CARLA...')
		self.client = carla.Client(address, port)
		self.client.set_timeout(timeout)  # limits networking operations (seconds)
		self.world = self.client.load_world(carla_map)
		self.map = carla_map
		self.timestep = timestep

		# Set to synchronous with fixed timestep
		settings = self.world.get_settings()
		settings.synchronous_mode = True
		settings.fixed_delta_seconds = timestep  # NOTE: Should not exceed 0.1
		self.world.apply_settings(settings)
		verbosePrint('Map loaded in simulator.')

		self.render = render  # visualization mode ON/OFF
		self.record = record  # whether to save images to disk

	def createSimulation(self, scene, verbosity=0):
		return CarlaSimulation(scene, self.client, self.map, self.timestep,
							   render=self.render, record=self.record,
							   verbosity=verbosity)

	def toggle_recording(self, record):
		self.record = record

	def is_recording(self):
		return self.record

class CarlaSimulation(DrivingSimulation):
	def __init__(self, scene, client, map, timestep, render, record, verbosity=0):
		super().__init__(scene, timestep=timestep, verbosity=verbosity)
		self.client = client
		self.client.load_world(map)
		self.world = self.client.get_world()
		self.blueprintLib = self.world.get_blueprint_library()
		
		# Reloads current world: destroys all actors, except traffic manager instances
		# self.client.reload_world()
		
		# Setup HUD
		self.render = render
		self.record = record
		if self.render:
			self.displayDim = (1280, 720)
			self.displayClock = pygame.time.Clock()
			self.camTransform = 0
			pygame.init()
			pygame.font.init()
			self.hud = visuals.HUD(*self.displayDim)
			self.display = pygame.display.set_mode(
				self.displayDim,
				pygame.HWSURFACE | pygame.DOUBLEBUF
			)
			self.cameraManager = None

		self.rgb_frame_buffer = []
		self.semantic_frame_buffer = []
		self.lidar_data_buffer = []
		self.bbox_buffer = []

		# Create Carla actors corresponding to Scenic objects
		self.ego = None
		for obj in self.objects:
			# Extract blueprint
			blueprint = self.blueprintLib.find(obj.blueprint)

			# Set up transform
			loc = utils.scenicToCarlaLocation(obj.position, z=obj.elevation, world=self.world)
			rot = utils.scenicToCarlaRotation(obj.heading)
			transform = carla.Transform(loc, rot)
			
			# Create Carla actor
			carlaActor = self.world.try_spawn_actor(blueprint, transform)
			if carlaActor is None:
				raise SimulationCreationError(f'Unable to spawn object {obj}')

			if isinstance(carlaActor, carla.Vehicle):
				carlaActor.apply_control(carla.VehicleControl(manual_gear_shift=True, gear=1))
			elif isinstance(carlaActor, carla.Walker):
				carlaActor.apply_control(carla.WalkerControl())

			# #create by batch
			# batch = []
			# equivVel = utils.scenicSpeedToCarlaVelocity(obj.speed, obj.heading)
			# print(equivVel)
			# batch.append(carla.command.SpawnActor(blueprint, transform, carlaActor).then(carla.command.ApplyVelocity(carla.command.FutureActor, equivVel)))

			obj.carlaActor = carlaActor

			# Check if ego (from carla_scenic_taks.py)
			if obj is self.objects[0]:
				self.ego = obj

				# Set up camera manager and collision sensor for ego
				if self.render:
					camIndex = 0
					camPosIndex = 0
					self.cameraManager = visuals.CameraManager(self.world, carlaActor, self.hud)
					self.cameraManager._transform_index = camPosIndex
					self.cameraManager.set_sensor(camIndex)
					self.cameraManager.set_transform(self.camTransform)
					self.cameraManager._recording = self.record

					if self.record:
						VIEW_WIDTH = self.hud.dim[0]
						VIEW_HEIGHT = self.hud.dim[1]
						VIEW_FOV = 90.0

						bp = self.world.get_blueprint_library().find('sensor.camera.rgb')
						bp.set_attribute('image_size_x', str(VIEW_WIDTH))
						bp.set_attribute('image_size_y', str(VIEW_HEIGHT))
						bp.set_attribute('fov', str(VIEW_FOV))
						ego_hood_transform = carla.Transform(carla.Location(x=0.0, y=0.0, z=2.0))
						self.rgb_cam = self.world.spawn_actor(bp, ego_hood_transform, attach_to=carlaActor)
						self.rgb_cam.listen(self.process_rgb_image)

						# Set up calibration matrix to be used for bounding box projection
						calibration = np.identity(3)
						calibration[0, 2] = VIEW_WIDTH / 2.0
						calibration[1, 2] = VIEW_HEIGHT / 2.0
						calibration[0, 0] = calibration[1, 1] = VIEW_WIDTH / (2.0 * np.tan(VIEW_FOV * np.pi / 360.0))
						self.rgb_cam.calibration = calibration

						bp = self.world.get_blueprint_library().find('sensor.camera.semantic_segmentation')
						bp.set_attribute('image_size_x', str(VIEW_WIDTH))
						bp.set_attribute('image_size_y', str(VIEW_HEIGHT))
						self.semantic_cam = self.world.spawn_actor(bp, ego_hood_transform, attach_to=carlaActor)
						self.semantic_cam.listen(self.process_semantic_image)

						bp = self.world.get_blueprint_library().find('sensor.lidar.ray_cast_semantic')
						lidar_transform = carla.Transform(carla.Location(x=1.6, z=1.7))
						self.lidar_sensor = self.world.spawn_actor(bp, lidar_transform, attach_to=carlaActor)
						self.lidar_sensor.listen(self.process_lidar_data)

		self.world.tick() ## allowing manualgearshift to take effect 

		for obj in self.objects:
			if isinstance(obj.carlaActor, carla.Vehicle):
				obj.carlaActor.apply_control(carla.VehicleControl(manual_gear_shift=False))

		self.world.tick()

		# Set Carla actor's initial speed (if specified)
		for obj in self.objects:
			if obj.speed is not None:
				equivVel = utils.scenicSpeedToCarlaVelocity(obj.speed, obj.heading)
				obj.carlaActor.set_velocity(equivVel)

	def executeActions(self, allActions):
		super().executeActions(allActions)

		# Apply control updates which were accumulated while executing the actions
		for obj in self.agents:
			ctrl = obj._control
			if ctrl is not None:
				obj.carlaActor.apply_control(ctrl)
				obj._control = None

	def step(self):
		# Run simulation for one timestep
		self.world.tick()

		if self.record:
			vehicles = self.world.get_actors().filter('vehicle.*')

			curr_frame_idx = self.world.get_snapshot().frame

			bounding_boxes_3d = rec_utils.BBoxUtil.get_bounding_boxes(vehicles, self.rgb_cam)
			bounding_boxes_2d = rec_utils.BBoxUtil.get_2d_bounding_boxes(bounding_boxes_3d)
			self.bbox_buffer.append((curr_frame_idx, bounding_boxes_2d))

		# Render simulation
		if self.render:
			# self.hud.tick(self.world, self.ego, self.displayClock)
			self.cameraManager.render(self.display)
			# self.hud.render(self.display)
			pygame.display.flip()

	def getProperties(self, obj, properties):
		# Extract Carla properties
		carlaActor = obj.carlaActor
		currTransform = carlaActor.get_transform()
		currLoc = currTransform.location
		currRot = currTransform.rotation
		currVel = carlaActor.get_velocity()
		currAngVel = carlaActor.get_angular_velocity()

		# Prepare Scenic object properties
		velocity = utils.carlaToScenicPosition(currVel)
		speed = math.hypot(*velocity)

		values = dict(
			position=utils.carlaToScenicPosition(currLoc),
			elevation=utils.carlaToScenicElevation(currLoc),
			heading=utils.carlaToScenicHeading(currRot),
			velocity=velocity,
			speed=speed,
			angularSpeed=utils.carlaToScenicAngularSpeed(currAngVel),
		)
		return values

	def process_rgb_image(self, image):
		image.convert(cc.Raw)
		self.rgb_frame_buffer.append(image)

	def process_semantic_image(self, image):
		# Save per-pixel classification for later
		image_classes = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
		image_classes = np.reshape(image_classes, (image.height, image.width, 4))
		# Class is stored in red channel
		image_classes = image_classes[:, :, 2].copy()

		image.convert(cc.CityScapesPalette)

		self.semantic_frame_buffer.append((image, image_classes))

	def process_lidar_data(self, lidar_data):
		self.lidar_data_buffer.append(lidar_data)

	def save_recordings(self, scene_name):
		if not self.record:
			print('No recordings saved; turn on recordings for simulator to enable')
			return

		# Find frame indices for which all sensors have data (so that recordings are synchronized)
		rgb_data = {data.frame: data for data in self.rgb_frame_buffer}
		semantic_data = {data.frame: data for data, _ in self.semantic_frame_buffer}
		frame_class_data = {data.frame: class_data for data, class_data in self.semantic_frame_buffer}
		lidar_data = {data.frame: data for data in self.lidar_data_buffer}
		bbox_data = {frame_idx: bboxes for frame_idx, bboxes in self.bbox_buffer}

		common_frame_idxes = set(rgb_data.keys()).intersection(set(semantic_data.keys())).intersection(lidar_data.keys()).intersection(bbox_data.keys())
		common_frame_idxes = sorted(list(common_frame_idxes))

		rgb_recording = rec_utils.VideoRecording()
		semantic_recording = rec_utils.VideoRecording()
		lidar_recording = rec_utils.LidarRecording()
		bbox_recording = rec_utils.BBoxRecording()

		for frame_idx in common_frame_idxes:
			rgb_recording.add_frame(rgb_data[frame_idx])
			semantic_recording.add_frame(semantic_data[frame_idx])

			classified_lidar_points = [[i.point.x, i.point.y, i.point.z, i.object_tag] for i in lidar_data[frame_idx]]
			lidar_recording.add_frame(classified_lidar_points)

			bbox_recording.add_frame(bbox_data[frame_idx])

		rgb_recording.save('{}_rgb.mp4'.format(scene_name))
		semantic_recording.save('{}_semantic.mp4'.format(scene_name))
		lidar_recording.save('{}_lidar.json'.format(scene_name))
		bbox_recording.save('{}_bboxes.json'.format(scene_name))