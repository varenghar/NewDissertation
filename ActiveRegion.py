import numpy as np
import sunpy.map
from PIL import Image
import cv2
import Database as db
import ObjectPreparation as prep


# Function reconstructs active region using chain code,
# convert pixel coordinate to Carrington coordinate system,
# make synthesis of observation and returns carrington coordinates as well
# as pixel coordinates (needed for sunspot synthesis)
# chains - 2D array with chain codes
# startx - x coordinate of chain code start position in pixels
# starty - y coordinate of chain code start position in pixels
# filname - array with filenames of original FITS images
# track_id - track_id of objects
# ar_id - id of active regions
# date - date of observation of active regions
def get_shapes(chains, startx, starty, filename, track_id, ar_id, date):
    filename = prep.decode_filename(filename)
    date = prep.decode_date(date)
    all_track = []
    all_intensities = []
    all_coords_carr = []
    all_contours_pix = []
    counter = 0
    # Loop goes through array of chain code
    # and calculates coordinate of each of the pixel of the contour
    for c in chains:
        xpos = startx[counter]  # Starting position of contour
        ypos = starty[counter]
        t_id = track_id[counter]    # tracking data
        a_id = ar_id[counter]      # unique id
        file = filename[counter]   # filename
        ar_date = date[counter]    # date of observation

        # Check if exists in database
        result = db.load_ar_from_database(a_id)
        if not result == ([], [], [], []):
            # check if object go through the end of map and finish at the beginning
            broken = (max(result[2][0][0]) - min(result[2][0][0])) > 358
            if not broken:
                all_track += result[0]
                all_intensities += result[1]
                all_coords_carr += result[2]
                all_contours_pix.append(result[3])
        else:
            # Calculate ar contour in pixel, carrington longitude and latitude
            ar, lon, lat = prep.get_shape(chain=c, xpos=xpos, ypos=ypos, file=file)
            all_contours_pix.append(ar)
            ar_inten = calculate_ar_intensity(ar, file)
            db.add_ar_to_database(a_id, ar_date, t_id, ar_inten, [lon, lat], ar)

            broken = max(lon) - min(lon) > 358  # check if object go through the end of map and finish at the beginning
            if not broken:
                all_track.append(str(t_id))
                all_intensities.append(ar_inten)
                all_coords_carr.append([lon, lat])

        counter += 1

    mer = merge_id_with_object(all_coords_carr, all_contours_pix, all_track, all_intensities)
    carrington_synthesis, pixel_synthesis = make_ar_synthesis(mer)

    return carrington_synthesis, pixel_synthesis


# Creates dictionary where key is track_id of active region
# and values are tuple of ar's intensity, carrington coordinates and
# pixel coordinates
def merge_id_with_object(carr_coords, pix_coords,  track_id, ar_intensity):
    ar_with_id = {}
    ar_with_id[track_id[0]] = [(ar_intensity[0], carr_coords[0], pix_coords[0])]
    if len(carr_coords) == len(track_id):
        for x in range(1, len(track_id)):
            if track_id[x] in ar_with_id:
                ar_with_id[track_id[x]].append((ar_intensity[x], carr_coords[x], pix_coords[x]))
            else:
                ar_with_id[track_id[x]] = [(ar_intensity[x], carr_coords[x], pix_coords[x])]

    return ar_with_id


# Finds pixel coordinates of pixels inside the ar contour
# Ar contour is drawn using pixel coordinate system
# AR is filled with black colour
# Function checks then which pixels are black and reveal indexes of these pixels
def get_contour_pixels_indexes(contour):
    contour = np.array(contour)
    im = Image.new('RGB', (4096, 4096), (0, 0, 0))  # create blank image
    cv_image = np.array(im)  # convert PIL image to opencv image
    cv2.fillPoly(cv_image, pts=[contour], color=(255, 255, 255))  # draw active region
    indexes = np.where(cv_image == 255)  # get all indexes of active region pixels

    return indexes


# coord - coordinates of contour of ar
# filename - FITS file associated with that ar
def calculate_ar_intensity(coord, filename):
    filename = "images//" + filename
    coord = get_contour_pixels_indexes(coord)  # find all pixels inside the contour
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
def make_ar_synthesis(ar_with_id):
    all_contours_carr = []
    all_contours_pix = []
    for id, coords in ar_with_id.items():
        regions = []  # contain the intensity values of AR with track_id=id
        ar_intensity_with_cords = {} # key = ar_intensity, value = (carrington_coord, pixel_coord)
        for y in coords:
            regions.append(y[0])
            ar_intensity_with_cords[y[0]] = (y[1], y[2])

        average = calculate_average_ar_intensity(regions)  # calculate the average intenisty value

        # from all intensities from track_id = id, choose value which is the closest
        # to the average value
        closest_to_average = min(regions, key=lambda x: abs(x - average))
        maximum = max(regions)
        synthesis, pixel_coord = ar_intensity_with_cords[maximum]

        all_contours_carr.append(synthesis)
        all_contours_pix.append(pixel_coord)

    return all_contours_carr, all_contours_pix


# Calculates average instensity of active regions
# ar_intensities - array with ar intensities
def calculate_average_ar_intensity(ar_intensities):
    sum = 0
    # go through array of pixel values and add them
    for x in ar_intensities:
        sum += x

    average = sum / len(ar_intensities)  # calculate average
    return average


if __name__ == '__main__':
    # ActiveRegion + ObjectPreparation test
    from DataAccess import DataAccess

    ar_data = DataAccess('2003-10-21T00:00:00', '2003-10-24T00:00:00', 'AR', 'SOHO', 'MDI')

    ar_chain_encoded = prep.decode_and_split(ar_data.get_chain_code())

    ar_carr_synthesis, ar_pix_synthesis = get_shapes(ar_chain_encoded, ar_data.get_pixel_start_x(),
                                                     ar_data.get_pixel_start_y(), ar_data.get_filename(),
                                               ar_data.get_noaa_number(), ar_data.get_ar_id(), ar_data.get_date())

    prep.display_object(ar_carr_synthesis, [])