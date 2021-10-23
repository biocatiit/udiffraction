import os
import sys

import fabio
import tifffile


def read_data_file(fn):
    with fabio.open(fn) as fabio_img:

        if fabio_img.nframes == 1:
            data = fabio_img.data
            hdf_data = [data]

        else:
            hdf_data = [fabio_img.data]

            for i in range(1, fabio_img.nframes):
                fabio_img = fabio_img.next()
                hdf_data.append(fabio_img.data)

    return hdf_data


def create_tiffs(img_data, metadata, dir, prefix):
    i = 1
    for data in img_data:
        tif_file_name = dir + os.sep + prefix + '_{:04d}'.format(i) + '.tif'
        extra_tags = [("ImageDescription", 's', 0, metadata, True)]
        tifffile.imsave(tif_file_name, data, extratags=extra_tags)
        i += 1


def read_meta_data(meta_fn):
    with open(meta_fn) as meta:
        return meta.read()


if __name__ == '__main__':
    filename = sys.argv[1]
    path = os.path.dirname(filename)
    prefix = os.path.basename(filename).rsplit('.', 1)[0]
    metadata = ''
    if len(sys.argv) > 2:
        metadata_filename = sys.argv[2]
        metadata = read_meta_data(metadata_filename)

    img_data = read_data_file(filename)
    create_tiffs(img_data, metadata, path, prefix)
