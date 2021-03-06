
'''
test punx tests/nxdl_schema module
'''

import lxml.etree
import os
import sys
import tempfile
import unittest

SRCPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, SRCPATH)
from punx import cache_manager, nxdl_schema


class MyClass(object):
    '''
    used when testing  nxdl_schema.render_class_str()
    '''
    
    def __init__(self):
        self.this = None
        self.that = 'that has a value'

    def __str__(self, *args, **kws): 
        return nxdl_schema.render_class_str(self)


class Test_Functions(unittest.TestCase):

    def test_namespace_dictionary(self):
        ns = nxdl_schema.get_xml_namespace_dictionary()
        self.assertTrue(isinstance(ns, dict))
        self.assertTrue('xs' in ns)
        self.assertTrue('nx' in ns)

    def test_render_class_str(self):
        obj = MyClass()
        self.assertTrue(isinstance(obj, MyClass))
        s = str(obj)
        self.assertGreaterEqual(s.find('MyClass'), 0, s)
        self.assertLess(s.find('this'), 0, str(obj.this))
        self.assertGreaterEqual(s.find('that'), 0, str(obj.that))

    def test_get_reference_keys(self):
        cm = cache_manager.CacheManager()
        fname = os.path.join(cm.default_file_set.path, 'nxdl.xsd')
        self.assertTrue(os.path.exists(fname))

        tree = lxml.etree.parse(fname)
        ns = nxdl_schema.get_xml_namespace_dictionary()
        query = '//xs:element/xs:complexType'
        nodes = tree.getroot().xpath(query, namespaces=ns)
        self.assertEqual(len(nodes), 3)
        
        section, line = nxdl_schema.get_reference_keys(nodes[0])
        self.assertTrue(isinstance(section, str))
        self.assertTrue(isinstance(line, str))
        self.assertEqual(section, query.split(':')[-1])
        self.assertEqual(line.split()[0], 'Line')

    def test_get_named_parent_node(self):
        cm = cache_manager.CacheManager()
        fname = os.path.join(cm.default_file_set.path, 'nxdl.xsd')
        self.assertTrue(os.path.exists(fname))

        tree = lxml.etree.parse(fname)
        ns = nxdl_schema.get_xml_namespace_dictionary()
        query = '//xs:complexType//xs:element'
        nodes = tree.getroot().xpath(query, namespaces=ns)
        self.assertGreater(len(nodes), 0)
        
        xml_node = nodes[0]
        self.assertTrue(isinstance(xml_node, lxml.etree._Element))
        parent_node = nxdl_schema.get_named_parent_node(xml_node)
        self.assertTrue(isinstance(parent_node, lxml.etree._Element))
        self.assertTrue('name' in parent_node.attrib)

        query = '/xs:schema/xs:element'
        nodes = tree.getroot().xpath(query, namespaces=ns)
        self.assertEqual(len(nodes), 1)
        parent_node = nxdl_schema.get_named_parent_node(nodes[0])
        self.assertTrue(parent_node.tag.endswith('}schema'))


class Test_Catalog(unittest.TestCase):
    
    def setUp(self):
        pass
    
    def tearDown(self):
        pass

    def test_NXDL_item_catalog_creation(self):
        cm = cache_manager.CacheManager()
        fname = os.path.join(cm.default_file_set.path, 'nxdl.xsd')
        self.assertTrue(os.path.exists(fname))
        
        catalog = nxdl_schema.NXDL_item_catalog(fname)
        self.assertTrue(isinstance(catalog, nxdl_schema.NXDL_item_catalog))

    def issue_67_main(self):
        summary = nxdl_schema.NXDL_Summary(nxdl_schema.NXDL_TEST_FILE)
        count, db = nxdl_schema.print_tree(summary.definition)
        print(count, db)

    def test_NXDL_item_catalog_issue_67_main(self):
        fpath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        sys.path.insert(0, fpath)
        import tests.common
        with tests.common.Capture_stdout() as printed_lines:
            self.issue_67_main()
        # 81 lines when this module run standalone
        # 180 lines when this module run as part of suite
        # 19 while refactoring issue 72
        self.assertIn(len(printed_lines), (19, 81, 180))
        # TODO: could do more extensive testing here

    def test_NXDL_summary(self):
        summary = nxdl_schema.NXDL_Summary(nxdl_schema.NXDL_TEST_FILE)
        self.assertTrue(isinstance(summary, nxdl_schema.NXDL_Summary))
        s2 = nxdl_schema.NXDL_Summary(nxdl_schema.NXDL_TEST_FILE)
        self.assertTrue(isinstance(s2, nxdl_schema.NXDL_Summary))
        self.assertNotEqual(summary, s2, 'no longer using singleton')
        # TODO: could do more extensive testing here


def suite(*args, **kw):
    test_suite = unittest.TestSuite()
    test_list = [
        Test_Functions,
        Test_Catalog,
        ]
    for test_case in test_list:
        test_suite.addTest(unittest.makeSuite(test_case))
    return test_suite


if __name__ == '__main__':
    runner=unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
