from odoo import models, fields, api, _
import json, requests, random, string, math
from math import sin, cos, sqrt, atan2, radians
import base64
import string
import random
import hashlib
import sys
from datetime import datetime
from Crypto.Cipher import AES

iv = '@@@@&&&&####$$$$'
BLOCK_SIZE = 16

if (sys.version_info > (3, 0)):
    __pad__ = lambda s: bytes(s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * chr(BLOCK_SIZE - len(s) % BLOCK_SIZE), 'utf-8')
else:
    __pad__ = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * chr(BLOCK_SIZE - len(s) % BLOCK_SIZE)

__unpad__ = lambda s: s[0:-ord(s[-1])]


def encrypt(input, key):
    input = __pad__(input)
    c = AES.new(key.encode("utf8"), AES.MODE_CBC, iv.encode("utf8"))
    input = c.encrypt(input)
    input = base64.b64encode(input)
    return input.decode("UTF-8")


def decrypt(encrypted, key):
    encrypted = base64.b64decode(encrypted)
    c = AES.new(key.encode("utf8"), AES.MODE_CBC, iv.encode("utf8"))
    param = c.decrypt(encrypted)
    if type(param) == bytes:
        param = param.decode()
    return __unpad__(param)


def generateSignature(params, key):
    if not type(params) is dict and not type(params) is str:
        raise Exception("string or dict expected, " + str(type(params)) + " given")
    if type(params) is dict:
        params = getStringByParams(params)
    return generateSignatureByString(params, key)


def verifySignature(params, key, checksum):
    if not type(params) is dict and not type(params) is str:
        raise Exception("string or dict expected, " + str(type(params)) + " given")
    if "CHECKSUMHASH" in params:
        del params["CHECKSUMHASH"]

    if type(params) is dict:
        params = getStringByParams(params)
    return verifySignatureByString(params, key, checksum)


def generateSignatureByString(params, key):
    salt = generateRandomString(4)
    return calculateChecksum(params, key, salt)


def verifySignatureByString(params, key, checksum):
    paytm_hash = decrypt(checksum, key)
    salt = paytm_hash[-4:]
    return paytm_hash == calculateHash(params, salt)


def generateRandomString(length):
    chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
    return ''.join(random.choice(chars) for _ in range(length))


def getStringByParams(params):
    params_string = []
    for key in sorted(params.keys()):
        value = params[key] if params[key] is not None and params[key].lower() != "null" else ""
        params_string.append(str(value))
    return '|'.join(params_string)


def calculateHash(params, salt):
    finalString = '%s|%s' % (params, salt)
    hasher = hashlib.sha256(finalString.encode())
    hashString = hasher.hexdigest() + salt
    return hashString


def calculateChecksum(params, key, salt):
    hashString = calculateHash(params, salt)
    return encrypt(hashString, key)

class IRAttachment(models.Model):
    _inherit = "ir.attachment"

    top_banner_id = fields.Many2one('website')
    special_for_you_id = fields.Many2one('website')

    category_id = fields.Many2one('product.public.category')

    offer_text = fields.Char('Offer Text')


class ResUser(models.Model):
    _inherit = "res.users"

    device_token = fields.Text('Device Token')

    def changePassword(self, newPassword):
        try:
            return self.write({'password': newPassword})
        except:
            return False

    def xmlid_to_res_id(self, vals):
        return self.env.ref(vals).id

    def _default_referral_code(self):

        def id_generator(size=6, chars=string.ascii_uppercase):
            return ''.join(random.choice(chars) for _ in range(size))

        odoo_seq = self.env['ir.sequence'].next_by_code('sltech.referral.code') or _('New')
        referral_code = id_generator() + odoo_seq
        return ''.join(random.sample(referral_code, len(referral_code)))

    isProductReview = fields.Boolean(default=False, string='Product Review')
    refer_code = fields.Char(string='Refer Code', default=_default_referral_code)
    isFirstOrder = fields.Boolean(default=True,string="Is First Order")
    refer_by = fields.Many2one('res.users',string="Refer By")

    def create_points(self, action_name, credit=0,force_action_name=""):
        point_id = self.env['sltech.points.rules'].search([('name', '=', action_name)])

        if force_action_name != "":
            action_name = force_action_name
        else:
            action_name = point_id.name
        # This is for order amt points update
        if credit == 0:
            credit = point_id.points
        txn_id = self.env['sltech.point.txn'].create({
            'user_id': self.id,
            'credit': credit,
            'name': action_name
        })

        return txn_id.id

    def get_points(self):
        tnx_ids = self.env['sltech.point.txn'].search([('user_id', '=', self.id)])
        return {
            'total_points': sum(x.credit - x.debit for x in tnx_ids),
            'refer_code': self.refer_code
        }
    def sltech_sign_up(self,refer_code,values):
        print(values,"==============value============")
        print(refer_code,"===============ref===========")
        user_id = self.sudo().create(values)
        user_id.create_points('sign_up')
        if refer_code:
            refer_by_user_id =self.search([('refer_code','=',refer_code)])
            user_id.sudo().update({'refer_by':refer_by_user_id.id})

        return user_id.id

    def sltech_product_review(self, partner_id, product_tmpl_id, rating, review):
        # print(partner_id, product_tmpl_id, rating, review)
        sale_order_line = self.env['sale.order.line'].sudo().search(
            [('order_partner_id', '=', partner_id), ('product_id.product_tmpl_id', '=', product_tmpl_id),
             ('state', 'in', ['sale', 'done'])])
        if sale_order_line:
            self.env['rating.rating'].sudo().create({
                'rated_partner_id':partner_id,
                'partner_id':partner_id,
                'rating': float(rating),
                'feedback': review,
                'res_id': product_tmpl_id,
                'res_model_id': self.env['ir.model']._get('product.template').id, #self.env['ir.model'].search([('name', '=', 'product.template')]).id,
                'consumed': True,
            })

            if not self.isProductReview:
                self.create_points("product_review")
                self.update({'isProductReview': True})

            return {'status': 200, 'msg': "Thank you"}

        else:
            return {'status': 401, 'msg': "Please purchase this product first"}




