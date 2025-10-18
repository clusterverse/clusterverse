# Copyright (c) 2020, Sky UK Ltd
# BSD 3-Clause License
#
# This plugin is similar to include_vars, but it is able to recurse multiple files and directories, and when it finds variables that have already been
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
# A variable 'ignore_missing_files' can be set such that any files or directories that are not found in the defined 'from' list will not raise an error.
#    - merge_vars:
#        ignore_missing_files: true
#        from:
#         - "./cluster_defs/all.yml"
#         - "./cluster_defs/{{ cloud_type }}/all.yml"
#         - "./cluster_defs/{{ cloud_type }}/{{ region }}/all.yml"
#         - "./cluster_defs/{{ cloud_type }}/{{ region }}/{{ buildenv }}/all.yml"
#         - "./cluster_defs/{{ cloud_type }}/{{ region }}/{{ buildenv }}/{{ clusterid }}.yml"
#
# It can optionally include only files with certain extensions:
#  - merge_vars:
#      extensions: ['yml', 'yaml']
#      from:
#         - "./cluster_defs/{{ cloud_type }}"
#
# By default, it will recursively merge the found variables with existing variables.  Optionally it can replace the variables completely.
#    - merge_vars:
#        from:
#           - "./cluster_defs/{{ cloud_type }}"
#        replace: True

# It can merge in variables literally:
#   - merge_vars:
#       facts:
#         - path: "cluster_vars.innov.aws_access_key"
#           value: "{{get_url_registered_value}}"

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase
from ansible.utils.vars import merge_hash
from ansible.module_utils._text import to_native, to_text
from os import path, listdir
from copy import deepcopy


class ActionModule(ActionBase):
    VALID_ARGUMENTS = ['from', 'facts', 'ignore_missing_files', 'extensions', 'replace']

    def __init__(self, *args, **kwargs):
        super(ActionModule, self).__init__(*args, **kwargs)
        self._result = None
        self._display.columns = 50000       # Set the columns for display.warning to a very large number (so it wraps by console, not by Ansible)

    def run(self, tmp=None, task_vars=None):
        self._result = super(ActionModule, self).run(tmp, task_vars)
        self._result["changed"] = False

        self.ignore_missing_files = self._task.args.get('ignore_missing_files', False)
        self.valid_extensions = self._task.args.get('extensions')

        self._display.vvvvv("*** self._task.args %s " % self._task.args)
        self._display.vvvvv("*** task_vars %s " % task_vars)

        # NOTE: We have to pretend that this plugin action is actually the 'include_vars' plugin, so that the loaded vars
        # are treated as host variables, (and not just facts), otherwise they are not templated.  We could try to
        # template them (e.g. self._template.template()), but because we're actually templating a yaml *file*,
        # (not individual variables), things like yaml aliases do not resolve.
        # https://github.com/ansible/ansible/blob/v2.15.4/lib/ansible/plugins/strategy/__init__.py#L729-L734
        self._task.action = 'include_vars'

        # Check for arguments that are not supported
        invalid_args = [arg for arg in self._task.args if arg not in self.VALID_ARGUMENTS]
        if invalid_args:
            raise AnsibleActionFail(message="The following are not valid options in merge_vars '%s'" % ", ".join(invalid_args))

        # Check that minimum arguments are present
        if not any(item in self._task.args for item in ['from', 'facts']):
            raise AnsibleActionFail(message="At least one of 'from' or 'facts' should be present.")

        new_facts = {}
        if 'from' in self._task.args:
            self._result['ansible_included_var_files'] = files = []
            for source in self._task.args['from']:
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

            for filename in files:
                if (not self.valid_extensions) or path.splitext(filename)[-1][1:] in self.valid_extensions:
                    _new_facts_cmp = deepcopy(new_facts)
                    self._display.vvvvv("*** _new_facts_cmp: %s " % _new_facts_cmp)

                    ansible_version_tuple = (task_vars['ansible_version']['major'], task_vars['ansible_version']['minor'])
                    if ansible_version_tuple < (2, 19):
                        self._display.v("*** using load_from_file for v<2.19")
                        new_facts = merge_hash(new_facts, self._loader.load_from_file(filename, cache=None))
                    else:
                        self._display.v("*** using load_from_file for v>=2.19")
                        new_facts = merge_hash(new_facts, self._loader.load_from_file(filename, cache=None, trusted_as_template=True))
                    self._display.vvvvv("*** new_facts: %s " % new_facts)
                    if new_facts != _new_facts_cmp:
                        self._result["changed"] = True
                    self._result['ansible_included_var_files'].append(filename)
                else:
                    self._display.warning("File extension is not in the allowed list: %s " % filename)

        if 'facts' in self._task.args:
            new_task = self._task.copy()
            new_task.action = 'ansible.utils.update_fact'
            new_task.args = {'updates': self._task.args['facts']}

            # Get the action_loader for ansible.utils.update_fact
            update_fact_actionloader = self._shared_loader_obj.action_loader.get(new_task.action, task=new_task, connection=self._connection, play_context=self._play_context, loader=self._loader, templar=self._templar, shared_loader_obj=self._shared_loader_obj)

            # Run ansible.utils.update_fact
            task_result = update_fact_actionloader.run(task_vars=task_vars)
            self._display.vvvvv("*** task_result: %s " % task_result)

            # Set changed if changed
            self._result["changed"] = self._result["changed"] or task_result['changed']

            # Remove 'changed', 'skipped', 'failed' from the results from ansible.utils.update_fact
            [task_result.pop(key, None) for key in ['changed', 'skipped', 'failed']]

            # Recursively merge any variables loaded by the 'files' with these
            new_facts = merge_hash(new_facts, task_result)

        # Merge these new variables with previously-defined variables if 'replace' is not set
        new_facts = merge_hash(task_vars.get('ansible_facts', {}), new_facts, recursive=(not self._task.args.get('replace')))

        self._display.vvvvv("*** new_facts: %s " % new_facts)
        self._result['ansible_facts'] = new_facts
        return self._result
