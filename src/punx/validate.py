#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# :author:    Pete R. Jemian
# :email:     prjemian@gmail.com
# :copyright: (c) 2017, Pete R. Jemian
#
# Distributed under the terms of the Creative Commons Attribution 4.0 International Public License.
#
# The full license is in the file LICENSE.txt, distributed with this software.
#-----------------------------------------------------------------------------


"""
validate files against the NeXus/HDF5 standard

PUBLIC

.. autosummary::
   
   ~Data_File_Validator

INTERNAL

.. autosummary::
   
   ~ValidationItem

"""

import collections
import h5py
import logging
import os
import re

import punx
import punx.finding
import punx.utils
import punx.nxdl_manager


SLASH = "/"
INFORMATIVE = int((logging.INFO + logging.DEBUG)/2)
logger = punx.utils.setup_logger(__name__)
CLASSPATH_OF_NON_NEXUS_CONTENT = "non-NeXus content"
VALIDITEMNAME_STRICT_PATTERN = r'[a-z_][a-z0-9_]*'


class Data_File_Validator(object):
    """
    manage the validation of a NeXus HDF5 data file
    
    USAGE


    1. make a validator with a certain schema::
        
        validator = punx.validate.Data_File_Validator()    # default
    
       You may have downloaded additional NeXus Schema (NXDL file sets).
       If so, pick any of these by name as follows::

        validator = punx.validate.Data_File_Validator("v3.2")
        validator = punx.validate.Data_File_Validator("master")
        
    2. use to validate a file or files::
        
        result = validator.validate(hdf5_file_name)
        result = validator.validate(another_file)
        
    3. close the HDF5 file when done with validation::
        
        validator.close()

    PUBLIC METHODS
    
    .. autosummary::
       
       ~close
       ~validate

    INTERNAL METHODS

    .. autosummary::
       
       ~build_address_catalog
       ~_group_address_catalog_
       ~validate_item_name

    """

    def __init__(self, ref=None):
        self.h5 = None
        self.validations = []      # list of Finding() instances
        self.addresses = collections.OrderedDict()     # dictionary of all HDF5 address nodes in the data file
        self.classpaths = {}
        self.validation_keys = {}
        self.regexp_cache = {}
        self.manager = punx.nxdl_manager.NXDL_Manager(ref)

    
    def close(self):
        """
        close the HDF5 file (if it is open)
        """
        if punx.utils.isHdf5FileObject(self.h5):
            self.h5.close()
            self.h5 = None
    
    def record_finding(self, v_item, key, status, comment):
        """
        prepare the finding object and record it
        """
        f = punx.finding.Finding(v_item.h5_address, key, status, comment)
        self.validations.append(f)
        v_item.validations[key] = f
        if key not in self.validation_keys:
            self.validation_keys[key] = []
        self.validation_keys[key].append(f)
        return f
    
    def validate(self, fname):
        '''
        start the validation process from the file root
        '''
        if not os.path.exists(fname):
            raise punx.FileNotFound(fname)
        self.fname = fname

        if self.h5 is not None:
            self.close()            # left open from previous call to validate()
        try:
            self.h5 = h5py.File(fname, 'r')
        except IOError:
            logger.error("Could not open as HDF5: " + fname)
            raise punx.HDF5_Open_Error(fname)

        self.build_address_catalog()

        # 1. check all objects in file (name is valid, ...)
        for v_list in self.classpaths.values():
            for v_item in v_list:
                self.validate_item_name(v_item)

        # 2. check all base classes against defaults
        for k, v_item in self.addresses.items():
            if punx.utils.isHdf5Group(v_item.h5_object) \
            or punx.utils.isHdf5FileObject(v_item.h5_object):
                self.validate_group(v_item)

        # 3. check application definitions
        for k in ("/NXentry/definition", "/NXentry/NXsubentry/definition"):
            if k in self.classpaths:
                for v_item in self.classpaths[k]:
                    self.validate_application_definition(v_item.parent)

        # 4. check for default plot
    
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    
    def build_address_catalog(self):
        """
        find all HDF5 addresses and NeXus class paths in the data file
        """
        self._group_address_catalog_(None, self.h5)

    def _group_address_catalog_(self, parent, group):
        """
        catalog this group's address and all its contents
        """
        def addClasspath(v):
            if v.classpath not in self.classpaths:
                self.classpaths[v.classpath] = []
            self.classpaths[v.classpath].append(v)
            logger.log(INFORMATIVE, "NeXus classpath: " + v.classpath)
        def get_subject(parent, o):
            v = ValidationItem(parent, o)
            self.addresses[v.h5_address] = v
            logger.log(INFORMATIVE, "HDF5 address: " + v.h5_address)
            addClasspath(v)
            for k, a in sorted(o.attrs.items()):
                av = ValidationItem(v, a, attribute_name=k)
                self.addresses[av.h5_address] = av
                addClasspath(av)
            return v

        obj = get_subject(parent, group)
        parent = self.classpaths[obj.classpath][-1]
        for item in group:
            if punx.utils.isHdf5Group(group[item]):
                self._group_address_catalog_(parent, group[item])
            else:
                get_subject(parent, group[item])

    def validate_item_name(self, v_item, key=None):
        from .validations import item_name
        item_name.validate_item_name(self, v_item, key)

    def validate_group(self, v_item):
        """
        validate the NeXus content of a HDF5 data file group
        """
        key = "NeXus_group"
        if v_item.classpath == CLASSPATH_OF_NON_NEXUS_CONTENT:
            self.record_finding(
                v_item, 
                key,
                punx.finding.OK, 
                "not a NeXus group")
            return
        if v_item.classpath.startswith("/NX"):
            nx_class = v_item.nx_class
        elif v_item.classpath == "":
            nx_class = "NXroot"    # handle as NXroot
        else:
            raise ValueError("unexpected: " + str(v_item))
        # print(str(v_item), v_item.name, v_item.classpath)
        
        # TODO: Verify that items presented in data file are valid with base class
        # TODO: Verify that items specified in base class are compliant with file
        
        self.validate_NX_class_attribute(v_item, nx_class)
        # TODO: validate attributes - both HDF5-supplied & NXDL-specified
        # TODO: validate symbols - both HDF5-supplied & NXDL-specified
        # TODO: validate fields - both HDF5-supplied & NXDL-specified
        # TODO: validate links - both HDF5-supplied & NXDL-specified
        # TODO: validate groups - both HDF5-supplied & NXDL-specified
        pass # TODO
    
    def validate_application_definition(self, v_item):
        """
        validate group as a NeXus application definition
        """
        pass # TODO
    
    def validate_NX_class_attribute(self, v_item, nx_class):
        """
        validate proper use of NeXus groups
        
        Only known base classes (and contributed definitions intended 
        for use as base classes) can be used as groups in a NeXus data file.
        Application definitions are used in a different way, as an overlay 
        on a parent NXentry or NXsubentry group, and declared in the 
        `definition` field of that parent group.
        """
        known = nx_class in self.manager.classes
        status = punx.finding.TF_RESULT[known]
        msg = nx_class + ": recognized NXDL specification"
        self.record_finding(v_item, "known NXDL", status, msg)

        if known:
            as_base = self.usedAsBaseClass(nx_class)
            status = punx.finding.TF_RESULT[as_base]
            self.manager.classes[nx_class].category
            msg = nx_class
            if self.manager.classes[nx_class].category == "base_classes":
                msg += ": known NeXus base class"
            else:
                msg += ": known NeXus contributed definition used as base class"
            self.record_finding(v_item, "NeXus base class", status, msg)

    def usedAsBaseClass(self, nx_class):
        """
        returns bool: is the nx_class a base class?
        
        NXDL specifications in the contributed definitions directory 
        could be intended as either a base class or an 
        application definition.  NeXus provides no easy identifier 
        for this difference.  The most obvious distinction between
        them is the presence of the `definition` field 
        in the :ref:`NXentry` group of an application definition.
        This field is not present in base classes.
        """
        nxdl_def = self.manager.classes.get(nx_class, None)
        if nxdl_def is None:
            return False
        if nxdl_def.category == "applications":
            return False
        if nxdl_def.category == "base_classes":
            return True
        # now, need to work at it a bit
        # *Should* only be one NXentry group but that is not a rule.
        if len(nxdl_def.fields) == 0 and \
           len(nxdl_def.links) == 0 and \
           len(nxdl_def.groups) == 1: # maybe ...
            entry_group = nxdl_def.groups.values()[0]
            # TODO: test entry_group.NX_class == "NXentry" but that attribute is not ready yet!
            # assume OK
            return "definition" not in entry_group.fields
        return True