class PointRules(models.Model):
    _name = "sltech.points.rules"

    name = fields.Char('Name')
    points = fields.Integer('Points')

    _sql_constraints = [
        ('sltech_point_name_uniq', 'unique(name)', 'The Point Name must be unique!')
    ]

class PointTxn(models.Model):
    _name = "sltech.point.txn"

    user_id = fields.Many2one('res.users', string="User")
    credit = fields.Integer(default=0)
    debit = fields.Integer(default=0)
    name = fields.Char("Name")

class ResCompany(models.Model):
    _inherit = "res.company"

    delivery_range = fields.Float(string='Delivery Range In KM')


class Website(models.Model):
    _inherit = "website"

    top_banner_ids = fields.One2many('ir.attachment', 'top_banner_id', string='Top Banner Images')
    first_cat_ids = fields.Many2many('product.public.category', 'abc_rel')

    special_for_you_ids = fields.One2many('ir.attachment', 'special_for_you_id', string='Special For You')

    cat_ids = fields.Many2many('product.public.category', 'abc1_rel')
    minimum_order_price = fields.Float('Minimum Order Price',default=500)




class ProductTemplate(models.Model):
    _inherit = "product.template"

    def sltech_get_combination_info(self, product_template_id, product_id=0, combination={}, add_qty=1,
                                    partner_id=False):
        original_combo = combination
        if combination:
            # print(combination)

            def getRealCombo(combination, product_template_id):
                data = []
                for attribute in combination:
                    product_template_attribute_value_id = self.env['product.template.attribute.value'].search(
                        [('attribute_id', '=', int(attribute)),
                         ('product_tmpl_id', '=', product_template_id),
                         ('product_attribute_value_id', '=', combination[attribute])]
                    )
                    data.append(product_template_attribute_value_id.id)
                return data

            combination = getRealCombo(combination, product_template_id)
            # print(combination, '=======')
            combination = self.env['product.template.attribute.value'].browse(combination)
            kw = {'pricelist_id': False, 'parent_combination': [], 'context': {'website_sale_stock_get_quantity': True}}
            pricelist = self.env['product.pricelist'].search([], limit=1)
            ProductTemplate = self.env['product.template']
            if 'context' in kw:
                ProductTemplate = ProductTemplate.with_context(**kw.get('context'))
            product_template = ProductTemplate.browse(int(product_template_id))
            res = product_template._get_combination_info(combination, int(product_id or 0), int(add_qty or 1),
                                                         pricelist)
            if 'parent_combination' in kw:
                parent_combination = self.env['product.template.attribute.value'].browse(kw.get('parent_combination'))
                if not combination.exists() and product_id:
                    product = self.env['product.product'].browse(int(product_id))
                    if product.exists():
                        combination = product.product_template_attribute_value_ids
                res.update({
                    'is_combination_possible': product_template._is_combination_possible(combination=combination,
                                                                                         parent_combination=parent_combination),
                    'parent_exclusions': product_template._get_parent_attribute_exclusions(
                        parent_combination=parent_combination)
                })

            res.update({'combnation': original_combo,
                        'rating_avg': self.env['product.product'].browse(res['product_id']).rating_avg})
        else:

            product_id = self.env['product.product'].search([('product_tmpl_id', '=', product_template_id)], limit=1)
            combination = {}
            for value in product_id.product_template_variant_value_ids:
                combination.update({value.attribute_id.id: value.product_attribute_value_id.id})
            res = {'product_id': product_id.id, 'product_template_id': product_template_id,
                   'display_name': product_id.display_name,
                   'display_image': True, 'price': 1.0, 'list_price': product_id.list_price,
                   'has_discounted_price': False,
                   'combnation': combination,
                   'base_unit_name': 'Units', 'base_unit_price': 0.0, 'free_qty': 0.0, 'product_type': 'product',
                   'product_template': product_template_id, 'available_threshold': 5.0, 'cart_qty': 0,
                   'uom_name': 'Units',
                   'allow_out_of_stock_order': True, 'show_availability': False,
                   'out_of_stock_message': '<p><br></p>', 'is_combination_possible': True,
                   'parent_exclusions': {}, 'rating_avg': product_id.rating_avg}
        datas = []
        # print(self, '======')
        for line in self.attribute_line_ids:
            datas.append({
                'attribute_id': {
                    'id': line.attribute_id.id,
                    'name': line.attribute_id.name,
                    'display_type': line.attribute_id.display_type,
                    'help': 'Please use color value in display type'
                },
                'value_ids': [{
                    'id': x.id,
                    'name': x.name,
                    'html_color': x.html_color
                } for x in line.value_ids]
            })
        res.update({
            'attribute_line_ids': datas
        })
        res.update({'description_sale': self.description_sale, 'name': self.name,
                    'wishlist': False,
                    })
        if partner_id:
            print(res['product_id'], '---------------')
            res.update({'wishlist': self.env['product.wishlist'].search(
                [('product_id', '=', res['product_id']), ('partner_id', '=', partner_id)]).id})
        # print(res,")))))))))))))))))))))")
        return res

    def sltech_add_wishlist(self, res_id, modal, partner_id):
        if modal == 'product.template':
            product_id = self.env['product.product'].search([('product_tmpl_id', '=', res_id)], limit=1)

        else:
            product_id = self.env['product.product'].browse(res_id)

        wish = self.env['product.wishlist']._add_to_wishlist(self.env.ref('product.list0').id,
                                                             self.env.user.company_id.currency_id.id,
                                                             self.env.ref('website.default_website').id,
                                                             product_id.list_price,
                                                             product_id.id, partner_id)
        return wish.id


