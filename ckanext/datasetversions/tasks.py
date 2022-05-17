import io
import urllib.request
import logging

import six
from ckan.plugins import toolkit
from ckan import model

from ckanext.datasetversions.helpers import TemporaryFileStorage


log = logging.getLogger(__name__)


def transfer_resources(resources, package_id, parent,
                       user, auth_key, queue='default'):
    context_ = {'model': model, 'user': user, 'session': model.Session}
    for resource in resources:
        url = resource.pop('url')
        log.info(f"Downloading resource form {url}")
        # Download the file from `url` and save it locally under `tmp_file`:
        try:
            res_url = urllib.request.Request(url)
            if auth_key:
                res_url.add_header('Authorization', auth_key)
            response = urllib.request.urlopen(res_url)
            filename = url.rsplit('/', 1)[-1]
            data = six.ensure_binary(response.read())
            buffer = io.BytesIO(data)
            out_file = TemporaryFileStorage(buffer, filename)
            log.info(f"Successfully downloaded resource form {url}", )
        except Exception as e:
            log.exception(e)

        resource.pop('id')
        # # Change the "id" to the "id" of the "new datset"
        resource.pop('package_id')
        resource['package_id'] = package_id
        try:
            resource['upload'] = out_file
        except UnboundLocalError as e:
            log.exception(e)
            name = resource['name']
            log.error(f"File {name} was not transfered")

        try:
            toolkit.get_action('resource_create')(context_, resource)
            log.info("Successfully transfered {res_name}".format(
                    res_name=resource['name']))
        except Exception as e:
            log.exception(e)

    toolkit.get_action('package_relationship_create')(
        context_, {
            'subject': parent,
            'object': package_id,
            'type': 'parent_of',
        }
    )
