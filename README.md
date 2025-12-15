# clusterverse  &nbsp; [![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause) ![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)
A full-lifecycle, immutable cloud infrastructure cluster management **collection**, using Ansible.
+ **Multi-cloud:** clusterverse can manage cluster lifecycle in AWS, GCP, Azure, libvirt (Qemu) and ESXi (standalone host only, not vCentre).
+ **DNS:**  clusterverse can create DNS entries for your nodes, and remove them when the nodes are deleted.
+ **_Deploy_:**  You define your infrastructure as code and clusterverse will deploy it.
  + **Scale-up:**  If you update the cluster definitions with additional nodes and rerun the deploy, new nodes will be added.
  + **Repair:**  If a node fails, clusterverse can repair it (replacing the node with a new one).
+ **_Redeploy_ (e.g. replace OS, or increment cluster version):** Akin to an cloud-managed service - if you need to up-version, or replace the underlying OS, (i.e. to achieve fully immutable infrastructure), the `redeploy.yml` playbook will replace each node in the cluster (via pluggable redeploy schemes)
  + **zero-downtime:**  Redeploys can be done with zero-downtime, (assuming the cluster topology supports it).
  + **canary redeploy:**  Redeploys can be done in a canary fashion, to ensure that the new nodes are working before the old nodes are removed.
  + **rollback:**  If a deploy or redeploy fails, clusterverse can rollback to the previous state (depending on the scheme used).

**clusterverse** is designed to manage base-vm infrastructure that underpins cluster-based infrastructure, for example, Couchbase, Kafka, Elasticsearch, or Cassandra.

