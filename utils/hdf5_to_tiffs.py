import os
import sys

import fabio
from PIL import Image


def read_data_file(filename):
    with fabio.open(filename) as fabio_img:

        if fabio_img.nframes == 1:
            data = fabio_img.data
            hdr = fabio_img.getheader()

            hdf_data = [data]
            hdf_header = [hdr]

        else:
            hdf_data = []
            hdf_header = []

            hdf_data.append(fabio_img.data)
            hdf_header.append(fabio_img.getheader())

            for i in range(1, fabio_img.nframes):
                fabio_img = fabio_img.next()
                hdf_data.append(fabio_img.data)
                hdf_header.append(fabio_img.getheader())

    return hdf_data, hdf_header


def create_tiffs(img_data, dir, prefix):
    i = 1
    for data in img_data:
        tif_file_name = dir + os.sep + prefix + '_{:04d}'.format(i) + '.tif'
        Image.fromarray(data).save(tif_file_name)
        i += 1


if __name__ == '__main__':
    filename = sys.argv[1]
    path = os.path.dirname(filename)
    prefix = os.path.basename(filename).rsplit('.', 1)[0]

    img_data, img_hdr = read_data_file(filename)
    create_tiffs(img_data, path, prefix)
