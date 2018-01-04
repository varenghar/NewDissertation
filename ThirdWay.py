import numpy as np
import matplotlib as plt
from astropy.coordinates import SkyCoord
import sunpy.map
import matplotlib.pyplot as plt
from sunpy.coordinates import frames
import astropy.units as u
import matplotlib
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import math
from descartes import PolygonPatch
from PIL import Image
import cv2


# Function takes array with chain codes, encode the chain code,
# then splits into array
def encode_and_split(chain_codes):
    print("encode_and_split() START")
    codes = []

    for chains in chain_codes:
        if type(chains) is bytes:
            chains = chains.decode("utf-8")

        splitted_chain = list(map(int,str(chains)))
        codes.append(splitted_chain)

    return codes

# Go through array with chain code, convert to carrington, draw contour of shape
# using chain code.
# chains - 2D array with chain codes
# startx - x coordinate of chain code start position in pixels
# starty - y coordinate of chain code start position in pixels
# return - array with coordinates of the contour of the object
def get_shapes(chains, startx, starty, filename):
    print("get_shapes() START")
    all_contours_carr = []
    all_contours_pix = []

    counter = 0
    # Loop goes through array of chain code
    # and calculates coordinate of each of the pixel of the contour
    for c in chains:
        xpos = startx[counter]  # Starting position of contour
        ypos = starty[counter]
        lon = []
        lat = []
        x = []
        y = []
        for d in c:
            if d == 0:
                xpos -= 1
            elif d == 1:
                xpos -= 1
                ypos -= 1
            elif d == 2:
                ypos -= 1
            elif d == 3:
                ypos -= 1
                xpos += 1
            elif d == 4:
                xpos += 1
            elif d == 5:
                ypos += 1
                xpos += 1
            elif d == 6:
                ypos += 1
            elif d == 7:
                ypos += 1
                xpos -= 1

            x.append(xpos)
            y.append(ypos)

            carr = convert_to_carrington(xpos, ypos, filename)
            if not (math.isnan(carr.lon.deg) or math.isnan(carr.lat.deg)):
                lon.append(carr.lon.deg)  # Add calculated position to array
                lat.append(carr.lat.deg)
            else:
                print("Problem with converting pixel. It will be ignored.")

        all_contours_pix.append([x, y])

        broken = max(lon) - min(lon) > 355  # check if object go through the end of map and finish at the beginning

        if not broken:
            all_contours_carr.append((lon, lat))

        counter += 1

    return all_contours_carr, all_contours_pix


# Function converts from pixel coordinates to carrington
def convert_to_carrington(lon, lat, filename):
    #print("convert_to_carrington() START ")
    #print('long = {0} lat =  {1}'.format(lon, lat))
    map = sunpy.map.Map(filename)
    # convert from pixel to picture coordinate system
    cords = map.pixel_to_world(lon * u.pix, lat * u.pix)
    # convert from picture coordinate frame to carrington
    carr = cords.transform_to(frames.HeliographicCarrington)

    return carr


def merge_id_with_ar(coords, track_id):
    ar_with_id = {}
    ar_with_id[track_id[0]] = [coords[0]]

    if len(coords) == len(track_id):
        for x in range(1, len(track_id)):
            if track_id[x] in ar_with_id:
                ar_with_id[track_id[x]].append(coords[x])
            else:
                ar_with_id[track_id[x]] = [coords[x]]

    return ar_with_id



def get_contour_pixels_indexes(contour, image_shape):
    print("get_contour_pixels_indexes() START ")
    im = Image.new('RGB', (4096, 4096), (0, 0, 0))  # create blank image of image size
    cv_image = np.array(im)  # convert PIL image to opencv image
    cv2.fillPoly(cv_image, pts=[contour], color=(255, 255, 255))  # draw active region
    indexes = np.where(cv_image == 255)  # get all indexes of active region pixels

    return indexes


def calculate_ar_intensity(coord, filename):
    print("calculate_ar_intensity() START ")
    pixels_number = len(coord)
    intensity = 0.0
    map = sunpy.map.Map(filename)

    for x in range(0, pixels_number):
        intensity = intensity + map.data[coord[0][x]][coord[1][x]]

    return intensity


def make_synthesis(ar_with_id):
    average = {}
    for id, coords in ar_with_id.items():
        regions = []
        for y in coords:
            regions.append(calculate_ar_intensity(y, 'aia1.fits'))

        average[id] = calculate_average_ar_intensity(regions)

    return average


def calculate_average_ar_intensity(ar_intensities):
    print("calculate_average_ar_intensity() START ")
    sum = 0

    for x in ar_intensities:
        sum += x

    average = sum / len(ar_intensities)
    return average


# coordinates - array with numpy arrays with coordinates of the contour of the object
# Function creates polygon by using array with coordinates of the contour of the object
def display_object(coordinates):
    print("display_object() START ")
    #print(coordinates)
    # fig = plt.figure(1, figsize=(10, 5), dpi=90)
    # ax = fig.add_subplot(111)
    fig, ax = plt.subplots(1, figsize=(10, 5))

    latitude_start = -90
    latitude_end = 90
    longitude_start = 0
    longitude_end = 360
    break_between = 30
    break_between_minor = 10

    ax.set_xlim(longitude_start, longitude_end)
    ax.set_ylim(latitude_start, latitude_end)
    ax.set_xticks(np.arange(longitude_start, longitude_end, break_between_minor), minor=True)
    ax.set_yticks(np.arange(latitude_start, latitude_end, break_between_minor), minor=True)
    ax.set_xticks(np.arange(longitude_start, longitude_end, break_between))
    ax.set_yticks(np.arange(latitude_start, latitude_end, break_between))

    ax.grid(which='both')

    # push grid lines behind the elements
    ax.set_axisbelow(True)

    for c in coordinates:
        #plt.scatter(c[0], c[1], marker='o', s=1)
        plt.fill(c[0], c[1])

    plt.show()


if __name__ == '__main__':
    from DataAccess import DataAccess

    data = DataAccess('2011-07-30T00:00:24', '2011-07-30T04:00:24')

    chain_encoded = encode_and_split(data.get_chain_code())

    cords2 = get_shapes(chain_encoded, data.get_pixel_start_x(), data.get_pixel_start_y(), "aia1.fits")

    test = [[123,3556,342,324,234], [144,4], [144,4], [144,4], [144,4], [144,4]]
    nid = np.array(data.get_track_id())

    ar_id = merge_id_with_ar(cords2[1], data.get_track_id())

    print(make_synthesis(ar_id))

   # display_object(cords2[0])