## Contributing
Contributions are welcome and encouraged.  Please see [CONTRIBUTING.md](https://github.com/clusterverse/clusterverse/blob/master/CONTRIBUTING.md) for details.

## Requirements
+ ansible-core >= 2.17.4 (pypi >= 10.4.0)
+ Python >= 3.8

### AWS
+ AWS account with rights to create EC2 VMs and security groups in the chosen VPCs/subnets.  Several mechanisms exist: Either:
  + Place IAM key/secret credentials in [Cluster Definition Variables](#cluster_definition_variables):
    + `cluster_vars[buildenv].aws_access_key:`
    + `cluster_vars[buildenv].aws_secret_key:`
  + Switch to a role that has rights to create VMs, either by being:
    + ... on an EC2 machine with an Instance Type that can switch to the role, or
    + ... logged in with a user that has rights to switch to the role
      + `cluster_vars[buildenv].aws_sts_assume_role_arn:`
  + Use environment variables:
    + `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables
      Or
    + `AWS_PROFILE` environment variable, which points to a profile in `~/.aws/[credentials|config]`
+ Preexisting VPCs:
  + `cluster_vars[buildenv].vpc_name: my-vpc-{{buildenv}}`
+ Preexisting subnets. This is a prefix - the cloud availability zone will be appended to the end (e.g. `a`, `b`, `c`).
  + `cluster_vars[buildenv].vpc_subnet_name_prefix: my-subnet-{{region}}`
+ Preexisting keys (in AWS IAM):
  + `cluster_vars[buildenv].key_name: my_key__id_rsa`

### GCP
+ Create a gcloud account.
+ Create a service account in `IAM & Admin` / `Service Accounts`.  Download the json file locally.
+ Store the contents within the `cluster_vars[buildenv].gcp_service_account_contents` variable.
  + During execution, the json file will be copied locally because the Ansible GCP modules often require the file as input.
+ Google Cloud SDK needs to be installed to run gcloud command-line (e.g. to disable delete protection) - this is handled by `pipenv install`

### libvirt (Qemu)
+ It is non-trivial to set up username/password access to a remote libvirt host, so we use an ssh key instead .
+ Your ssh user should be a member of the `libvirt` and `kvm` groups.
+ Store the config in `cluster_vars.libvirt`

### ESXi (free)
+ Username & password for a privileged user on an ESXi host
+ SSH must be enabled on the host
+ Set the `Config.HostAgent.vmacore.soap.maxSessionCount` variable to 0 to allow many concurrent tests to run.
+ Set the `Security.SshSessionLimit` variable to max (100) to allow as many ssh sessions as possible.
+ Store the config in `cluster_vars.esxi`

### Azure
+ Create an Azure account.
+ Create a Tenant and a Subscription
+ Create a Resource group and networks/subnetworks within that.
+ Create a service principal - add the credentials to:
  + `cluster_vars[buildenv].azure_subscription_id`
  + `cluster_vars[buildenv].azure_client_id`
  + `cluster_vars[buildenv].azure_secret`
  + `cluster_vars[buildenv].azure_tenant`


### DNS
DNS is optional.  If unset, no DNS names will be created.  If DNS is required, you will need a DNS zone delegated to one of the following:
+ nsupdate (e.g. bind9)
+ AWS Route53
+ Google Cloud DNS

Credentials to the DNS server will also be required. These are specified in the `cluster_vars` variable described below.


## Cluster Definition Variables
Clusters are defined as code within Ansible yaml files that are imported at runtime.  Because clusters are built from scratch on the localhost, the automatic Ansible `group_vars` inclusion cannot work with anything except the special `all.yml` group (ansible _groups_ must be in the _inventory_, which, in clusterverse, is dynamic and thus does exist until the cluster is built).  The `group_vars/all.yml` file is instead used to bootstrap _merge_vars_.

### merge_vars
Clusterverse is designed to be used to deploy the same clusters in multiple clouds and multiple environments, potentially using similar configurations.  In order to avoid duplicating configuration, a new [action plugin](https://docs.ansible.com/ansible/latest/dev_guide/developing_plugins.html#action-plugins) has been developed (called `merge_vars`) to use in place of the standard `include_vars`, which allows users to define the variables hierarchically, and include (and potentially override) those defined before them.  This plugin is similar to `include_vars`, but when it finds dictionaries that have already been defined, it _combines_ them instead of replacing them.

```yaml
- merge_vars:
    ignore_missing_files: True
    from: "{{ merge_dict_vars_list }}"     # 'merge_dict_vars_list' is defined in `group_vars/all.yml`
```
+ The variable _ignore_missing_files_ can be set such that any files or directories that are not found in the defined 'from' list will not raise an error.

<br/>

##### merge_dict_vars_list - hierarchical:
In the case of a fully hierarchical set of cluster definitions where each directory is a variable, (e.g. _cloud_ (aws or gcp), _region_ (eu-west-1) and _cluster_id_ (test)), the folders may look like:

```text
|-- aws
|   |-- eu-west-1
|   |   |-- dev
|   |   |   |-- test
|   |   |   |   `-- cluster_vars.yml
|   |   |   `-- cluster_vars.yml
|   |   `-- cluster_vars.yml
|   `-- cluster_vars.yml
|-- gcp
|   |-- europe-west4
|   |   `-- dev
|   |       |-- test
|   |       |   `-- cluster_vars.yml
|   |       `-- cluster_vars.yml
|   `-- cluster_vars.yml
|-- app_vars.yml
`-- cluster_vars.yml
```

`group_vars/all.yml` would contain `merge_dict_vars_list` with the files and directories, listed from top to bottom in the order in which they should override their predecessor:
```yaml
merge_dict_vars_list:
  - "./cluster_defs/cluster_vars.yml"
  - "./cluster_defs/app_vars.yml"
  - "./cluster_defs/{{ cloud_type }}/"
  - "./cluster_defs/{{ cloud_type }}/{{ region }}/"
  - "./cluster_defs/{{ cloud_type }}/{{ region }}/{{ buildenv }}/"
  - "./cluster_defs/{{ cloud_type }}/{{ region }}/{{ buildenv }}/{{ clusterid }}/"
```

<br/>

##### merge_dict_vars_list - flat:

It is also valid to define all the variables in a single sub-directory:
```text
cluster_defs/
|-- test_aws_euw1
|   |-- app_vars.yml
|   +-- cluster_vars.yml
+-- test_gcp_euw1
    |-- app_vars.yml
    +-- cluster_vars.yml
```
In this case, `merge_dict_vars_list` would be only the top-level directory (using `cluster_id` as a variable).  `merge_vars` does not recurse through directories.
```yaml
merge_dict_vars_list:
  - "./cluster_defs/{{ clusterid }}"
```

<br/>


## Cloud Credential Management
Credentials can be encrypted inline in the playbooks using [ansible-vault](https://docs.ansible.com/ansible/latest/vault_guide/index.html).
+ Because multiple environments are supported, it is recommended to use [vault-ids](https://docs.ansible.com/ansible/latest/vault_guide/vault_using_encrypted_content.html#passing-vault-ids), and have credentials per environment (e.g. to help avoid accidentally running a deploy on prod).
+ There is a small script (`.vaultpass-client.py`) that returns a password stored in an environment variable (`VAULT_PASSWORD_BUILDENV`) to ansible.
  + `export VAULT_PASSWORD_BUILDENV=<'dev/stage/prod' password>`
+ To encrypt sensitive information, you must ensure that your current working dir can see the script `.vaultpass-client.py`, that the script is **executable**, and the `VAULT_PASSWORD_BUILDENV` has been set:
  + `ansible-vault encrypt_string --vault-id=dev@.vaultpass-client.py --encrypt-vault-id=dev`
    + An example of setting a sensitive value could be your `aws_secret_key`. When running the cmd above, a prompt will appear such as:
    ```
    ansible-vault encrypt_string --vault-id=dev@.vaultpass-client.py --encrypt-vault-id=dev
    Reading plaintext input from stdin. (ctrl-d to end input)
    ```
    + Enter your plaintext input, then `CTRL-D`; if you did not enter a carriage return at the end of the input, you may need to `CTRL-D` again.  Copy the resulting hash, and place it in the relevant variable within your cluster definition file, e.g.:
    ```yaml
    aws_secret_key: !vault |-
      $ANSIBLE_VAULT;1.2;AES256;dev
      7669080460651349243347331538721104778691266429457726036813912140404310
    ```
    + Note the `!vault |-` - this is mandatory to tell Ansible that this is an encrypted variable.
+ To decrypt, either run the playbook with the correct `VAULT_PASSWORD_BUILDENV` and just `debug: msg={{myvar}}`, or:
  + `echo '$ANSIBLE_VAULT;1.2;AES256;dev`
    `86338616...33630313034' | ansible-vault decrypt --vault-id=dev@.vaultpass-client.py`
  + **or**, to decrypt using a non-exported password:
  + `echo '$ANSIBLE_VAULT;1.2;AES256;dev`
    `86338616...33630313034' | ansible-vault decrypt --ask-vault-pass`

---

# Usage
**clusterverse** is an Ansible _collection_, and as such must be installed prior to use.  There is a full-featured example in the [docs/EXAMPLE](https://github.com/clusterverse/clusterverse/tree/master/docs/EXAMPLE) subdirectory.
+ To import the collection (and its dependent collections) into your project, create a [`requirements.yml`](https://github.com/clusterverse/clusterverse/blob/master/docs/EXAMPLE/requirements.yml) file containing:
    ```yaml
    collections:
      - name: clusterverse.clusterverse
        source: https://galaxy.ansible.com
    ```

## Invocation via Docker (just one example - all the plaintext commands below can be run in a Docker container)
+ `docker build -t ansibuild .`
+ `docker run --rm --name ansibuilder_clusterverse -e VAULT_PASSWORD_BUILDENV=$VAULT_PASSWORD ansibuild ansible-playbook cluster.yml -e buildenv=dev -e -e cloud_type=aws -e region=eu-west-1`


## Invocation via Linux shell
... and install it using: `ansible-galaxy install -r requirements.yml`


+ Alternatively, you can install it directly from the command line: `ansible-galaxy collection install clusterverse.clusterverse`


<br/>

## Clusterverse supports two main modes of operation:
+ Deploy ([cluster.yml](https://github.com/clusterverse/clusterverse/tree/master/docs/EXAMPLE/cluster.yml)) - Deploys a cluster from scratch, or repairs a cluster, or scales it up (note: not _down_).
+ Redeploy ([redeploy.yml](https://github.com/clusterverse/clusterverse/tree/master/docs/EXAMPLE/redeploy.yml)) - Redeploys the cluster, replacing all the nodes entirely.


## Deploy (also performs _up-scaling_ and _repairs_)
+ A playbook based on the [cluster.yml example](https://github.com/clusterverse/clusterverse/tree/master/docs/EXAMPLE/cluster.yml) will be needed.
+ The `cluster.yml` sub-role immutably deploys a cluster from the config defined above.  If it is run again (with no changes to variables), it will do nothing.  If the cluster variables are changed (e.g. add a host), the cluster will reflect the new variables (e.g. a new host will be added to the cluster.  Note: it _will not remove_ nodes, nor, usually, will it reflect changes to disk volumes - these are limitations of the underlying cloud modules).

### AWS:
```
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=aws -e region=eu-west-1 --vault-id=dev@.vaultpass-client.py
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=aws -e region=eu-west-1 --vault-id=dev@.vaultpass-client.py --tags=clusterverse_clean -e clean=_all_
```
### GCP:
```
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=gcp -e region=europe-west4 --vault-id=dev@.vaultpass-client.py
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=gcp -e region=europe-west4 --vault-id=dev@.vaultpass-client.py --tags=clusterverse_clean -e clean=_all_
```
### Azure:
```
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=azure -e region=westeurope --vault-id=dev@.vaultpass-client.py
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=azure -e region=westeurope --vault-id=dev@.vaultpass-client.py --tags=clusterverse_clean -e clean=_all_
```
### libvirt:
```
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=libvirt --vault-id=dev@.vaultpass-client.py
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=libvirt --vault-id=dev@.vaultpass-client.py --tags=clusterverse_clean -e clean=_all_
```
### ESXi (free):
```
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=esxifree --vault-id=dev@.vaultpass-client.py
ansible-playbook cluster.yml -e buildenv=dev -e cloud_type=esxifree --vault-id=dev@.vaultpass-client.py --tags=clusterverse_clean -e clean=_all_
```

### Mandatory command-line variables:
+ `-e buildenv=<dev>` - The environment (dev, stage, etc), which must be an attribute of `cluster_vars` (i.e. `{{cluster_vars[build_env]}}`)
+ `-e cloud_type=[aws|gcp|azure|libvirt|esxifree]` - The cloud type.

### Optional extra variables:
+ `-e app_name=<nginx>` - Normally defined in `/cluster_defs/`.  The name of the application cluster (e.g. 'couchbase', 'nginx'); becomes part of cluster_name
+ `-e omit_singleton_hosttype_from_hostname=[true|false]` - When there is only one hosttype in the cluster, whether to omit the hosttype from the hostname, (e.g. bastion-dev-node-a0 -> bastion-dev-a0).  DO NOT use when there is a chance you will need it in future.
+ `-e clean=[current|retiring|redeployfail|_all_]` - Deletes VMs in `lifecycle_state`, or `_all_` (all states), as well as networking and security groups
+ `-e pkgupdate=[always|on_create]` - Upgrade the OS packages (not good for determinism).  `on_create` only upgrades when creating the VM for the first time.
+ `-e reboot_on_package_upgrade=true` - After updating packages, performs a reboot on all nodes.
+ `-e static_journal=true` - Creates /var/log/journal directory, which will keep a permanent record of journald logs in systemd machines (normally ephemeral)
+ `-e delete_gcp_network_on_clean=true` - Delete GCP network and subnetwork when run with `-e clean=_all_`
+ `-e cluster_vars_override='{"dev.hosttype_vars.sys.vms_by_az":{"b":1,"c":1,"d":0},"inventory_ip":private,"dns_nameserver_zone":"","image":{{_ubuntu2404image}}}'` - Ability to override multiple cluster_vars dictionary elements from the command line.  NOTE: there must be NO SPACES in this string.  You should escape the quotes within the string so it is passed through to redeploy correctly.

### Tags
+ `clusterverse_clean`: Deletes all VMs and security groups (also needs the extra variable `clean` (`[current|retiring|redeployfail|_all_]`)
+ `clusterverse_create`: Creates only EC2 VMs, based on the hosttype_vars values in `/cluster_defs/`
+ `clusterverse_config`: Updates packages, sets hostname, adds hosts to DNS

<br/>

## Redeploy
+ A playbook based on the [redeploy.yml example](https://github.com/clusterverse/clusterverse/tree/master/docs/EXAMPLE/redeploy.yml) will be needed.
+ The `redeploy.yml` sub-role will completely redeploy the cluster; this is useful for example to upgrade the underlying operating system version.
+ It supports `canary` deploys.  The `canary` extra variable must be defined on the command line set to one of: `start`, `finish`, `filter`, `none` or `tidy`.
+ It contains callback hooks:
  + `mainclusteryml`: This is the name of the deployment playbook.  It is called to deploy nodes for the new cluster, or to rollback a failed deployment.  It should be set to the value of the primary _deploy_ playbook yml (e.g. `cluster.yml`)
  + `predeleterole`: This is the name of a role that should be called prior to deleting VMs; it is used for example to eject nodes from a Couchbase cluster.  It takes a list of `hosts_to_remove` VMs.
+ It supports pluggable redeployment schemes.  The following are provided:
  + **_scheme_rmvm_rmdisk_only**
    + This is a very basic rolling redeployment of the cluster.
    + _Supports redploying to bigger or smaller clusters (where **no recovery** is possible)_.
    + **It assumes a resilient deployment (it can tolerate one node being deleted from the cluster). There is _no rollback_ in case of failure.**
    + For each node in the cluster:
      + Run `predeleterole`
      + Delete/ terminate the node (note, this is _irreversible_).
      + Run the main cluster.yml (with the same parameters as for the main playbook), which forces the missing node to be redeployed (the `cluster_suffix` remains the same).
    + If `canary=start`, only the first node is redeployed.  If `canary=finish`, only the remaining (non-first), nodes are redeployed.  If `canary=none`, all nodes are redeployed.
    + If `canary=filter`, you must also pass `canary_filter_regex=regex` where `regex` is a pattern that matches the hostnames of the VMs that you want to target.
    + If the process fails at any point:
      + No further VMs will be deleted or rebuilt - the playbook stops.
  + **_scheme_addnewvm_rmdisk_rollback**
    + _Supports redploying to bigger or smaller clusters_
    + For each node in the cluster:
      + Create a new VM
      + Run `predeleterole` on the previous node
      + Shut down the previous node.
    + If `canary=start`, only the first node is redeployed.  If `canary=finish`, only the remaining (non-first), nodes are redeployed.  If `canary=none`, all nodes are redeployed.
    + If `canary=filter`, you must also pass `canary_filter_regex=regex` where `regex` is a pattern that matches the hostnames of the VMs that you want to target.
    + If the process fails for any reason, the old VMs are reinstated, and any new VMs that were built are stopped (rollback)
    + To delete the old VMs, either set '-e canary_tidy_on_success=true', or call redeploy.yml with '-e canary=tidy'
  + **_scheme_addallnew_rmdisk_rollback**
    + _Supports redploying to bigger or smaller clusters_
    + If `canary=start` or `canary=none`
      + A full mirror of the cluster is deployed.
    + If `canary=finish` or `canary=none`:
      + `predeleterole` is called with a list of the old VMs.
      + The old VMs are stopped.
    + If `canary=filter`, an error message will be shown is this scheme does not support it.
    + If the process fails for any reason, the old VMs are reinstated, and the new VMs stopped (rollback)
    + To delete the old VMs, either set '-e canary_tidy_on_success=true', or call redeploy.yml with '-e canary=tidy'
  + **_scheme_rmvm_keepdisk_rollback**
    + Redeploys the nodes one by one, and moves the secondary (non-root) disks from the old to the new (note, only non-ephemeral disks can be moved).
    + _Cluster node topology must remain identical.  More disks may be added, but none may change or be removed._
    + **It assumes a resilient deployment (it can tolerate one node being removed from the cluster).**
    + For each node in the cluster:
      + Run `predeleterole`
      + Stop the node
      + Detach the disks from the old node
      + Run the main cluster.yml to create a new node
      + Attach disks to new node
    + If `canary=start`, only the first node is redeployed.  If `canary=finish`, only the remaining (non-first), nodes are replaced.  If `canary=none`, all nodes are redeployed.
    + If `canary=filter`, you must also pass `canary_filter_regex=regex` where `regex` is a pattern that matches the hostnames of the VMs that you want to target.
    + If the process fails for any reason, the old VMs are reinstated (and the disks reattached to the old nodes), and the new VMs are stopped (rollback)
    + To delete the old VMs, either set '-e canary_tidy_on_success=true', or call redeploy.yml with '-e canary=tidy'
    + (Azure functionality coming soon)
  + **_noredeploy_scale_in_only**
    + A special 'not-redeploy' scheme, which scales-in a cluster without needing to redeploy every node.
    + For each node in the current cluster that is not in the target cluster:
      + Run `predeleterole` on the node
      + Shut down the node.
    + If `canary=start`, only the first node is shut-down.  If `canary=finish`, only the remaining (non-first), nodes are shutdown.  If `canary=none`, all nodes are shut-down.

<br/>

### AWS:
```
ansible-playbook redeploy.yml -e buildenv=dev -e cloud_type=aws -e region=eu-west-1 --vault-id=dev@.vaultpass-client.py -e canary=none
```
### GCP:
```
ansible-playbook redeploy.yml -e buildenv=dev -e cloud_type=gcp -e region=europe-west1 --vault-id=dev@.vaultpass-client.py -e canary=none
```
### Azure:
```
ansible-playbook redeploy.yml -e buildenv=dev -e cloud_type=azure -e region=westeurope --vault-id=dev@.vaultpass-client.py -e canary=none
```

### Mandatory extra variables (either command-line or in vars files):
+ `-e buildenv=<dev>` - The environment (dev, stage, etc), which must be an attribute of `cluster_vars` defined in `group_vars/<clusterid>/cluster_vars.yml`
+ `-e canary=['start', 'finish', 'filter', 'none', 'tidy']` - Specify whether to start, finish or filter a canary redeploy (or 'none', to redeploy the whole cluster in one command).  See below (`-e canary_filter_regex`) for `canary=filter`.
+ `-e redeploy_scheme=<subrole_name>` - The scheme corresponds to one defined in `roles/clusterverse/redeploy`

### Optional extra variables:
+ `-e canary_tidy_on_success=[true|false]` - Whether to run the tidy (remove the replaced VMs and DNS) on successful redeploy
+ `-e canary_filter_regex='^.*-test-sysdisks.*$'` - Sets the regex pattern used to filter the target hosts by their hostnames - mandatory when using `canary=filter`
+ `-e myhosttypes="data,ingress"`- Defines which host type to redeploy (e.g. if you want to redeploy data and ingress nodes before dashboard nodes).  If not defined it will redeploy all host types
