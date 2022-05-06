import io
import re
import urllib.request
import six

import ckan.logic as logic
from ckan.logic.action.get import package_show as ckan_package_show
from ckan.plugins import toolkit

from ckanext.datasetversions.helpers import get_context, TemporaryFileStorage


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
        get_context(context), {"id": parent})

    # get version
    version = dataset.get('version', None)
    if version is None:
        version = 1
    else:
        version = int(version) + 1
    print('---------> VERSION', version)

    # TODO: Create a new dataset with copies of all the resources of
    # the previous version
    name = dataset['name']
    if version == 1:
        new_name = name + '-v1'
    else:
        # get the last substring of digits from the name(URL)
        m = re.search(r'\d+$', name)
        ver_num = m.group()
        # Split the name on the version
        # ex. test-v2 ---> test-v
        name = name.split(ver_num, 1)[0]
        # Add the number+1 to the end of the new name
        new_ver_num = str(int(ver_num) + 1)
        new_name = name + new_ver_num

    # remove "id", "name" and "version" so we can change them appropriately
    dataset.pop('id')
    dataset.pop('name')
    dataset.pop('version')
    # Remove the resources and they will be uploaded seperatly
    resources = dataset.pop('resources')

    dataset['name'] = new_name
    dataset['version'] = version
    # The resource need to be reUPLOADED because this is just
    # the same resource so if you change it in the verson it will change
    # it in the previous version which should not be the case

    # Expected behaivaour:
    # create a new dataset with the same resources but,
    # the resources should be new (seperate resource)
    new_dataset = toolkit.get_action('package_create')(
                  get_context(context), dataset)

    for resource in resources:
        url = resource.pop('url')
        print(url)
        print("TUKA=========================")
        # Download the file from `url` and save it locally under `tmp_file`:
        try:
            response = urllib.request.urlopen(
                url)
        except Exception as e:
            print(e)
        print("TUKA++++++++++++++++++++++++++")

        filename = url.rsplit('/', 1)[-1]
        data = six.ensure_binary(response.read())
        buffer = io.BytesIO(data)
        out_file = TemporaryFileStorage(buffer, filename)

        resource.pop('id')
        # # Change the "id" to the "id" of the "new datset"
        resource.pop('package_id')
        resource['package_id'] = new_dataset['id']

        resource['upload'] = out_file

        try:
            toolkit.get_action('resource_create')(
                get_context(context), resource)
        except Exception as e:
            print("EXCEPTION")
            print(e)

    # Create the new version with releationship as "type": "child_of"
    toolkit.get_action('dataset_version_create')(
        get_context(context), {
            'id': new_dataset['id'],
            'base_name': parent,
            'owner_org': dataset['organization']['id']
        }
    )

    return new_dataset
