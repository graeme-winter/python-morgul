import argparse
import configparser
import glob
import os
import sys

import numpy
import h5py

hostname = os.uname()[1]
if "diamond.ac.uk" in hostname:
    hostname = "xxx.diamond.ac.uk"
install = os.path.dirname(os.path.realpath(__file__))


def get_config():
    """Get the local configuration from the installation directory"""
    configuration = configparser.ConfigParser()
    assert (
        "morannon.ini" in configuration.read(os.path.join(install, "morannon.ini"))[0]
    )
    return configuration


config = get_config()


def psi_gain_maps(detector):
    """Read gain maps from installed location, return as 3 x numpy array g0, g1, g2"""
    calib = config[hostname]["calibration"]
    result = {}
    for k in config.keys():
        if k.startswith(detector):
            module = config[k]["module"]
            gain_file = glob.glob(os.path.join(calib, f"M{module}_fullspeed", "*.bin"))
            assert len(gain_file) == 1
            shape = 3, 512, 1024
            count = shape[0] * shape[1] * shape[2]
            gains = numpy.fromfile(
                open(gain_file[0], "r"), dtype=numpy.float64, count=count
            ).reshape(*shape)
            result[f"M{module}"] = gains
    return result


def init(detector):
    maps = psi_gain_maps(detector)

    with h5py.File(f"{detector}_calib.h5", "w") as f:
        for k in sorted(maps):
            g = f.create_group(k)
            g012 = maps[k]
            for j in 0, 1, 2:
                g.create_dataset(f"g{j}", data=g012[j])


def average_pedestal(gain_mode, filename):

    with h5py.File(filename) as f:
        d = f["data"]
        s = d.shape
        image = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)

        for j in range(s[0]):
            i = d[j]
            if gain_mode == 0:
                i[i > 0x3fff] = 0
            elif gain_mode == 2:
                i[i < 0x8000] = 0
            else:
                i[i < 0x4000] = 0
                i[i >= 0x8000] = 0
            image += i

        return image / s[0]

def main():
    parser = argparse.ArgumentParser(
        prog="morannon",
        description="Calibration setup for Jungfrau",
    )
    parser.add_argument("detector")
    parser.add_argument(
        "-i", "--init", action="store_true", help="create initial files"
    )
    parser.add_argument(
        "-0", "--pedestal-0", dest="p0", help="pedestal run at gain mode 0"
    )
    parser.add_argument(
        "-1", "--pedestal-1", dest="p1", help="pedestal run at gain mode 1"
    )
    parser.add_argument(
        "-2", "--pedestal-2", dest="p2", help="pedestal run at gain mode 2"
    )
    args = parser.parse_args()

    assert args.detector

    if args.init:
        init(args.detector)
        return

    assert args.p0
    assert args.p1
    assert args.p2

    p0 = average_pedestal(0, args.p0)
    p1 = average_pedestal(1, args.p1)
    p2 = average_pedestal(2, args.p2)

    with h5py.File(f"{args.detector}_pedestal.h5", "w") as f:
        f.create_dataset(f"p0", data=p0)
        f.create_dataset(f"p1", data=p1)
        f.create_dataset(f"p2", data=p2)


if __name__ == "__main__":
    main()
