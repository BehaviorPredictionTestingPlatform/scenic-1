
import scenic.simulators.carla.actions as actions
import time
from shapely.geometry import LineString
from scenic.core.regions import regionFromShapelyObject
from scenic.simulators.domains.driving.network import loadNetwork
from scenic.simulators.domains.driving.roads import ManeuverType
loadNetwork('/home/carla_challenge/Downloads/Town01.xodr')

from scenic.simulators.carla.model import *
from scenic.simulators.carla.behaviors import *

simulator = CarlaSimulator('Town01')

MAX_BREAK_THRESHOLD = 1
TERMINATE_TIME = 20


behavior EgoBehavior(thresholdDistance, target_speed=20, trajectory = None):
	assert trajectory is not None
	brakeIntensity = 0.7

	try: 
		FollowTrajectoryBehavior(target_speed=15, trajectory=trajectory)

	interrupt when distanceToAnyCars(car=self, thresholdDistance=thresholdDistance):
		take actions.SetBrakeAction(brakeIntensity)


threeWayIntersections = []
for intersection in network.intersections:
	if intersection.is3Way:
		threeWayIntersections.append(intersection)

intersection = Uniform(*threeWayIntersections)
maneuvers = intersection.maneuvers

leftTurn_manuevers = []
for m in maneuvers:
	if m.type == ManeuverType.LEFT_TURN:
		leftTurn_manuevers.append(m)

leftTurn_maneuver = Uniform(*leftTurn_manuevers)
ego_L_startLane = leftTurn_maneuver.startLane
ego_L_connectingLane = leftTurn_maneuver.connectingLane
ego_L_endLane = leftTurn_maneuver.endLane
ego_L_centerlines = [ego_L_startLane.centerline, ego_L_connectingLane.centerline, ego_L_endLane.centerline]


other_leftTurn_manuevers = []
for m in leftTurn_maneuver.conflictingManeuvers:
	if m.type == ManeuverType.LEFT_TURN:
		other_leftTurn_manuevers.append(m) 

leftTurn_maneuver = Uniform(*other_leftTurn_manuevers)
other_L_startLane = leftTurn_maneuver.startLane
other_L_connectingLane = leftTurn_maneuver.connectingLane
other_L_endLane = leftTurn_maneuver.endLane

other_L_centerlines = [other_L_startLane.centerline, other_L_connectingLane.centerline, other_L_endLane.centerline]

ego = Car on ego_L_startLane.centerline,
		with behavior EgoBehavior(target_speed=10, trajectory=ego_L_centerlines, thresholdDistance = 20)

other = Car at other_L_startLane.centerline[-1],
		with behavior FollowTrajectoryBehavior(target_speed=10, trajectory=other_L_centerlines)


# require that other car reaches the intersection before the ego car