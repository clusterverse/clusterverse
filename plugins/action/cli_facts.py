from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.2',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: cli_facts
short_description: Gather system ARGV and CLI arguments as facts
version_added: "2.8"
author: "Dougal Seeley"
description:
    - Gathers system ARGV and CLI arguments and sets them as facts in plays.
    - Adds two facts: argv (system arguments) and cliargs (Ansible CLI arguments).
    - This is an action plugin instead of vars plugin so that we don't need to set vars_plugins_enabled in all projects that consume clusterverse 
options: {}
requirements: []
'''

from ansible.plugins.action import ActionBase
from ansible.context import CLIARGS
import sys


class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)
        
        # Gather the facts
        result = {
            'ansible_facts': {
                'cliargs': dict(CLIARGS),
                'argv': sys.argv
            },
            'changed': False
        }
        
        return result