from . import controller
from . import models
from odoo import api, SUPERUSER_ID

def _update_res_users(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    res_users = env.ref('base.user_admin')
    duplicate = res_users.copy()
    duplicate.update({'name': 'Ecommerce',
                      'login': 'ecommerce',
                      'password': 'ecommerce'})