class ValidationItem(object):
    """
    HDF5 data file object for validation
    """
    
    def __init__(self, parent, obj, attribute_name=None):
        assert(isinstance(parent, (ValidationItem, type(None))))
        self.parent = parent
        self.validations = {}    # validation findings go here
        self.h5_object = obj
        if hasattr(obj, 'name'):
            self.h5_address = obj.name
            if obj.name == SLASH:
                self.name = SLASH
            else:
                self.name = obj.name.split(SLASH)[-1]
            self.classpath = self.determine_NeXus_classpath()
        else:
            self.name = attribute_name
            if parent.classpath == CLASSPATH_OF_NON_NEXUS_CONTENT:
                self.h5_address = None
                self.classpath = CLASSPATH_OF_NON_NEXUS_CONTENT
            else:
                self.h5_address = parent.h5_address + "@" + self.name
                self.classpath = str(parent.classpath) + "@" + self.name
    
    def __str__(self, *args, **kwargs):
        try:
            import h5py._hl
            if isinstance(self.h5_object, h5py._hl.files.File):
                object_type = "HDF5 file root"
            elif isinstance(self.h5_object, h5py._hl.group.Group):
                object_type = "HDF5 group"
            elif isinstance(self.h5_object, h5py._hl.dataset.Dataset):
                object_type = "HDF5 dataset"
            else:
                object_type = type(self.h5_object)
            terms = collections.OrderedDict()
            terms["name"] = self.name
            terms["type"] = object_type
            terms["classpath"] = self.classpath
            s = ", ".join(["%s=%s" % (k, str(v)) for k, v in terms.items()])
            return "ValidationItem(" + s + ")"
        except Exception as _exc:
            return object.__str__(self, *args, **kwargs)

    def determine_NeXus_classpath(self):
        """
        determine the NeXus class path
        
        :see: http://download.nexusformat.org/sphinx/preface.html#class-path-specification
        
        EXAMPLE
        
        Given this NeXus data file structure::
            
            /
                entry: NXentry
                    data: NXdata
                        @signal = data
                        data: NX_NUMBER
        
        The HDF5 address of the plottable data is: ``/entry/data/data``.
        The NeXus class path is: ``/NXentry/NXdata/data
        
        For the "signal" attribute of this HDF5 address: ``/entry/data``,
        the NeXus class path is: ``/NXentry/NXdata@signal
        """
        if self.name == SLASH:
            return ""
        else:
            h5_obj = self.h5_object

            classpath = str(self.parent.classpath)
            if classpath == CLASSPATH_OF_NON_NEXUS_CONTENT:
                logger.log(INFORMATIVE, "%s is not NeXus content" % h5_obj.name)
                return CLASSPATH_OF_NON_NEXUS_CONTENT

            if not classpath.endswith(SLASH):
                if punx.utils.isHdf5Group(h5_obj):
                    if "NX_class" in h5_obj.attrs:
                        nx_class = punx.utils.decode_byte_string(h5_obj.attrs["NX_class"])
                        self.nx_class = nx_class    # only for groups
                        logger.log(INFORMATIVE, "NeXus base class: " + nx_class)
                    else:
                        logger.log(INFORMATIVE, "HDF5 group is not NeXus: " + self.h5_address)
                        return CLASSPATH_OF_NON_NEXUS_CONTENT
                else:
                    nx_class = self.name
                classpath += SLASH + nx_class
            return classpath


if __name__ == '__main__':
    print("Start this module using:  python main.py validate ...")
    exit(0)
