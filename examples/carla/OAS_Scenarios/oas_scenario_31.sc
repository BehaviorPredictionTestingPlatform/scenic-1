
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

threeWayIntersections = []
for intersection in network.intersections:
	if intersection.is3Way:
		threeWayIntersections.append(intersection)

intersection = Uniform(*threeWayIntersections)
# intersection = threeWayIntersections[5]
maneuvers = intersection.maneuvers

straight_manuevers = []
for m in maneuvers:
	if m.type == ManeuverType.STRAIGHT:
		straight_manuevers.append(m)

straight_maneuver = Uniform(*straight_manuevers)
startLane = straight_maneuver.startLane
connectingLane = straight_maneuver.connectingLane
endLane = straight_maneuver.endLane

centerlines = [startLane.centerline, connectingLane.centerline, endLane.centerline]


leftTurn_manuevers = []
for m in maneuvers:
	if m.type == straight_maneuver.conflictingManeuvers:
		leftTurn_manuevers.append(m)

leftTurn_maneuver = Uniform(*leftTurn_manuevers)
ego_L_startLane = leftTurn_maneuver.startLane
ego_L_connectingLane = leftTurn_maneuver.connectingLane
ego_L_endLane = leftTurn_maneuver.endLane

ego_L_centerlines = [ego_L_startLane.centerline, ego_L_connectingLane.centerline, ego_L_endLane.centerline]


ego = Car at ego_L_startLane.centerline[-1],
		with behavior FollowTrajectoryBehavior(target_speed=10, trajectory=ego_L_centerlines)

other = Car at startLane.centerline[-1],
		with behavior FollowTrajectoryBehavior(target_speed=10, trajectory=centerlines)

# require ego arrives right before other does