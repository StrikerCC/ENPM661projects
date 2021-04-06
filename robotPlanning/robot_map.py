import math
from shapely.geometry import Point, Polygon
import numpy as np
import cv2

from robotPlanning.robot import robot, point_robot, rigid_robot


class geometry():
    def __init__(self, shape, size):
        self.shape_name = shape
        if shape == 'polygon':
            self.size = Polygon(size)
        else:
            self.size = size

    # check if the input point in any obstacle
    def inside(self, point):
        if self.shape_name == 'polygon':
            p_geometry = Point(point[1], point[0])
            return p_geometry.within(self.size)
        elif self.shape_name == 'circular':
            return np.linalg.norm(self.size["center"] - point) <= self.size["radius"]
        elif self.shape_name == 'ellipsoid':
            return ((point[0]-self.size["center"][0])**2)/(self.size['semi_major_axis']**2) + \
                   ((point[1]-self.size["center"][1])**2)/(self.size["semi_minor_axis"]**2) <= 1
        # elif self.shape == 'rectangle':
        # return self.size['dl'][0] <= point[0] <= self.size['ur'][0] and \
        #        self.size['dl'][1] <= point[1] <= self.size['ur'][1]

    def __str__(self):
        return self.shape_name + ' ' + str(self.size)


class map2D:
    def __init__(self, height=300, width=400):
        self.size = (height, width)

    def invalidArea(self, robot_):
        if isinstance(robot_, robot):
            return 0 < robot_.loc()[0] < self.size[0] and 0 < robot_.loc()[1] < self.size[1]
        elif isinstance(robot_, point_robot):
            return 0 < robot_.loc()[0] < self.size[0] and 0 < robot_.loc()[1] < self.size[1]
        elif isinstance(robot_, rigid_robot):
            return 0 < robot_.loc()[0] - robot_.clearance() and robot_.loc()[0] + robot_.clearance() < self.size[0] and 0 < robot_.loc()[1] - robot_.clearance() and robot_.loc()[1] + robot_.clearance() < self.size[1]
        else:
            AssertionError('unknown type of robot for map class')


class map2DWithObstacle(map2D):
    def __init__(self, height=300, width=400):
        super().__init__(height, width)
        self.obstacles = []
        self.map_obstacle = np.zeros(self.size, dtype=np.bool)  # mask obstacle in map. 1 is free space, 0 is obstacle

    def invalidArea(self, robot_):
        if isinstance(robot_, robot):
            return super().invalidArea(robot_) and not self.map_obstacle[robot_.loc()]
        elif isinstance(robot_, point_robot):
            return super().invalidArea(robot_) and not self.map_obstacle[robot_.loc()]
        elif isinstance(robot_, rigid_robot):
            Warning('using map without clearance to navigate rigid robot')
            return super().invalidArea(robot_) and not self.map_obstacle[robot_.loc()]
        else:
            AssertionError('unknown type of robot for map class')

    def isfree(self, index):
        index = index if isinstance(index, tuple) else tuple(index)
        assert len(index) == len(self.size) and isinstance(index[0], int)
        return not self.map_obstacle[index]

    def get_map_obstacle(self):
        return np.copy(self.map_obstacle)

    def add_rectangle_obstacle(self, corner_ll, width, height, angle):
        """

        :param corner_ll:
        :type corner_ll:
        :param width:
        :type width:
        :param height:
        :type height:
        :param angle: angle between the side between low left corner and low right corner and horizontal axis
        :type angle: int or float in degree
        :return:
        :rtype:
        """
        # if not expand: self.obstacles.append(
        #     {'type': 'rectangle', 'corner_ll': corner_ll, 'width': width, 'height': height, 'angle': angle})

        angle *= math.pi / 180
        arctan_h_w = math.atan(height / width)
        diag = math.sqrt(width ** 2 + height ** 2)
        corner_lr = (corner_ll[0] + width * math.cos(angle), corner_ll[1] + width * math.sin(angle))
        corner_ul = (
            corner_ll[0] + height * math.cos(angle + math.pi / 2),
            corner_ll[1] + height * math.sin(angle + math.pi / 2))
        corner_ur = (
            corner_ll[0] + diag * math.cos(arctan_h_w + angle), corner_ll[1] + diag * math.sin(arctan_h_w + angle))
        rectangle = Polygon([corner_ll, corner_lr, corner_ur, corner_ul])

        obstacle = geometry('polygon', rectangle)
        for i in range(self.size[0]):
            for j in range(self.size[1]):
                if obstacle.inside((i, j)):
                    self.map_obstacle[i, j] = True

    def add_polygon_obstacle(self, points):
        # if not expand: self.obstacles.append({'type': 'polygon', 'points': points})

        obstacle = geometry('polygon', points)
        for i in range(self.size[0]):
            for j in range(self.size[1]):
                if obstacle.inside((i, j)):
                    self.map_obstacle[i, j] = True

    def add_circular_obstacle(self, center, radius):
        # if not expand: self.obstacles.append({'type': 'circular', 'center': center, 'radius': radius})

        obstacle = geometry('circular', {"center": np.array(center)[::-1], "radius": radius})
        for i in range(self.size[0]):
            for j in range(self.size[1]):
                if obstacle.inside((i, j)):
                    self.map_obstacle[i, j] = True

    def add_ellipsoid_obstacle(self, center, semi_major_axis, semi_minor_axis):
        # if not expand: self.obstacles.append({'type': 'ellipsoid', 'center': center, 'semi_major_axis': semi_major_axis,
        #                        'semi_minor_axis': semi_minor_axis})

        obstacle = geometry('ellipsoid', {"center": np.array(center)[::-1], "semi_major_axis": semi_minor_axis,
                                                     "semi_minor_axis": semi_major_axis})
        for i in range(self.size[0]):
            for j in range(self.size[1]):
                if obstacle.inside((i, j)):
                    self.map_obstacle[i, j] = True

    def numpy_array_representation(self, map_obstacle, robot_=None):
        img = np.zeros(self.size, dtype=np.uint8)   # free space as 0
        img[map_obstacle] = 75      # obstacle as 0

        if robot_:
            if isinstance(robot_, robot) and isinstance(robot_, point_robot):
                img[robot_.loc()] = 255
                # print('point ', robot_.loc())
            elif isinstance(robot_, rigid_robot):
                Warning('using map without clearance to navigate rigid robot')

                map_2D_with_robot = map2DWithObstacle(self.size[0], self.size[1])            # make a robot map based on obstacle map
                map_2D_with_robot.add_circular_obstacle(robot_.loc(), robot_.clearance())       # treat robot as a obstacle
                robot_in_map = map_2D_with_robot.get_map_obstacle()  # boolean mask representation of robot occupy map space, using numpy array, True if occupied, False if not
                img[robot_in_map] = 255     # robot space as 255
            else:
                AssertionError('unknown type of robot for map class')

        # draw each obstacle on display window
        img = cv2.flip(img, 0)
        return img

    def show(self, robot_=None):
        cv2.imshow('obstacle', self.numpy_array_representation(self.map_obstacle, robot_))
        if cv2.waitKey(0) & 0xFF == ord('q'):
            return


