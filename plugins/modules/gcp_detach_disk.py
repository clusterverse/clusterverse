# -*- coding: utf-8 -*-

# Copyright 2024 Dougal Seeley <git@dougalseeley.com>
# BSD 3-Clause License

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

DOCUMENTATION = '''
---
module: gcp_detach_disk
version_added: 1.0.0
description:
  - Detaches a disk from an instance.  Functionality is missing from google.cloud collection
authors:
  - Dougal Seeley <github@dougalseeley.com>
options:
  zone:
    description:
    - A reference to the zone where the disk resides.
    required: true
    type: str
  name:
    description:
    - Name of the disk.
    required: true
    type: str
  instance_name:
    description:
    - Name of the instance from which to detach the <name> disk.
    required: true
    type: str
'''

EXAMPLES = '''
- clusterverse.clusterverse.gcp_detach_disk:
    auth_kind: "serviceaccount"
    service_account_file: "{{gcp_credentials_file}}"
    project: "dev01-123456"
    zone: "europe-west4-a"
    name: "dougal-test-dev-sysdisks2-a0-1716614556--mysvc2"
    instance_name: "dougal-test-dev-sysdisks2-a0-1716614556"
'''

from ansible_collections.google.cloud.plugins.module_utils.gcp_utils import (
    GcpSession,
    GcpModule,
)
import time


def check_disk_exists(module):
    session = GcpSession(module, 'compute')
    try:
        url = "https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/disks/{name}".format(**module.params)
        response = session.get(url)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            module.fail_json(msg=f"Unexpected response status code: {response.status_code}")
    except Exception as e:
        module.fail_json(msg=f"Failed to check disk existence: {str(e)}")


def get_instance_disks(module):
    session = GcpSession(module, 'compute')
    try:
        url = "https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instances/{instance_name}".format(**module.params)
        response = session.get(url)
        instance_info = response.json()
        return instance_info.get('disks', [])
    except Exception as e:
        module.fail_json(msg=f"Failed to get instance disks: {str(e)}")


def detach_disk(module):
    session = GcpSession(module, 'compute')
    try:
        url = "https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instances/{instance_name}/detachDisk".format(**module.params)
        params = {'deviceName': module.params['name']}
        result = session.post(url, params=params)
        return result.json()
    except Exception as e:
        module.fail_json(msg=str(e))


def wait_for_operation(module, operation):
    session = GcpSession(module, 'compute')
    url = f"https://www.googleapis.com/compute/v1/projects/{module.params['project']}/zones/{module.params['zone']}/operations/{operation}"
    while True:
        try:
            result = session.get(url).json()
            if 'error' in result:
                module.fail_json(msg=f"Operation failed: {result['error']}")
            if result['status'] == 'DONE':
                return result
            time.sleep(2)
        except Exception as e:
            module.fail_json(msg=f"Error waiting for operation: {str(e)}")


def main():
    module = GcpModule(argument_spec=dict(
        project=dict(type='str', required=True),
        zone=dict(type='str', required=True),
        instance_name=dict(type='str', required=True),
        name=dict(type='str', required=True)
    ))

    if not module.params['scopes']:
        module.params['scopes'] = ['https://www.googleapis.com/auth/compute']

    # Check if the disk exists
    if not check_disk_exists(module):
        module.warn("The disk '{name}' does not exist in zone '{zone}' of project '{project}'.".format(**module.params))
        module.exit_json(changed=False, msg="The disk '{name}' does not exist in zone '{zone}' of project '{project}'.".format(**module.params))

    # Get the current state of instance disks
    instance_disks = get_instance_disks(module)
    current_disks = [d['deviceName'] for d in instance_disks]

    # Check if the disk is attached
    disk_attached = module.params['name'] in current_disks
    if disk_attached:
        detach_result = detach_disk(module)
        operation = detach_result['name']
        wait_result = wait_for_operation(module, operation)
        module.exit_json(changed=True, result=wait_result)
    else:
        module.exit_json(changed=False, msg="Disk is already detached.")


if __name__ == '__main__':
    main()
