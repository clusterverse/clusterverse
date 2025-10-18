#!/usr/bin/python
# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = '''
---
module: ec2_instance_type_info
version_added: 1.0.0
short_description: EC2 instance type info
description:
  - List details of EC2 instance types.
  - Uses the boto describe_instance_types API
author: "Dougal Seeley (@dseeley)"
options:
  instance_types:
    description: One or more instance types.
    type: list
    elements: str
  filters:
    description:
      - A dict of filters to apply. Each dict item consists of a filter key and filter value.
        See U(https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-instance-types.html#options)
        for possible filters. Filter names and values are case sensitive.
    required: false
    default: {}
    type: dict
'''

EXAMPLES = r'''
- name: List all instance_type in the current region.
  clusterverse.clusterverse.ec2_instance_type_info:
  register: regional_eip_addresses

- name: List all instance_type for a VM.
  clusterverse.clusterverse.ec2_instance_type_info:
    instance_types: ["t3a.nano", "t4g.nano"]
    filters:
      hypervisor: "nitro"
  register: r__ec2_instance_type_info

- ansible.builtin.debug:
    msg: "{{ r__ec2_instance_type_info }}"
'''


from ansible_collections.amazon.aws.plugins.module_utils.core import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.ec2 import (ansible_dict_to_boto3_filter_list,
                                                                     boto3_tag_list_to_ansible_dict,
                                                                     camel_dict_to_snake_dict
                                                                     )

try:
    from botocore.exceptions import (BotoCoreError, ClientError)
except ImportError:
    pass  # caught by imported AnsibleAWSModule


def get_describe_instance_types(module):
    connection = module.client('ec2')
    try:
        response = connection.describe_instance_types(InstanceTypes=module.params.get("instance_types"), Filters=ansible_dict_to_boto3_filter_list(module.params.get("filters")))
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg="Error retrieving InstanceTypes")

    instance_types = camel_dict_to_snake_dict(response)['instance_types']
    return instance_types


def main():
    module = AnsibleAWSModule(
        argument_spec=dict(
            instance_types=dict(default=[], type='list', elements='str', aliases=['instance_type']),
            filters=dict(type='dict', default={})
        ),
        supports_check_mode=True
    )

    module.exit_json(changed=False, instance_types=get_describe_instance_types(module))


if __name__ == '__main__':
    main()