class map2DWithObstacleAndClearance(map2DWithObstacle):
    def __init__(self, height=300, width=400, clearance=20):
        # self.obstacles = []
        super().__init__(height, width)
        self.map_obstacle_expand = np.copy(self.map_obstacle)
        self.clearance = clearance

    def invalidArea(self, robot_):
        if isinstance(robot_, robot):
            return super().invalidArea(robot_) and not self.map_obstacle_expand[robot_.loc()]
        elif isinstance(robot_, point_robot):
            return super().invalidArea(robot_) and not self.map_obstacle_expand[robot_.loc()]
        elif isinstance(robot_, rigid_robot):
            Warning('using map without clearance to navigate rigid robot')
            return super().invalidArea(robot_) and not self.map_obstacle_expand[robot_.loc()]
        else:
            AssertionError('unknown type of robot for map class')

    def add_rectangle_obstacle(self, corner_ll, width, height, angle, expand=False):
        # self.obstacles.append({'type': 'rectangle', 'corner_ll': corner_ll, 'width': width, 'height': height, 'angle': angle})
        # corner_ll, width, height, angle = self.expand(name='rectangle', parameters=[corner_ll, width, height, angle])
        super().add_rectangle_obstacle(corner_ll, width, height, angle)
        self.expand()

    def add_polygon_obstacle(self, points):
        # self.obstacles.append({'type': 'polygon', 'points': points})
        # points = self.expand(name='polygon', parameters=points)
        super().add_polygon_obstacle(points)
        self.expand()

    def add_circular_obstacle(self, center, radius):
        # self.obstacles.append({'type': 'circular', 'center': center, 'radius': radius})
        # radius = self.expand(name='polygon', parameters=radius)
        super().add_circular_obstacle(center, radius)
        self.expand()

    def add_ellipsoid_obstacle(self, center, semi_major_axis, semi_minor_axis, expand=False):
        # self.obstacles.append({'type': 'ellipsoid', 'center': center, 'semi_major_axis': semi_major_axis, 'semi_minor_axis': semi_minor_axis})
        # semi_major_axis, semi_minor_axis = self.expand(name='polygon', parameters=[semi_major_axis, semi_minor_axis])
        super().add_ellipsoid_obstacle(center, semi_major_axis, semi_minor_axis)
        self.expand()

    def expand(self):
        map_obstacle = np.copy(self.map_obstacle).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (self.clearance, self.clearance))
        map_obstacle_expand = cv2.dilate(map_obstacle, kernel=kernel)
        map_obstacle_expand = map_obstacle_expand.astype(bool)
        self.map_obstacle_expand = map_obstacle_expand

    def show(self, robot_=None):
        cv2.imshow('obstacle', self.numpy_array_representation(self.map_obstacle_expand, robot_))
        if cv2.waitKey(0) & 0xFF == ord('q'):
            return

    # def expand(self, name, parameters, clearance):
    #     if name == 'rectangle':
    #         corner_ll, width, height, angle = parameters
    #         angle_diag_horizontal = 0   # angle between horizontal axis and
    #
    #     elif name == 'polygon':
    #         assert isinstance(parameters, list)
    #         # normalize points coordinates
    #         points = parameters
    #         points_np = np.array(points)
    #
    #         # scale points coordinates
    #         centroid = np.mean(points_np)   # use centroid as scale center
    #         mapping = np.array([[]])
    #     elif name == 'circular':
    #         return parameters + clearance
    #     elif name == 'ellipsoid':
    #         semi_major_axis, semi_minor_axis = parameters
    #         return semi_major_axis+clearance, semi_minor_axis+clearance
    #     else:
    #         AttributeError('no such shape', name, ' in class', self.__class__)

