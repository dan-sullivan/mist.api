import logging

from pyramid.response import Response
from mist.api.clouds.models import Cloud
from mist.api.auth.methods import auth_context_from_request

from mist.api.helpers import trigger_session_update
from mist.api.helpers import view_config, params_from_request

from mist.api.exceptions import BadRequestError
from mist.api.exceptions import RequiredParameterMissingError, NotFoundError

from mist.api.clouds.methods import filter_list_clouds, add_cloud_v_2
from mist.api.clouds.methods import rename_cloud as m_rename_cloud
from mist.api.clouds.methods import delete_cloud as m_delete_cloud

from mist.api.tag.methods import add_tags_to_resource

from mist.api import config

logging.basicConfig(level=config.PY_LOG_LEVEL,
                    format=config.PY_LOG_FORMAT,
                    datefmt=config.PY_LOG_FORMAT_DATE)
log = logging.getLogger(__name__)

OK = Response("OK", 200)


@view_config(route_name='api_v1_clouds', request_method='GET', renderer='json')
def list_clouds(request):
    """
    Tags: clouds
    ---
    Lists all added clouds.
    READ permission required on cloud.
    ---
    """
    auth_context = auth_context_from_request(request)
    # to prevent iterate throw every cloud
    auth_context.check_perm("cloud", "read", None)
    return filter_list_clouds(auth_context)


@view_config(route_name='api_v1_clouds',
             request_method='POST', renderer='json')
def add_cloud(request):
    """
    Tags: clouds
    ---
    Adds a new cloud and returns the cloud's id.
    ADD permission required on cloud.
    ---
    api_key:
      type: string
      description: Required for Clearcenter
    api_secret:
      type: string
    apikey:
      type: string
      description: Required for Ec2, Hostvirtual, Linode, Packet, Rackspace, OnApp, SoftLayer, Vultr
    apisecret:
      type: string
      description: Required for Ec2
    apiurl:
      type: string
    auth_password:
      description: Optional for Docker
      type: string
    auth_url:
      type: string
      description: Required for OpenStack
    auth_user:
      description: Optional for Docker
      type: string
    authentication:
      description: Required for Docker
      enum:
      - tls
      - basic
    ca_cert_file:
      type: string
      description: Optional for Docker
    cert_file:
      type: string
      description: Optional for Docker
    certificate:
      type: string
      description: Required for Azure
    compute_endpoint:
      type: string
      description: Optional for OpenStack
    dns_enabled:
      type: boolean
    docker_host:
      description: Required for Docker
    docker_port:
      type: string
    host:
      type: string
      description: Required for OnApp, Vcloud, vSphere
    images_location:
      type: string
      description: Required for KVM
    key:
      type: string
      description: Required for Azure_arm
    key_file:
      type: string
      description: Optional for Docker
    machine_hostname:
      type: string
      description: Required for KVM
    machine_key:
      type: string
      description: Id of the key. Required for KVM
    machine_port:
      type: string
    machine_user:
      type: string
      description: Required for KVM
    organization:
      type: string
      description: Required for Vcloud
    password:
      type: string
      description: Required for Nephoscale, OpenStack, Vcloud, vSphere
    port:
      type: integer
      description: Required for Vcloud
    private_key:
      type: string
      description: Required for GCE
    project_id:
      type: string
      description: Required for GCE. Optional for Packet
    provider:
      description: The cloud provider.
      required: True
      enum:
      - vcloud
      - bare_metal
      - docker
      - libvirt
      - openstack
      - vsphere
      - ec2
      - rackspace
      - nephoscale
      - digitalocean
      - softlayer
      - gce
      - azure
      - azure_arm
      - linode
      - onapp
      - hostvirtual
      - vultr
      - clearcenter
      required: true
      type: string
    region:
      type: string
      description: Required for Ec2, Rackspace. Optional for Openstack
    remove_on_error:
      type: string
    secret:
      type: string
      description: Required for Azure_arm
    ssh_port:
      type: integer
      description: Required for KVM
    subscription_id:
      type: string
      description: Required for Azure, Azure_arm
    tenant_id:
      type: string
      description: Required for Azure_arm
    tenant_name:
      type: string
      description: Required for OpenStack
    title:
      description: The human readable title of the cloud.
      type: string
      required: True
    token:
      type: string
      description: Required for Digitalocean
    username:
      type: string
      description: Required for Nephoscale, Rackspace, OnApp, SoftLayer, OpenStack, Vcloud, vSphere
    """
    auth_context = auth_context_from_request(request)
    cloud_tags = auth_context.check_perm("cloud", "add", None)
    owner = auth_context.owner
    params = params_from_request(request)
    # remove spaces from start/end of string fields that are often included
    # when pasting keys, preventing thus succesfull connection with the
    # cloud
    for key in params.keys():
        if type(params[key]) in [unicode, str]:
            params[key] = params[key].rstrip().lstrip()

    # api_version = request.headers.get('Api-Version', 1)
    title = params.get('title', '')
    provider = params.get('provider', '')

    if not provider:
        raise RequiredParameterMissingError('provider')

    monitoring = None
    ret = add_cloud_v_2(owner, title, provider, params)

    cloud_id = ret['cloud_id']
    monitoring = ret.get('monitoring')

    cloud = Cloud.objects.get(owner=owner, id=cloud_id)

    # If insights enabled on org, set poller with half hour period.
    if auth_context.org.insights_enabled:
        cloud.ctl.set_polling_interval(1800)

    if cloud_tags:
        add_tags_to_resource(owner, cloud, cloud_tags.items())

    c_count = Cloud.objects(owner=owner, deleted=None).count()
    ret = cloud.as_dict()
    ret['index'] = c_count - 1
    if monitoring:
        ret['monitoring'] = monitoring
    return ret


