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
import json


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


def encode_filename(filenames):
    files = []

    for f in filenames:
        if type(f) is bytes:
            f = f.decode("utf-8")

        f = f.replace(":", "_")
        files.append(f)

    return files

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
        ar = []
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

            ar.append([xpos, ypos])

            carr = convert_to_carrington(xpos, ypos, filename)
            if not (math.isnan(carr.lon.deg) or math.isnan(carr.lat.deg)):
                lon.append(carr.lon.deg)  # Add calculated position to array
                lat.append(carr.lat.deg)
            else:
                print("Problem with converting pixel. It will be ignored.")


        broken = max(lon) - min(lon) > 355  # check if object go through the end of map and finish at the beginning


        all_contours_pix.append(ar)

        if not broken:
            all_contours_carr.append((lon, lat))

        counter += 1

    return all_contours_carr, all_contours_pix


# Go through array with chain code and calculate pixel coordinates
# using chain code.
# chains - 2D array with chain codes
# startx - x coordinate of chain code start position in pixels
# starty - y coordinate of chain code start position in pixels
# return - array with coordinates of the contour of the object
def get_shapes2(chains, startx, starty):
    all_contours_pix = []

    counter = 0
    # Loop goes through array of chain code
    # and calculates coordinate of each of the pixel of the contour
    for c in chains:
        xpos = startx[counter]  # Starting position of contour
        ypos = starty[counter]
        ar = []
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

            ar.append([xpos, ypos])

        all_contours_pix.append(ar)

        counter += 1

    return all_contours_pix



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

# Creates dictionary where key is track_id of active region
# and values are pixel coordinates of active region
def merge_id_with_ar(coords, track_id, filename):
    print("merge_id_with_ar START")
    filename = encode_filename(filename)
    ar_with_id = {}
    ar_with_id[track_id[0]] = [(filename[0], coords[0])]

    if len(coords) == len(track_id):
        for x in range(1, len(track_id)):
            if track_id[x] in ar_with_id:
                ar_with_id[track_id[x]].append((filename[x], coords[x]))
                print("appending")
                print(track_id[x], [track_id[x]])
            else:
                ar_with_id[track_id[x]] = [(filename[x], coords[x])]
                print("creating")
                print(track_id[x], ar_with_id[track_id[x]])

    return ar_with_id


# Finds pixel coordinates of pixels inside the ar contour
def get_contour_pixels_indexes(contour, image_shape):
    print("get_contour_pixels_indexes() START ")
    contour = np.array(contour)
    im = Image.new('RGB', (4096, 4096), (0, 0, 0))  # create blank image of FITS image size
    cv_image = np.array(im)  # convert PIL image to opencv image
    cv2.fillPoly(cv_image, pts=[contour], color=(255, 255, 255))  # draw active region
    indexes = np.where(cv_image == 255)  # get all indexes of active region pixels

    return indexes


# coord - coordinates of contour of ar
# filename - FITS file associated with that ar
def calculate_ar_intensity(coord, filename):
    print("calculate_ar_intensity() START ")
    coord = get_contour_pixels_indexes(coord, filename)  # find all pixels inside the contour
    pixels_number = len(coord)
    intensity = 0.0
    map = sunpy.map.Map(filename)
    # calculate intensity
    for x in range(0, pixels_number):
        intensity = intensity + map.data[coord[0][x]][coord[1][x]]

    return intensity


# Function takes dictionary with AR coords and their track_id
# Goes through dictionary, calculates the intensity of each AR
# makes synthesis by calculating the average of the same AR and by
# choosing the closest AR to the average
def make_synthesis(ar_with_id):
    all_contours_carr = []
    for id, coords in ar_with_id.items():
        regions = []  # contain the intensity values of AR with track_id=id
        ar_intensity_with_cords = {} # key = ar_intensity, value = coords
        for y in coords:
            ar_intensity = calculate_ar_intensity(y[1], y[0])
            regions.append(ar_intensity)
            ar_intensity_with_cords[ar_intensity] = y[1]

        print("id = ", id)
        print("regions = ", regions)
        average = calculate_average_ar_intensity(regions)  # calculate the average intenisty value
        print("average = ", average)
        # from all intensities from track_id = id, choose value which is the closest
        # to the average value
        closest_to_average = min(regions, key=lambda x: abs(x - average))
        maximum = max(regions)
        print("closest", closest_to_average)
        print("max", maximum)
        # synthesis[id] = intensity_cords[closest_to_average]
        synthesis = ar_intensity_with_cords[maximum]

        lon = []
        lat = []
        # convert choosen ar from pixel coordinates to carrington
        for ar in synthesis:
            carr = convert_to_carrington(ar[0], ar[1], "aia.lev1.171A_2011-07-30T00_00_24.34Z.image_lev1.fits")
            if not (math.isnan(carr.lon.deg) or math.isnan(carr.lat.deg)):
                lon.append(carr.lon.deg)  # Add calculated position to array
                lat.append(carr.lat.deg)
            else:
                print("Problem with converting pixel. It will be ignored.")

        broken = max(lon) - min(lon) > 355  # check if object go through the end of map and finish at the beginning

        if not broken:
            all_contours_carr.append((lon, lat))

    return all_contours_carr


def add_to_database(coords):
    import sqlite3
    conn = sqlite3.connect('ar_carrington.db')
    curs = conn.cursor()
    #curs.execute('''CREATE TABLE ar_test(coords)''')


    js = json.dumps(coords)
    curs.execute('''INSERT INTO ar_test VALUES(?)''', (js, ))
    #js2 = curs.execute("SELECT * FROM ar_test").fetchall()
    c = curs.execute("SELECT * FROM ar_test").fetchall()

    kurwa = c[0][0]

    le = json.loads(kurwa)

    return le


# ar_intensities - array with ar intensities
def calculate_average_ar_intensity(ar_intensities):
    print("calculate_average_ar_intensity() START ")
    sum = 0
    # go through array of pixel values and add them
    for x in ar_intensities:
        sum += x

    average = sum / len(ar_intensities) # calculate average
    return average


# coordinates - array with numpy arrays with coordinates of the contour of the object
# Function creates polygon by using array with coordinates of the contour of the object
def display_object(coordinates):
    print("display_object() START ")
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

    data = DataAccess('2011-07-30T00:00:24', '2011-07-30T00:00:24')

    chain_encoded = encode_and_split(data.get_chain_code())

    cords2 = get_shapes(chain_encoded, data.get_pixel_start_x(), data.get_pixel_start_y(), "aia1.fits")
    # test = [[123,3556,342,324,234], [144,4], [144,4], [144,4], [144,4], [144,4]]
    # nid = np.array(data.get_track_id())

    # ar_id = merge_id_with_ar(cords2, data.get_track_id(), data.get_filename())
    #
    # syn = make_synthesis(ar_id)

    a = add_to_database(cords2[0])

    display_object(a)