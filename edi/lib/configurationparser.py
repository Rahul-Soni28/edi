# -*- coding: utf-8 -*-
# Copyright (C) 2016 Matthias Luescher
#
# Authors:
#  Matthias Luescher
#
# This file is part of edi.
#
# edi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# edi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with edi.  If not, see <http://www.gnu.org/licenses/>.

import yaml
from edi.lib.helpers import get_user, get_hostname, print_error_and_exit
import os
from os.path import basename, splitext
import logging
from aptsources.sourceslist import SourceEntry


class ConfigurationParser():

    # shared data for all configuration parsers
    _configurations = {}

    def dump(self):
        return yaml.dump(self._get_config(), default_flow_style=False)

    def get_project_name(self):
        return self.config_id

    def get_workdir(self):
        # we might want to overwrite it by a config setting
        return os.getcwd()

    def get_distribution(self):
        repository = self._get_bootstrap_item("repository", "")
        return SourceEntry(repository).dist

    def get_architecture(self):
        return self._get_bootstrap_item("architecture", None)

    def get_bootstrap_tool(self):
        return self._get_bootstrap_item("tool", "debootstrap")

    def get_bootstrap_uri(self):
        repository = self._get_bootstrap_item("repository", "")
        return SourceEntry(repository).uri

    def get_bootstrap_repository_key(self):
        return self._get_bootstrap_item("repository_key", None)

    def get_bootstrap_components(self):
        repository = self._get_bootstrap_item("repository", "")
        return SourceEntry(repository).comps

    def get_use_case(self):
        return self._get_global_configuration_item("use_case", "edi_run")

    def get_compression(self):
        return self._get_global_configuration_item("compression", "xz")

    def __init__(self, base_config_file):
        self.config_id = splitext(basename(base_config_file.name))[0]
        if not ConfigurationParser._configurations.get(self.config_id):
            logging.info(("Using base configuration file '{0}'"
                          ).format(base_config_file.name))
            base_config = yaml.load(base_config_file.read())
            all_config = self._get_overlay_config(base_config_file, "all")
            host_config = self._get_overlay_config(base_config_file,
                                                   get_hostname())
            user_config = self._get_overlay_config(base_config_file,
                                                   get_user())

            merge_1 = self._merge_configurations(base_config, all_config)
            merge_2 = self._merge_configurations(merge_1, host_config)
            merged_config = self._merge_configurations(merge_2, user_config)

            ConfigurationParser._configurations[self.config_id] = merged_config
            logging.info("Merged configuration:\n{0}".format(self.dump()))

    def _get_config(self):
        return ConfigurationParser._configurations.get(self.config_id, {})

    def _get_overlay_config(self, base_config_file, overlay_name):
        filename, file_extension = os.path.splitext(base_config_file.name)
        fn = "{0}.{1}{2}".format(filename, overlay_name, file_extension)
        if os.path.isfile(fn) and os.access(fn, os.R_OK):
            with open(fn, encoding="UTF-8", mode="r") as config_file:
                logging.info(("Using overlay configuration file '{0}'"
                              ).format(config_file.name))
                return yaml.load(config_file.read())
        else:
            return {}

    def _merge_configurations(self, base, overlay):
        merged_config = {}

        elements = ["global_configuration", "bootstrap"]
        for element in elements:
            merged_config[element
                          ] = self._merge_key_value_node(base, overlay,
                                                         element)

        playbook_element = "playbooks"
        merged_config[playbook_element
                      ] = self._merge_ansible_playbooks(base, overlay,
                                                        playbook_element)
        return merged_config

    def _merge_key_value_node(self, base, overlay, node_name):
        base_node = base.get(node_name, {})
        overlay_node = overlay.get(node_name, {})
        if base_node is None and overlay_node is None:
            return {}
        if base_node is None:
            return overlay_node
        if overlay_node is None:
            return base_node
        return dict(base_node, **overlay_node)

    def _get_identifier(self, element):
        identifier = element.get("identifier", None)
        if identifier is None:
            print_error_and_exit(("Missing identifier for "
                                  "element:\n'{}'"
                                  ).format(element))
        return identifier

    def _merge_ansible_playbooks(self, base, overlay, playbook_node):
        merged_playbooks = self._merge_key_value_node(base, overlay,
                                                      playbook_node)

        for key, _ in merged_playbooks.items():
            playbook_base = base.get(playbook_node, {})
            playbook_overlay = overlay.get(playbook_node, {})
            merged_playbooks[key
                             ] = self._merge_key_value_node(playbook_base,
                                                            playbook_overlay,
                                                            key)

            element = "parameters"
            base_params = playbook_base.get(key, {})
            overlay_params = playbook_overlay.get(key, {})
            merged_params = self._merge_key_value_node(base_params,
                                                       overlay_params,
                                                       element)
            if merged_params:
                merged_playbooks[key][element] = merged_params

        return merged_playbooks

    def _get_bootstrap_item(self, item, default):
        return self._get_config().get("bootstrap", {}
                                      ).get(item, default)

    def _get_global_configuration_item(self, item, default):
        return self._get_config().get("global_configuration", {}
                                      ).get(item, default)