class ProductWishlist(models.Model):
    _inherit = "product.wishlist"

    product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id', store=True)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def sltech_cart_update(self, product_id, add_qty):
        self._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=0,
            product_custom_attribute_values=False,
            no_variant_attribute_values=False
        )
        return True

    def sltech_delivery_status(self):
        if any(x for x in self.picking_ids if x.state == 'done'):
            return 'Delivered'
        return 'Not Delivered'

    def sltech_create_final_payment(self, user_id, data):
        # # here user id will be the signup / login user id
        # user = self.env['res.users'].sudo().browse(user_id)
        # user.sudo().create_points('confirm_order', int(math.floor(self.amount_total * 0.1)),'confirm_order')
        #
        # if user.isFirstOrder:
        #     # one more step should be done
        #     user.refer_by.sudo().create_points('refer_and_earn')
        #     user.sudo().update({'isFirstOrder': False})
        #
        # # self.message_post(body=str(data))
        #
        # token_id = self.env['payment.token'].create({
        #     'acquirer_id': self.env.ref('paytm_payment_gateway.payment_acquirer_atom').id,
        #     'acquirer_ref': data['ORDERID'],
        #     'name': data['TXNID'],
        #     'partner_id': self.partner_id.id,
        #
        # })
        #
        # tx = self.env['payment.transaction'].sudo().search([('reference', '=', data['ORDERID'])])
        # tx.update({'state_message': data,
        #            'token_id': token_id,
        #            'sale_order_ids': self.ids})
        # tx._create_payment()
        # tx._set_done()
        # self.origin= data['ORDERID']
        # self.client_order_ref =data['TXNID']

        self.action_confirm()
        return True


    def sltech_get_paytm_details(self):

        if self.amount_total < 500:
            return {'statusCode': 500, 'msg': 'You must Purchase atleast ₹500!'}

        paytm_acquirer_id = self.env.ref('paytm_payment_gateway.payment_acquirer_atom')
        callback_URL = ""
        if paytm_acquirer_id.state == "test":
            callback_URL = "https://securegw-stage.paytm.in/theia/paytmCallback?ORDER_ID"
            initiate_url = "https://securegw-stage.paytm.in/theia/api/v1/initiateTransaction"
        elif paytm_acquirer_id.state == "enabled":
            callback_URL = "https://securegw.paytm.in/theia/paytmCallback?ORDER_ID"
            initiate_url = "https://securegw.paytm.in/theia/api/v1/initiateTransaction"
        partner_id = self.partner_id

        # reference = self.env['payment.transaction']._compute_reference(paytm_acquirer_id)

        Transaction = self.env['payment.transaction']
        reference = Transaction._compute_reference(paytm_acquirer_id)

        tx_sudo = Transaction.sudo().create({
            'acquirer_id': paytm_acquirer_id.id,
            'reference': reference,
            'amount': self.amount_total,
            'currency_id': self.currency_id.id,
            'partner_id': partner_id.id,
            # 'token_id': token_id,
            # 'operation': f'online_{flow}' if not is_validation else 'validation',
            # 'tokenize': tokenize,
            # 'landing_route': landing_route,
            # **(custom_create_values or {}),
        })  # In sudo mode to allow writing on callback fields

        paytmParams = dict()

        paytmParams["body"] = {
            "requestType": "Payment",
            "mid": paytm_acquirer_id.paytm_merchant_id,
            "websiteName": "WEBSTAGING",
            "orderId": reference,
            "callbackUrl": callback_URL + reference,
            "txnAmount": {
                "value": str(self.amount_total),
                "currency": "INR",
            },
            "userInfo": {
                "custId": str(partner_id.id),
            },

        }
        #  "enablePaymentMode":[{"mode" : "UPI", "channels" : ["UPI, UPIPUSH, UPIPUSHEXPRESS"]}],
        # Generate checksum by parameters we have in body
        # Find your Merchant Key in your Paytm Dashboard at https://dashboard.paytm.com/next/apikeys
        checksum = generateSignature(json.dumps(paytmParams["body"]),
                                                   paytm_acquirer_id.paytm_merchant_key)

        paytmParams["head"] = {
            "signature": checksum,
            "channelId": "WAP",
        }

        post_data = json.dumps(paytmParams)

        url = initiate_url + "?mid=" + paytmParams["body"]['mid'] + "&orderId=" + paytmParams["body"]['orderId']
        try:
            response = requests.post(url, data=post_data, headers={"Content-type": "application/json"}).json()
            if response['body']['resultInfo']['resultStatus'] == 'S':
                response.update({'statusCode': 200, 'details': paytmParams["body"]})
                response.update({'tx_sudo': tx_sudo.id})

            else:
                response.update({'statusCode': 400})

            print(response,'.............response')

            return response
        except:
            return {'statusCode': 500, 'msg': 'Internal Server Error'}


    def sltech_refund(self,comment):

        paytmParams = dict()

        paytm_acquirer_id = self.env.ref('paytm_payment_gateway.payment_acquirer_atom')

        Transaction = self.env['payment.transaction']
        reference = Transaction._compute_reference(paytm_acquirer_id)
        paytmParams["body"] = {
            "mid": paytm_acquirer_id.paytm_merchant_id,
            "txnType": "REFUND",
            "orderId": self.origin,
            "txnId": self.client_order_ref,
            "refId": reference, # str(datetime.now().replace(" ")),
            "refundAmount": self.amount_total,
            # "preferredDestination":"TO_INSTANT",
            "comments": "Refunding from ODOO"+comment
        }

        # Generate checksum by parameters we have in body
        # Find your Merchant Key in your Paytm Dashboard at https://dashboard.paytm.com/next/apikeys
        checksum = generateSignature(json.dumps(paytmParams["body"]), paytm_acquirer_id.paytm_merchant_key)

        paytmParams["head"] = {
            "signature": checksum
        }

        post_data = json.dumps(paytmParams)
        print(post_data, "-----------------------")


        if paytm_acquirer_id.state == "test":
            # for Staging
            url = "https://securegw-stage.paytm.in/refund/apply"
        elif paytm_acquirer_id.state == "enabled":
            # for Production
            url = "https://securegw.paytm.in/refund/apply"
        try:
            response = requests.post(url, data=post_data, headers={"Content-type": "application/json"}).json()
            # self.message_post(body=str(response))
            print(response, "=====================")
            if response['body']['resultInfo']['resultCode'] == "601":
                self.action_cancel()
                return True
            print("try=====================")
            return False
        except:
            print("except=====================")
            return False

    def sltech_lat_long_distance(self, lat_user, long_user):
        # approximate radius of earth in km
        R = 6373.0
        company_lat_long = self.env.user.company_id.partner_id
        print(company_lat_long, 'company_lat_long')
        sltech_delivery_range = self.env.user.company_id.delivery_range
        comp_lat = company_lat_long.partner_latitude
        print(comp_lat, 'comp_lat')
        comp_long = company_lat_long.partner_longitude
        print(comp_long, 'comp_long')
        lat1 = radians(comp_lat)
        lon1 = radians(comp_long)
        lat2 = radians(lat_user)
        lon2 = radians(long_user)

        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance = R * c
        print("Result:", distance)

        if distance <= sltech_delivery_range:
            return True
        else:
            return False


