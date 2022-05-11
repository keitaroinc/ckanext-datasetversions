from ckan.plugins import toolkit

import ckan.logic as logic
from ckan.logic.action.get import package_show as ckan_package_show

from ckanext.datasetversions.helpers import get_context


@toolkit.side_effect_free
def package_show(context, data_dict):
    # The parent dataset is private so it doesn't appear in the lists
    # but we want to override the authentication checks so we can
    # access the child datasets that represent the different versions
    ignore_auth = context.get('ignore_auth')
    context['ignore_auth'] = True

    # Get the dataset we actually asked for
    requested_dataset = ckan_package_show(context, data_dict)

    version_to_display = requested_dataset

    parent_names = _get_parent_dataset_names(
        get_context(context), requested_dataset['id'])

    if len(parent_names) > 0:
        base_name = parent_names[0]
        all_version_names = _get_child_dataset_names(
            get_context(context), base_name)
    else:
        # Requesting the latest version or an unversioned dataset
        base_name = requested_dataset['name']

        all_version_names = _get_child_dataset_names(
            get_context(context), base_name)

    all_active_versions = _get_ordered_active_dataset_versions(
        get_context(context),
        data_dict.copy(),  # Will get modified so make a copy
        base_name,
        all_version_names)

    # Do default CKAN authentication
    context['ignore_auth'] = ignore_auth
    logic.check_access('package_show', get_context(context), data_dict)

    version_to_display['_versions'] = _get_version_names_and_urls(
        all_active_versions, base_name)

    # Reindexing fails if we don't do this
    # Later versions of CKAN will not include these in the package
    # See https://github.com/ckan/ckan/issues/3114
    version_to_display.pop('relationships_as_subject', False)
    version_to_display.pop('relationships_as_object', False)

    return version_to_display


def _get_version_names_and_urls(all_active_versions, base_name):
    version_names_and_urls = []

    for (i, v) in enumerate(all_active_versions):
        if i == 0:
            url = base_name
        else:
            url = v['name']

        version_names_and_urls.append((v['name'], url))

    return version_names_and_urls


def _get_child_dataset_names(context, parent_id):
    children = []

    try:
        children = toolkit.get_action('package_relationships_list')(
            context,
            data_dict={'id': parent_id,
                       'rel': 'parent_of'})
    except logic.NotFound:
        pass

    return _get_names_from_relationships(children)


def _get_parent_dataset_names(context, child_id):
    parents = []

    try:
        parents = toolkit.get_action('package_relationships_list')(
            context,
            data_dict={'id': child_id,
                       'rel': 'child_of'})
    except logic.NotFound:
        pass

    return _get_names_from_relationships(parents)


def _get_names_from_relationships(relationships):
    return [r['object'] for r in relationships]


def _get_ordered_active_dataset_versions(context, data_dict,
                                         base_name, child_names):
    versions = []
    parrent = ckan_package_show(context, {"id": base_name})
    if parrent['state'] == 'active':
        versions.append(parrent)
    for name in child_names:
        data_dict['id'] = name
        version = ckan_package_show(context, data_dict)
        if version['state'] == 'active':
            versions.append(version)

    versions.sort(key=_get_version, reverse=True)

    return versions


def _get_version(dataset):
    try:
        version_number = int(dataset['version'])
    except (ValueError, TypeError, KeyError):
        version_number = 0

    return version_number
