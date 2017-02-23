"""
Interface to the config_metabuild.xml file.  This class inherits from GenericXML.py
"""

from CIME.XML.standard_module_setup import *
from CIME.XML.generic_xml import GenericXML
from CIME.XML.files import Files
from CIME.XML.compilers import Compilers
from CIME.XML.machines import Machines

logger = logging.getLogger(__name__)

class MetaBuild(GenericXML):

    def __init__(self, infile=None, files=None, machine=None):
        """
        initialize an object
        if a filename is provided it will be used,
        otherwise if a files object is provided it will be used
        otherwise create a files object from default values
        """
        if infile is None:
            if files is None:
                files = Files()
            infile = files.get_value('METABUILD_SPEC_FILE')
        GenericXML.__init__(self, infile)

    def write_configure_file(self, component):
        """
        Writes a configuration file for the requested component
        Returns the path to the configuration file
        """
        buildtool, configs = self._get_component_configs(component)
        buildmap = {'CMake': self._write_cmake_configure_file}
        def_map = self._aggregate_vars()
        return buildmap[buildtool](component, configs, def_map)

    def _write_cmake_configure_file(self, component, configs, def_map):
        fname = component + '_config.cmake'
        for elem in configs:
            for opt in elem:
                # TODO: Implement substitution
                print(opt.tag, opt.text, self.get_resolved_value(opt.text))

    def _aggregate_vars(self):
        # Determines what configuration values are associated with the
        # current machine/os/compiler settings, returning a map of them
        # Note that this assumes the machine being run on is the target
        # This is a bad assumption
        mach = Machines()
        compiler_nodes = [node for node in Compilers(mach).get_nodes('compiler')
                          if (('MACH' not in node.attrib
                               or node.attrib['MACH'] == mach.get_machine_name())
                              and
                              ('OS' not in node.attrib
                               or node.attrib['OS'] == mach.get_value('OS'))
                              and
                              ('COMPILER' not in node.attrib
                               or node.attrib['COMPILER'] == mach.get_value('COMPILER'))
                              )]
        def_map = {}
        for compiler in compiler_nodes:
            print(compiler.attrib)
            for option in compiler:
                varname = option.tag
                if varname[:4] == 'ADD_':
                    varname = varname[4:]
                if varname not in def_map:
                    def_map[varname] = option.text
                else:
                    def_map[varname] += option.text
                print('  ' + str((option, option.text)))
        print(def_map)
        return def_map

    def _get_component_configs(self, component):
        # Gets the configuration options for the component
        comp_tag = 'component'
        comp_attrib = 'COMP'
        component = self.get_node(comp_tag, attributes={comp_attrib: component})
        config_tag = 'configuration'
        configurations = [component.find(config_tag)]
        bt_attrib = 'buildtool'
        buildtool = component.find(bt_attrib).text
        additional = [n for n in self.get_nodes(comp_tag)
                      if 'COMP' not in n.attrib]
        expect(len(additional) <= 1, 'Incorrect number of subtrees to add')
        if len(additional) == 1:
            added_configs = [c for c in additional[0].findall(config_tag)
                             if bt_attrib in c.attrib and c.attrib[bt_attrib] == buildtool]
            expect(len(added_configs) <= 1, 'Incorrect number of configurations to add')
            if len(added_configs) == 1:
                configurations += added_configs
        return buildtool, configurations
