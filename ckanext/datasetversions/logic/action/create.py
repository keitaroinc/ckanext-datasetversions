import re

import ckan.logic as logic
from ckan.logic.action.get import package_show as ckan_package_show
from ckan.plugins import toolkit

from ckanext.datasetversions.helpers import get_context
from ckanext.datasetversions.lib import compat_enqueue
from ckanext.datasetversions.tasks import transfer_resources


_check_access = logic.check_access


def dataset_version_create(context, data_dict):
    id = data_dict.get('id')
    parent_name = data_dict.get('base_name')

    owner_org = data_dict.get('owner_org')

    parent_dict = {
        'name': parent_name,
        '__parent': True,
    }

    if owner_org:
        parent_dict['owner_org'] = owner_org
        parent_dict['private'] = True
    else:
        parent_dict['private'] = False

    parent = _get_or_create_parent_dataset(
        context,
        parent_dict
    )

    toolkit.get_action('package_relationship_create')(
        get_context(context), {
            'subject': id,
            'object': parent['id'],
            'type': 'child_of',
        }
    )


def _get_or_create_parent_dataset(context, data_dict):
    try:
        dataset = ckan_package_show(
            get_context(context), {'id': data_dict['name']})
    except (logic.NotFound):
        dataset = toolkit.get_action('package_create')(
            get_context(context), data_dict)

    return dataset


def new_version(context, data_dict):
    """Create a new dataset whitch is linked to the parent dataset.

    You must be authorized to create datasets.
    You must be authorized to edit both the subject and the object datasets.

    :param subject: the id of the dataset that is the subject of the
        relationship
    :type subject: string

    :returns: the newly created dataset
    :rtype: dictionary
    """
    _check_access('package_create', context, data_dict)
    id = data_dict.get('id')

    releationship = toolkit.get_action('package_relationships_list')(
        get_context(context), {"id": id})
    # Get the parent of the releationship
    try:
        releationship[0]
        if releationship[0]['type'] == "child_of":
            parent = releationship[0]['object']
        else:
            parent = releationship[0]['subject']
    # If no releationship means no versions exists
    except IndexError:
        parent = data_dict.get('id')

    # The overwritten action from "ckanext-dataversions"
    # We need the parents "ID" to get the latest version
    dataset = toolkit.get_action('package_show')(
            get_context(context), {"id": id})

    # get version
    version = dataset.get('version', None)

    if version is None or version == "":
        version = 1
    else:
        version = int(version) + 1

    name = dataset['name']
    if version == 1:
        new_name = name + '-v1'
    else:
        # get the last substring of digits from the name(URL)
        m = re.search(r'\d+$', name)
        ver_num = m.group()
        # Split the name on the version
        # ex. test-v2 ---> test-v
        name = name.rsplit(ver_num, 1)[0]
        # Add the number+1 to the end of the new name
        new_ver_num = str(int(ver_num) + 1)
        new_name = name + new_ver_num

    # remove "id", "name" and "version" so we can change them appropriately
    dataset.pop('id')
    dataset.pop('name')
    try:
        dataset.pop('version')
    except KeyError:
        pass

    # Remove the resources and they will be uploaded seperatly
    resources = dataset.pop('resources')

    dataset['name'] = new_name
    dataset['version'] = version

    new_dataset = toolkit.get_action('package_create')(
                  get_context(context), dataset)

    user = context.get('user')
    auth_key = context.get('auth_user_obj')['apikey']
    queue = 'default'

    compat_enqueue(transfer_resources, queue,
                   args=[resources, new_dataset['id'],
                         parent, user, auth_key])

    return new_dataset
