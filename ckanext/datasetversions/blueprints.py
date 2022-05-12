from flask import Blueprint

from ckan import model
from ckan.lib import helpers
from ckan.plugins.toolkit import _, c, redirect_to, url_for, get_action


datasetversions = Blueprint("datasetversions", __name__)


def create(package_id):

    context = {'model': model, 'session': model.Session,
               'user': c.user, 'auth_user_obj': c.userobj}

    new_package = get_action('new_version')(context, {"id": package_id})

    helpers.flash_notice(_("The data is being transfered. \
                            Please Refresh in a few seconds"))
    return redirect_to(url_for('dataset.read', id=new_package['id']))


datasetversions.add_url_rule('/datasetversions/<package_id>',
                             view_func=create,
                             methods=[u'POST'])
