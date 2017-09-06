
#-----------------------------------------------------------------------------
# :author:    Pete R. Jemian
# :email:     prjemian@gmail.com
# :copyright: (c) 2017, Pete R. Jemian
#
# Distributed under the terms of the Creative Commons Attribution 4.0 International Public License.
#
# The full license is in the file LICENSE.txt, distributed with this software.
#-----------------------------------------------------------------------------


import re

from .. import finding
from .. import utils
from ..validate import logger


def verify(validator):
    c = "need to validate existence of default plot"
    obj = validator.addresses["/"]
    status = finding.TODO
    
    addr = default_plot_v3(validator)
    if addr is not None:
        c = "found by v3: " + addr
        status = finding.OK
    elif default_plot_v2(validator):
        c = "found by v2"
        status = finding.OK
    elif default_plot_v1(validator):
        c = "found by v1"
        status = finding.OK
    else:
        c = "complete path from root not found"
        status = finding.NOTE
    validator.record_finding(obj, "NeXus default plot", status, c)


def default_plot_v3(validator):
    """
    return the HDF5 address of the v3 default plottable data or None
    
    :see: http://download.nexusformat.org/doc/html/datarules.html#version-3
    """
    # The default plot is described only at classpath: /NXentry/NXdata@signal
    # This must result in plottable data..
    # Assume the attribute values are tested elsewhere
    def build_h5_address(v_item, pointer):
        if isinstance(v_item.h5_object, str):
            parent = v_item.parent or v_item
            addr = parent.h5_object.name
        else:
            addr = v_item.h5_object.name
        if not addr.endswith("/"):
            addr += "/"
        addr += utils.decode_byte_string(pointer)
        return addr
    def attribute_points_at_target(validator, v_item, attribute_name, v_target):
        pointer = v_item.h5_object.attrs.get(attribute_name)
        if pointer is None:
            return False
        addr = build_h5_address(v_item, pointer)
        if addr not in v_item.h5_object:
            return False
        return v_target == addr

    test_name = "NeXus default plot v3"
    short_list = list(validator.classpaths.get("/NXentry/NXdata@signal", []))
    # TODO: why not look at every NXdata@signal?

    final_list = []
    for v_item in short_list:
        # check existence of @default attributes, as well
        root, entry, data = v_item.h5_address.split("@")[0].split("/")
        nxdata = validator.addresses["/" + entry + "/" + data]
        nxentry = validator.addresses["/" + entry]
        nxroot = validator.addresses["/"]
        signal_h5_addr = build_h5_address(nxdata, nxdata.h5_object.attrs["signal"])
        t1 = attribute_points_at_target(validator, nxroot, "default", nxentry.h5_address)
        t2 = attribute_points_at_target(validator, nxentry, "default", nxdata.h5_address)
        t3 = attribute_points_at_target(validator, nxdata, "signal", signal_h5_addr)
        t4 = utils.isNeXusDataset(validator.addresses[signal_h5_addr].h5_object)
        if t3 and t4:
            status = finding.OK
            c = "correct default plot setup in /NXentry/NXdata"
            validator.record_finding(v_item, test_name + ", NXdata@signal", status, c)
            status = True   # the minimal satisfaction
        if t1 and t2 and t3 and t4:
            # this is the NIAC2014 test
            final_list.append(v_item)
    
    # TODO: could also test /NXentry/NXdata@axes
    if len(final_list) == 1:
        status = finding.OK
        c = "default plot setup in /NXentry/NXdata"
        validator.record_finding(v_item, test_name, status, c)
        return v_item.h5_address


def default_plot_v2(validator):
    """
    return the HDF5 address of the v2 default plottable data or None
    
    :see: http://download.nexusformat.org/doc/html/datarules.html#version-2
    """
    status = False
    test_name = "NeXus default plot v2"
    short_list = []
    for k, v in validator.classpaths.items():
        if k.endswith("@signal"):
            for v_item in v:
                if utils.isNeXusDataset(v_item.h5_object):
                    short_list.append(v_item)
    
    return status


def default_plot_v1(validator):
    """
    return the HDF5 address of the v1 default plottable data or None
    
    :see: http://download.nexusformat.org/doc/html/datarules.html#version-1
    """
    status = False
    test_name = "NeXus default plot v1"
    return status
