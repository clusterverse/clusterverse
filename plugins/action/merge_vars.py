# Copyright (c) 2020, Sky UK Ltd
# BSD 3-Clause License
#
# This plugin is similar to include_vars, but it is able to merge across multiple files and directories, and when it finds variables that have already been
# defined, it recursively merges them (in the order defined).
#
# It is also able to merge variables defined literally (using the same syntax as the update_fact plugin).  It is useful to do this here, rather than using
# set_fact, because set_fact causes the source of the variable to change to a higher precedence (facts are higher than include_vars), and if you set_fact,
# then merge_vars will not be able to override the values later.
#
#
# By splitting different cluster configurations across tiered files, applications can adhere to the "Don't Repeat Yourself" principle.
#
#       cluster_defs/
#       |-- app_vars.yml
#       |-- cluster_vars.yml
#       |-- aws
#       |   |-- cluster_vars__cloud.yml
#       |   `-- eu-west-1
#       |       |-- cluster_vars__region.yml
#       |       `-- sandbox
#       |           `-- cluster_vars__buildenv.yml
#       `-- gcp
#           |-- cluster_vars__cloud.yml
#           `-- europe-west1
#               `-- sandbox
#                   `-- cluster_vars__buildenv.yml
#
# These files can be combined (in the order defined) in the application code, using variables to differentiate between cloud (aws or gcp), region and build env.
# A variable 'ignore_missing_files' can be set such that any files or directories that are not found in the defined 'files' list will not raise an error.
#    - merge_vars:
#        ignore_missing_files: true
#        files:
#         - "./cluster_defs/all.yml"
#         - "./cluster_defs/{{ cloud_type }}/all.yml"
#         - "./cluster_defs/{{ cloud_type }}/{{ region }}/all.yml"
#         - "./cluster_defs/{{ cloud_type }}/{{ region }}/{{ buildenv }}/all.yml"
#         - "./cluster_defs/{{ cloud_type }}/{{ region }}/{{ buildenv }}/{{ clusterid }}.yml"
#
# It can optionally include only files with certain extensions:
#  - merge_vars:
#      extensions: ['yml', 'yaml']
#      files:
#         - "./cluster_defs/{{ cloud_type }}"
#
# It can merge in variables literally:
#   - merge_vars:
#       literals:
#         - path: "cluster_vars.innov.aws_access_key"
#           value: "{{get_url_registered_value}}"

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase
from ansible.utils.vars import merge_hash
from os import path, listdir
from copy import deepcopy
from datetime import datetime


# A simple deep diff function to find differences between two nested dictionaries
def deep_diff(d1, d2, path=""):
    diffs = []

    for key in d1.keys() | d2.keys():
        new_path = f"{path}.{key}" if path else str(key)

        if key not in d1:
            diffs.append((new_path, None, d2[key]))
        elif key not in d2:
            diffs.append((new_path, d1[key], None))
        else:
            v1, v2 = d1[key], d2[key]
            if isinstance(v1, dict) and isinstance(v2, dict):
                diffs.extend(deep_diff(v1, v2, new_path))
            elif v1 != v2:
                diffs.append((new_path, v1, v2))

    return diffs