@view_config(route_name='api_v1_cloud_action', request_method='DELETE')
def delete_cloud(request):
    """
    Tags: clouds
    ---
    Deletes a cloud with given cloud_id.
    REMOVE permission required on cloud.
    ---
    cloud:
      in: path
      required: true
      type: string
    """
    auth_context = auth_context_from_request(request)
    cloud_id = request.matchdict['cloud']
    try:
        Cloud.objects.get(owner=auth_context.owner, id=cloud_id, deleted=None)
    except Cloud.DoesNotExist:
        raise NotFoundError('Cloud does not exist')
    auth_context.check_perm('cloud', 'remove', cloud_id)
    m_delete_cloud(auth_context.owner, cloud_id)
    return OK


@view_config(route_name='api_v1_cloud_action', request_method='PUT')
def rename_cloud(request):
    """
    Tags: clouds
    ---
    Renames cloud with given cloud_id.
    EDIT permission required on cloud.
    ---
    cloud:
      in: path
      required: true
      type: string
    new_name:
      description: ' New name for the given cloud'
      type: string
    """
    auth_context = auth_context_from_request(request)
    cloud_id = request.matchdict['cloud']
    try:
        Cloud.objects.get(owner=auth_context.owner, id=cloud_id, deleted=None)
    except Cloud.DoesNotExist:
        raise NotFoundError('Cloud does not exist')

    params = params_from_request(request)
    new_name = params.get('new_name', '')
    if not new_name:
        raise RequiredParameterMissingError('new_name')
    auth_context.check_perm('cloud', 'edit', cloud_id)

    m_rename_cloud(auth_context.owner, cloud_id, new_name)
    return OK


@view_config(route_name='api_v1_cloud_action', request_method='PATCH')
def update_cloud(request):
    """
    Tags: clouds
    ---
    Updates cloud with given cloud_id.
    EDIT permission required on cloud.
    Not all fields need to be specified, only the ones being modified
    ---
    cloud_id:
      in: path
      required: true
      type: string
    """
    auth_context = auth_context_from_request(request)
    cloud_id = request.matchdict['cloud']
    try:
        cloud = Cloud.objects.get(owner=auth_context.owner,
                                  id=cloud_id, deleted=None)
    except Cloud.DoesNotExist:
        raise NotFoundError('Cloud does not exist')

    params = params_from_request(request)
    creds = params

    if not creds:
        raise BadRequestError("You should provide your new cloud settings")

    auth_context.check_perm('cloud', 'edit', cloud_id)

    log.info("Updating cloud: %s", cloud_id)

    fail_on_error = params.pop('fail_on_error', True)
    fail_on_invalid_params = params.pop('fail_on_invalid_params', True)
    polling_interval = params.pop('polling_interval', None)

    # Edit the cloud
    cloud.ctl.update(fail_on_error=fail_on_error,
                     fail_on_invalid_params=fail_on_invalid_params, **creds)

    try:
        polling_interval = int(polling_interval)
    except (ValueError, TypeError):
        pass
    else:
        cloud.ctl.set_polling_interval(polling_interval)

    log.info("Cloud with id '%s' updated successfully.", cloud.id)
    trigger_session_update(auth_context.owner, ['clouds'])
    return OK


@view_config(route_name='api_v1_cloud_action', request_method='POST')
def toggle_cloud(request):
    """
    Tags: clouds
    ---
    Toggles cloud with given cloud id.
    EDIT permission required on cloud.
    ---
    cloud_id:
      in: path
      required: true
      type: string
    new_state:
      enum:
      - '0'
      - '1'
      required: true
      type: string
    """
    auth_context = auth_context_from_request(request)
    cloud_id = request.matchdict['cloud']
    try:
        cloud = Cloud.objects.get(owner=auth_context.owner,
                                  id=cloud_id, deleted=None)
    except Cloud.DoesNotExist:
        raise NotFoundError('Cloud does not exist')

    auth_context.check_perm('cloud', 'edit', cloud_id)

    new_state = params_from_request(request).get('new_state', None)
    dns_enabled = params_from_request(request).get('dns_enabled', None)

    if new_state == '1':
        cloud.ctl.enable()
    elif new_state == '0':
        cloud.ctl.disable()
    elif new_state:
        raise BadRequestError('Invalid cloud state')

    if dns_enabled == 1:
        cloud.ctl.dns_enable()
    elif dns_enabled == 0:
        cloud.ctl.dns_disable()
    elif dns_enabled:
        raise BadRequestError('Invalid DNS state')

    if new_state is None and dns_enabled is None:
        raise RequiredParameterMissingError('new_state or dns_enabled')

    trigger_session_update(auth_context.owner, ['clouds'])
    return OK
