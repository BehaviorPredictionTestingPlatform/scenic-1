
import scenic.simulators.carla.actions as actions
import time
from shapely.geometry import LineString
from scenic.core.regions import regionFromShapelyObject
from scenic.simulators.domains.driving.network import loadNetwork
from scenic.simulators.domains.driving.roads import ManeuverType
loadNetwork('/home/carla_challenge/Desktop/Carla/Dynamic-Scenic/CARLA_0.9.9/Unreal/CarlaUE4/Content/Carla/Maps/OpenDrive/Town03.xodr')

from scenic.simulators.carla.model import *
from scenic.simulators.carla.behaviors import *

simulator = CarlaSimulator('Town03')

MAX_BREAK_THRESHOLD = 1
TERMINATE_TIME = 20

behavior FollowWayPoints(target_speed=20, waypoints = None):
	assert waypoints is not None

	while True:
		nearest_line_points = waypoints.nearestSegmentTo(self.position)
		nearest_line_segment = PolylineRegion(nearest_line_points)
		cte = nearest_line_segment.signedDistanceTo(self.position)
		take actions.FollowLaneAction(target_speed, cte)

fourWayIntersections = []
for intersection in network.intersections:
	if intersection.is4Way:
		fourWayIntersections.append(intersection)

# intersection = Uniform(*fourWayIntersections)
intersection = fourWayIntersections[5]
maneuvers = intersection.maneuvers

straight_manuevers = []
for m in maneuvers:
	if m.type == ManeuverType.STRAIGHT:
		straight_manuevers.append(m)

straight_maneuver = Uniform(*straight_maneuvers)
startLane = straight_maneuver.startLane
connectingLane = straight_maneuver.connectingLane
endLane = straight_maneuver.endLane

centerlines = [startLane.centerline, connectingLane.centerline, endLane.centerline]

ego = Car on startLane.centerline,
		with behavior FollowTrajectoryBehavior(target_speed=10, trajectory=centerlines)