class ActionModule(ActionBase):
    VALID_ARGUMENTS = ['files', 'literals', 'ignore_missing_files', 'extensions']

    def __init__(self, *args, **kwargs):
        super(ActionModule, self).__init__(*args, **kwargs)
        self._result = None
        self._display.columns = 50000  # Set the columns for display.warning to a very large number (so it wraps by console, not by Ansible)

    def run(self, tmp=None, task_vars=None):
        self._result = super(ActionModule, self).run(tmp, task_vars)
        self._result["changed"] = False

        self.ignore_missing_files = self._task.args.get('ignore_missing_files', False)
        self.valid_extensions = self._task.args.get('extensions')

        self._display.vvvvv("*** self._task.args %s " % self._task.args)
        self._display.vvvvv("*** task_vars %s " % task_vars)

        # NOTE: We spoof the plugin action to have an action of 'include_vars', so that the loaded vars
        # are treated as host variables (and not facts), and merged with host variables when returning 'ansible_facts'.
        # They are also otherwise they are not templated.  We could try to template them (e.g. self._template.template()),
        # but because we're actually templating a yaml *file*, (not individual variables), things like yaml aliases do not resolve.
        # https://github.com/ansible/ansible/blob/v2.15.4/lib/ansible/plugins/strategy/__init__.py#L729-L734
        self._task.action = 'include_vars'

        # Check for arguments that are not supported
        invalid_args = [arg for arg in self._task.args if arg not in self.VALID_ARGUMENTS]
        if invalid_args:
            raise AnsibleActionFail(message="The following are not valid options in merge_vars '%s'" % ", ".join(invalid_args))

        # Check that minimum arguments are present
        if not any(item in self._task.args for item in ['files', 'literals']):
            raise AnsibleActionFail(message="At least one of 'files' or 'literals' should be present.")

        # Get the extra-vars dict - these are the highest precedence and cannot be merged into the host variables
        extra_vars = self._task.get_variable_manager().extra_vars  # dict of only the --extra-vars
        self._display.vvv("***extra_vars: %s" % (extra_vars))

        # Dictionary to hold all the variables to be merged into host variables.
        hostvars_to_update = {}
        if 'files' in self._task.args:
            self._result['ansible_included_var_files'] = files = []
            for source in self._task.args['files']:
                if path.isfile(source):
                    files.append(source)
                elif path.isdir(source):
                    dirfiles = [path.join(source, filename) for filename in listdir(source) if path.isfile(path.join(source, filename))]
                    dirfiles.sort()
                    files = files + dirfiles
                elif not (path.isfile(source) or path.isdir(source)) and self.ignore_missing_files:
                    self._display.v("Missing source file/dir (%s) ignored due to 'ignore_missing_files: True'" % (source))
                else:
                    raise AnsibleActionFail("Source file/dir '%s' does not exist" % source)

            # A copy of the original hostvars_to_update before loading files, for diffing later
            hostvars_to_update_files_orig = {}
            for filename in files:
                if (not self.valid_extensions) or path.splitext(filename)[-1][1:] in self.valid_extensions:
                    ansible_version_tuple = (task_vars['ansible_version']['major'], task_vars['ansible_version']['minor'])
                    load_kwargs = {'cache': None}
                    if ansible_version_tuple >= (2, 19):
                        load_kwargs['trusted_as_template'] = True

                    cur_file_vars = self._loader.load_from_file(filename, **load_kwargs)
                    self._display.vvv("***cur_file_vars: %s" % cur_file_vars)

                    # Here we pre-seed top-level keys from task_vars into hostvars_to_update. This allows us to merge new sub-keys from cur_file_vars into
                    # existing structures in task_vars, perhaps defined in previous runs of merge_vars (or include_vars).
                    for (k, v) in cur_file_vars.items():
                        # If the top-level key is not already in hostvars_to_update, copy it from task_vars
                        if k not in hostvars_to_update and k in task_vars:
                            hostvars_to_update_files_orig[k] = task_vars[k]
                            hostvars_to_update[k] = deepcopy(task_vars[k])

                    self._display.vvv("***files_preload/hostvars_to_update: %s " % hostvars_to_update)
                    hostvars_to_update = merge_hash(hostvars_to_update, cur_file_vars)

                    self._result['ansible_included_var_files'].append(filename)
                else:
                    self._display.warning(datetime.now().strftime("%H:%M:%S:%f") + ": File extension is not in the allowed list: %s " % filename)

            for unmergable in [k for k in hostvars_to_update if k in extra_vars.keys()]:
                self._display.warning(datetime.now().strftime("%H:%M:%S:%f") + ": Key '%s' is also in extra_vars; cannot merge" % unmergable)
                hostvars_to_update[unmergable] = extra_vars[unmergable]

            self._display.vvv("***files_postload/hostvars_to_update: %s " % hostvars_to_update)

            hostvars_files_diff = deep_diff(hostvars_to_update_files_orig, hostvars_to_update)
            self._display.vvv("*deepdiff: %s, len(%s):" % (str(hostvars_files_diff), len(hostvars_files_diff)))
            if len(hostvars_files_diff) > 0:
                self._result["changed"] = True

        if 'literals' in self._task.args:
            if not isinstance(self._task.args['literals'], list):
                raise AnsibleActionFail("The 'literals' argument in merge_vars must be a list of dictionaries, each with 'path' and 'value'")

            for item in self._task.args['literals']:
                if not isinstance(item, dict) or 'path' not in item or 'value' not in item:
                    raise AnsibleActionFail("Each item in 'literals' must be a dict with 'path' and 'value' keys")

                path_str = self._templar.template(item['path'])  # Allow templating in path if needed (rare)
                new_value = self._templar.template(item['value'])

                keys = path_str.split('.')
                if not keys:
                    raise AnsibleActionFail("Path cannot be empty in vars update")

                if keys[0] in extra_vars:
                    self._display.warning(datetime.now().strftime("%H:%M:%S:%f") + ": Key '%s' is also in extra_vars; cannot merge" % keys[0])
                else:
                    # If the top-level key is not already in hostvars_to_update, copy it from task_vars
                    if keys[0] not in hostvars_to_update and keys[0] in task_vars:
                        hostvars_to_update[keys[0]] = deepcopy(task_vars[keys[0]])

                    # Start from task_vars and walk/create the path
                    current = hostvars_to_update

                    # Traverse all but the last key, creating dicts if needed
                    for key in keys[:-1]:
                        if key not in current or not isinstance(current[key], dict):
                            current[key] = {}  # Create intermediate dict
                        current = current[key]

                    # Replace the final value
                    if current.get(keys[-1]) != new_value:
                        self._result["changed"] = True
                    current[keys[-1]] = new_value

        self._result['ansible_facts'] = hostvars_to_update  # Because we spoofed self._task.action = 'include_vars', the vars in 'ansible_facts' are not actuall added to 'ansible_facts', but instead to host variables.
        return self._result
