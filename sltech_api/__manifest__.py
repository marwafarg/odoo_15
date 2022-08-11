{
    "name": "Ecommerce",
    "author": "SL TECH ERP SOLUTION",
    "website": "https://sltecherpsolution.com/",
    "depends": ['base', 'website_sale', 'website_sale_wishlist', 'rating', 'base_geolocalize'],
    "data": [
        'security/ir.model.access.csv',
        'views/website.xml',
        'views/ir_attachment.xml',
        'views/res_users.xml'
    ],
    'post_init_hook': '_update_res_users',
    "auto_install": False,
    "installable": True,
}

