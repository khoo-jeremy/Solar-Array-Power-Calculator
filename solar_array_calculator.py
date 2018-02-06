"""Calculates the power profile of the 'Polaris' solar car model.

Given the latitude, longitude, GMT time offset, year, month, day, and angle that the car is facing relative to the 
West direction, finds the power generated by the solar cells on the 'Polaris' solar car model at any time at that 
location throughout the day.
"""

import sys
import numpy as np
import os.path
import sunmodel as sm


class NodeVector:
    """Contains information about a vector consisting of all nodes in a 3D mesh.

        Attributes:
            node_num: int representing number of nodes in mesh.
            node_vec: list containing node positions; beginning at index 1 (as opposed to 0).
    """

    def __init__(self):
        """Initializes NodeVector with no nodes."""
        self.node_num = 0
        self.node_vec = []


class ElementVector:
    """Contains information about a vector consisting of all finite elements in a 3D mesh.
        
        Finite elements are closed areas in 3D space represented defined by distinct nodes. 

        Attributes:
            ele_num: int representing number of elements in mesh.
            ele_type: int representing area geometry; namely, a triangle is type 2.
            ele_vec: list containing element definitions defined by nodes; beginning at index 1 (as opposed to 0).
    """

    def __init__(self):
        """Initializes ElementVector with no elements."""
        self.ele_num = 0
        self.ele_type = 0
        self.ele_vec = []


def car_solar_flux(lat, lon, timezone, year, month, day, hour, minute, z_rotate):
    """Returns the solar flux (solar power) produced by the car and surrounding useful information.

        Solar flux is dependent on the provided solar car mesh file (test.msh). This is a theoretical model under ideal 
        conditions, namely not considering cloud cover and other weather effects. It does take into account the Sun's 
        position in space and the atmospheric effects on sun intensity. 

        Args:
            lat: latitude in degrees, float.
            lon: longitude in degrees, float.
            timezone: GMT time offset, negative or positive int.
            year: calender year, int.
            month: calendar month, int.
            day: calendar day, int.
            hour: hour in 24 hour clock, int.
            minute: minute, float.
            z_rotate: angle offset in degrees relative to the [W] direction that the car faces.

        Returns: 
            flux: solar flux in Watts.
            area: surface area of the 3D mesh in m^2.
            ele_count: number of finite elements in the mesh.
            neg_count: number of elements with their normal pointing downwards; i.e. not facing the sun.
        """

    # Initialize variables to be used in file read.
    # Node list will be stored in node_vector.
    # Triangular element list will be stored in element_vector.
    node_read = 0
    node_vector = []
    element_read = 0
    element_vector = []
    # Read pre-defined 3D mesh file in gmsh format.
    with open("test.msh", "r") as f:
        for line in f:
            # Identify beginning and end of sections in mesh file.
            if line.find("$Nodes") >= 0:
                node_read = 1
                continue
            if line.find("$EndNodes") >= 0:
                node_read = 0
                continue
            if line.find("$Elements") >= 0:
                element_read = 1
                continue
            if line.find("$EndElements") >= 0:
                element_read = 0
                continue
            # This line has number of nodes; index node_vector by 1 to match index to node.
            if node_read == 1:
                node_read = 2
                x = 0
                node_vector.append(x)
                continue
            # Create list of node positions.
            if node_read == 2:
                x = NodeVector()
                sl = line.split()
                x.node_num = np.int(sl[0])
                x.node_vec = [np.float(sl[1]), np.float(sl[2]), np.float(sl[3])]
                node_vector.append(x)
            # This line has number of elements; index element_vector by 1 to match index to element.
            if element_read == 1:
                element_read = 2
                x = 0
                element_vector.append(x)
                continue
            # Create list of triangular elements.
            if element_read == 2:
                x = ElementVector()
                sl = line.split()
                x.ele_num = np.int(sl[0])
                x.ele_type = np.int(sl[1])
                if x.ele_type == 2:
                    x.ele_vec = [np.int(sl[5]), np.int(sl[6]), np.int(sl[7])]
                    element_vector.append(x)

    # Create list of the normal vectors of the elements.
    normal_vec = []
    area = 0
    for i in range(1, np.size(element_vector)):
        # Get indexes of nodes of the elements.
        n0 = element_vector[i].ele_vec[0]
        n1 = element_vector[i].ele_vec[1]
        n2 = element_vector[i].ele_vec[2]
        # Get two vectors to input into cross product based on the triangle node ordering reference specified at
        # http://www.manpagez.com/info/gmsh/gmsh-2.2.6/gmsh_65.php#SEC65
        #
        #   v
        #   ^
        #   |
        #   2
        #   |`\
        #   |  `\
        #   |    `\
        #   |      `\
        #   |        `\
        #   0----------1 --> u
        #
        v1 = np.subtract(node_vector[n1].node_vec, node_vector[n0].node_vec)
        v2 = np.subtract(node_vector[n2].node_vec, node_vector[n0].node_vec)
        normal = np.cross(v1, v2)
        if normal[2] < 0:
            normal = np.multiply(normal, -1)
        normal_vec.append(normal)
        # Find the area of the 3D mesh.
        ele_area = np.linalg.norm(normal) / (2*1000000)
        area += ele_area

    # Fetch the important solar angles and generate the sun vector
    # Angle conventions:
    #   N (+y), S (-y), E (+x), W (-x)
    #   -x direction is direction car is facing, facing W.
    #   Azimuth (azimuth) is the degree angle clockwise from N.
    #   Elevation (h_corr) is in Z axis.
    [h_corr, azimuth, julian_day] = sm.solar_angles(lat, lon, timezone, year, month, day, hour, minute)
    irr = sm.irradiance(h_corr, julian_day)
    sun_vec = np.zeros(3)
    sun_vec[0] = np.sin(np.deg2rad(h_corr))
    sun_vec[1] = np.cos(np.deg2rad(azimuth))
    sun_vec[2] = np.sin(np.deg2rad(julian_day))
    # Rotate sun vector due to effect of z-rotation (direction the car is facing):
    #   Z-axis rotation only (x and y axis rotation not yet included).
    #   Sun rotating ccw == car rotating cw; thus can apply rotation matrix to sun instead of car.
    sun_vec[0] = sun_vec[0] * np.cos(np.deg2rad(z_rotate)) - sun_vec[1] * np.sin(np.deg2rad(z_rotate))
    sun_vec[1] = sun_vec[0] * np.sin(np.deg2rad(z_rotate)) + sun_vec[1] * np.cos(np.deg2rad(z_rotate))
    # Take the dot product of the sun rays and car area normals to find solar flux
    # For all negative dot products, reduce to 0 (no sun on elements not facing the sun).
    # Divide by 1000000 for the conversion from mm^2 --> m^2
    flux = 0
    eff = 0.239
    ele_count = np.size(element_vector)
    neg_count = 0
    for j in range(0, np.size(element_vector)-1):
        temp = eff * irr * 0.5 * np.dot(sun_vec, normal_vec[j]) / 1000000
        if temp < 0:
            temp = 0
            neg_count += 1
        flux = flux + temp
    return flux, area, ele_count, neg_count

